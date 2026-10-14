from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest
from pypdf import PdfReader

from make_test_invoices import line_items

ROOT = Path(__file__).parent.parent
INVOICES = ROOT / "invoices"
FIELDS = [
    "document_type", "supplier_name", "gst_number", "invoice_number", "invoice_date", "due_date",
    "buyer_name", "buyer_identifier", "reference", "work_order", "site", "subtotal", "gst", "total",
    "bank_account",
]


def answer_key():
    return pd.read_csv(ROOT / "answer_key.csv", dtype=str, keep_default_na=False)


def rows():
    return answer_key().to_dict("records")


def squash(text):
    """Ignore differences in spaces and line breaks, keep case."""
    return " ".join(text.split())


def pdf_text(file):
    return squash(" ".join(page.extract_text() for page in PdfReader(INVOICES / file).pages))


def test_answer_key_has_one_row_per_test_pdf():
    files = answer_key()["file"]
    assert files.is_unique
    assert sorted(files) == sorted(p.name for p in INVOICES.glob("*.pdf"))
    assert len(files) == 21


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["file"])
def test_every_answer_key_value_appears_in_its_pdf(row):
    text = pdf_text(row["file"])
    values = [row[f] for f in FIELDS] + [v for item in line_items(row) for v in item]
    missing = [v for v in values if v and squash(v) not in text]
    assert not missing, f"not in PDF text: {missing}"


FLAG_LABELS = {
    "Not a bill:", "Credit note:", "Missing for IRD:", "Missing:", "Maths:", "Wrong GST:", "Duplicate:",
    "GST number invalid:", "Unknown supplier:", "Supplier mismatch:", "Bank account changed:",
    "Future date:", "Old invoice:", "Wrong entity:", "Property unclear:", "No property:",
    "Source text not found:", "Unreadable:", "Could not read:",
}
CLEAN = {"01-clean.pdf", "11-sole-trader.pdf", "18-exactly-1000.pdf"}
NO_PROBLEM_PLANTED = {"05-alias.pdf", "12-job-management.pdf", "13-xero-newer.pdf"}  # property and layout tests


def flags(row):
    return [f.strip() for f in row["expected_flags"].split(";") if f.strip()]


def money(s):
    return Decimal(s.replace("$", "").replace(",", ""))


@pytest.mark.parametrize("row", rows(), ids=lambda r: r["file"])
def test_only_problem_invoices_list_flags(row):
    if row["file"] in CLEAN | NO_PROBLEM_PLANTED:
        assert flags(row) == []
    else:
        assert flags(row)
    assert row["expected_status"] == ("Needs you" if flags(row) else "Looks fine")


def test_every_flag_label_is_from_the_fixed_set():
    assert {f for row in rows() for f in flags(row)} <= FLAG_LABELS


@pytest.mark.parametrize("file", sorted(CLEAN))
def test_clean_invoice_amounts_add_up(file):
    row = next(r for r in rows() if r["file"] == file)
    items = [money(amount) for _, amount in line_items(row)]
    if not row["subtotal"]:  # GST-inclusive total only, allowed at $200 or less
        assert sum(items) == money(row["total"]) <= 200
        return
    subtotal, gst = money(row["subtotal"]), money(row["gst"])
    assert sum(items) == subtotal
    assert subtotal + gst == money(row["total"])
    assert abs(gst - subtotal * Decimal("0.15")) <= Decimal("0.01") * len(items)


def test_clean_invoice_uses_the_agreed_gst_number():
    assert rows()[0]["file"] == "01-clean.pdf"
    assert rows()[0]["gst_number"] == "112-345-671"


def test_run_date_is_fixed():
    assert set(answer_key()["run_date"]) == {"2026-10-15"}


def test_planted_edge_cases():
    key = {r["file"]: r for r in rows()}
    suppliers = pd.read_csv(ROOT / "suppliers.csv", dtype=str).set_index("name")
    past = pd.read_csv(ROOT / "past_invoices.csv", dtype=str)

    # #1 prints a 2-digit bank suffix; suppliers.csv has 3.
    assert key["01-clean.pdf"]["bank_account"] == "99-0101-0123456-01"
    assert suppliers.loc["Southbridge Electrical Limited", "bank_account"] == "99-0101-0123456-001"
    # #1's buyer address is at another property.
    assert "Matai Centre" in key["01-clean.pdf"]["buyer_identifier"]
    # #12 prints the macron.
    assert key["12-job-management.pdf"]["site"] == "Kōwhai House"
    # #4 resends a past invoice; #8 reduces one.
    assert "INV-3288" in set(past["invoice_number"])
    assert "INV-7731" in set(past["invoice_number"])
    assert "INV-7731" in key["08-credit-note.pdf"]["reference"]
    # Supplier name printed with "Limited" where suppliers.csv says "Ltd".
    assert key["13-xero-newer.pdf"]["supplier_name"] == "Bellbird Cleaning Limited"
    assert "Bellbird Cleaning Ltd" in suppliers.index
