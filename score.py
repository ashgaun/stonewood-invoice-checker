"""Live scoring: check the test invoices twice with the real extractor and score both runs against answer_key.csv.

Usage: python score.py invoices/
Not part of pytest, because it calls OpenAI.
"""
import argparse
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from check_invoices import PARSERS, parse_amount, run, squash
from make_test_invoices import line_items

KEY = pd.read_csv(Path(__file__).parent / "answer_key.csv", dtype=str, keep_default_na=False).set_index("file")
FIELDS = [
    "document_type", "supplier_name", "gst_number", "invoice_number", "invoice_date", "due_date",
    "buyer_name", "buyer_identifier", "reference", "work_order", "site", "subtotal", "gst", "total",
    "bank_account", "line_items",
]
CLEAN = ["01-clean.pdf", "11-sole-trader.pdf", "18-exactly-1000.pdf"]
CRITERIA = ["No Flags on clean invoices", "Every planted problem flagged", "Property correct or Needs you",
            "Same status in both runs"]


def labels(flags):
    return [line.partition(":")[0] + ":" for line in (flags or "").splitlines()]


def expected_values(file):
    """The answer key's values, worked out the same way the checker works out extracted ones."""
    row = KEY.loc[file]
    values = {f: PARSERS.get(f, squash)(row[f]) if row[f] else None for f in FIELDS if f != "line_items"}
    values["line_items"] = [(squash(d), parse_amount(a)) for d, a in line_items(row)]
    return values


def show(value):
    if value is None:
        return "(blank)"
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, list):
        return " | ".join(f"{show(d)} = {show(a)}" for d, a in value) or "(blank)"
    return str(value)


def score(runs):
    """Score each run's rows (as returned by check_invoices.run) against the answer key."""
    must = {name: [] for name in CRITERIA}
    wrong, right, total = [], Counter(), Counter()
    for n, rows in enumerate(runs, 1):
        by_file = {row["File"]: row for row in rows}  # rows not in the answer key are left out
        for file, key in KEY.iterrows():
            row = by_file.get(file, {"Status": "not in this run", "Flags": None})
            flags = (row["Flags"] or "").replace("\n", " / ")
            if file in CLEAN and row["Status"] != "Looks fine":
                must["No Flags on clean invoices"].append(
                    f"run {n}: {file} is {row['Status']}" + (f": {flags}" if flags else ""))
            missing = [f.strip() for f in key["expected_flags"].split(";")
                       if f.strip() and f.strip() not in labels(row["Flags"])]
            if missing:
                must["Every planted problem flagged"].append(
                    f"run {n}: {file} is missing {', '.join(missing)} (got: {flags or 'no Flags'})")
            suggested = row.get("Suggested property") or ""  # a row that could not be read has none
            # Never a wrong property: blank is fine only on a Needs you row, a wrong one never is.
            if suggested != key["expected_property"] and (suggested or row["Status"] != "Needs you"):
                must["Property correct or Needs you"].append(
                    f"run {n}: {file} suggested {suggested or '(none)'}, answer key {key['expected_property'] or '(none)'}"
                    f" ({row['Status']})")

            want = expected_values(file)
            got = dict(row["values"], line_items=row["items"]) if "values" in row else None
            for field in FIELDS:
                ok = got is not None and got[field] == want[field]
                right[field] += ok
                total[field] += 1
                right["layout", key["layout"]] += ok
                total["layout", key["layout"]] += 1
                if not ok:
                    shown = show(got[field]) if got else "(not read)"
                    wrong.append(f"run {n}: {file} {field}: got {shown}, answer key {show(want[field])}")

    statuses = [{row["File"]: row["Status"] for row in rows} for rows in runs]
    for file in KEY.index:
        seen = [s.get(file, "not in this run") for s in statuses]
        if len(set(seen)) > 1:
            must["Same status in both runs"].append(
                f"{file}: " + ", ".join(f"run {n} {s}" for n, s in enumerate(seen, 1)))

    return {
        "must_pass": must,
        "wrong_fields": wrong,
        "by_field": {f: (right[f], total[f]) for f in FIELDS},
        "by_layout": {k: (right["layout", k], total["layout", k]) for k in sorted(set(KEY["layout"]))},
    }


def report(result):
    lines = ["Must pass"]
    for name, failures in result["must_pass"].items():
        lines.append(f"  {'FAIL' if failures else 'PASS'}  {name}")
        lines += [f"        {f}" for f in failures]
    for title, counts in [("by field", result["by_field"]), ("by layout", result["by_layout"])]:
        lines += ["", f"Field accuracy {title} (reported, not required to pass)"]
        # Rounded down, so 100% only when every one is right.
        lines += [f"  {name:<18} {r * 100 // t:>4}%  ({r}/{t})" for name, (r, t) in counts.items()]
    lines += ["", "Wrong fields"] + [f"  {w}" for w in result["wrong_fields"] or ["none"]]
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the test invoices twice with OpenAI and score against answer_key.csv.")
    parser.add_argument("folder", help="folder of test invoice PDFs, e.g. invoices/")
    args = parser.parse_args()
    pdfs = {pdf.name for pdf in Path(args.folder).glob("*.pdf")}
    if pdfs != set(KEY.index):  # before any OpenAI call
        parser.error(f"{args.folder} must hold exactly the PDFs in answer_key.csv. "
                     f"Missing: {', '.join(sorted(set(KEY.index) - pdfs)) or 'none'}. "
                     f"Not in answer_key.csv: {', '.join(sorted(pdfs - set(KEY.index))) or 'none'}.")
    from extractor import extract
    run_date = date.fromisoformat(KEY["run_date"].iloc[0])  # one fixed run date, so #16 stays in the future
    with tempfile.TemporaryDirectory() as tmp:
        runs = [run(args.folder, Path(tmp) / f"run{n}.xlsx", extract, run_date) for n in (1, 2)]
    result = score(runs)
    sys.stdout.reconfigure(encoding="utf-8")  # so "Kōwhai" prints when the report is redirected to a file
    print(report(result))
    sys.exit(1 if any(result["must_pass"].values()) else 0)
