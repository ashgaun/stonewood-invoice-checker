import copy
import shutil

import pytest

from check_invoices import run
from test_check_invoices import KEY, ROOT, RUN_DATE, fake_extract, read_review

CRITERIA = [
    "No Flags on clean invoices",
    "Every planted problem flagged",
    "Property correct or Needs you",
    "Same status in both runs",
]
FIELDS = [
    "document_type", "supplier_name", "gst_number", "invoice_number", "invoice_date", "due_date",
    "buyer_name", "buyer_identifier", "reference", "work_order", "site", "subtotal", "gst", "total",
    "bank_account", "line_items",
]


def all_invoices(folder):
    folder.mkdir()
    for f in KEY.index:
        shutil.copy(ROOT / "invoices" / f, folder)
    return folder


def run_all(folder, name, extract=fake_extract):
    """One run over all 21 invoices: (rows run returned, rows read back from the sheet)."""
    out = folder.parent / f"{name}.xlsx"
    returned = run(folder, out, extract, RUN_DATE)
    return returned, read_review(out)


def score_of(*runs):
    import score
    return score.score(list(runs))


def labels(row):
    return sorted(line[:line.index(":") + 1] for line in (row["Flags"] or "").splitlines())


def expected_labels(file):
    return sorted(f.strip() for f in KEY.loc[file, "expected_flags"].split(";") if f.strip())


@pytest.fixture(scope="module")
def clean_runs(tmp_path_factory):
    """Two runs of all 21 invoices with the perfect fake extractor."""
    folder = all_invoices(tmp_path_factory.mktemp("full") / "invoices")
    return run_all(folder, "run1"), run_all(folder, "run2")


def test_all_21_invoices_match_the_answer_key_status_flags_and_property(clean_runs):
    (_, sheet), _ = clean_runs
    assert sorted(r["File"] for r in sheet) == sorted(KEY.index)
    for row in sheet:
        file = row["File"]
        assert row["Status"] == KEY.loc[file, "expected_status"], (file, row["Flags"])
        assert labels(row) == expected_labels(file), (file, row["Flags"])
        assert row["Suggested property"] == (KEY.loc[file, "expected_property"] or None), file


def test_needs_you_rows_come_first_then_looks_fine_each_in_file_order(clean_runs):
    (returned, sheet), _ = clean_runs
    files = [r["File"] for r in sheet]
    needs_you = sorted(f for f in KEY.index if KEY.loc[f, "expected_status"] == "Needs you")
    looks_fine = sorted(f for f in KEY.index if KEY.loc[f, "expected_status"] == "Looks fine")
    assert files == needs_you + looks_fine
    assert [r["File"] for r in returned] == files


def test_scoring_the_fake_extractor_passes_every_criterion_with_100_percent_fields(clean_runs):
    (run1, _), (run2, _) = clean_runs
    result = score_of(run1, run2)
    assert result["must_pass"] == {c: [] for c in CRITERIA}
    assert result["wrong_fields"] == []
    assert set(result["by_field"]) == set(FIELDS)
    assert all(result["by_field"][f] == (42, 42) for f in FIELDS), result["by_field"]
    assert set(result["by_layout"]) == set(KEY["layout"])
    assert all(right == total for right, total in result["by_layout"].values()), result["by_layout"]
    assert sum(total for _, total in result["by_layout"].values()) == len(FIELDS) * 21 * 2


def test_wrong_total_and_wrong_site_are_reported_naming_run_invoice_and_field(clean_runs, tmp_path):
    def extract(pdf):
        out = fake_extract(pdf)
        if pdf.name == "01-clean.pdf":
            out["total"]["source_text"] = "$1,026.00"  # printed on #1 as its subtotal
            out["site"]["source_text"] = "Matai Centre"  # printed on #1 in the buyer address
        return out

    wrong, _ = run_all(all_invoices(tmp_path / "invoices"), "wrong", extract)
    (clean, _), _ = clean_runs
    result = score_of(wrong, clean)

    assert len(result["wrong_fields"]) == 2, result["wrong_fields"]
    total, = [w for w in result["wrong_fields"] if "total" in w]
    site, = [w for w in result["wrong_fields"] if "site" in w]
    for failure in (total, site):
        assert "run 1" in failure and "01-clean.pdf" in failure
    assert result["by_field"]["total"] == (41, 42)
    assert result["by_field"]["site"] == (41, 42)
    assert result["by_layout"]["standard"][0] == result["by_layout"]["standard"][1] - 2

    [failure] = result["must_pass"]["No Flags on clean invoices"]
    assert "01-clean.pdf" in failure and "run 1" in failure


def test_a_wrong_property_fails_even_on_a_needs_you_row(clean_runs):
    # Never a wrong property: she may trust the suggestion while fixing the row's other Flag.
    (run1, _), (run2, _) = clean_runs
    run1 = copy.deepcopy(run1)
    rows = {r["File"]: r for r in run1}
    rows["05-alias.pdf"]["Suggested property"] = "Matai Centre"  # Looks fine
    rows["02-wrong-gst.pdf"]["Suggested property"] = "Kowhai House"  # Needs you for its GST

    looks_fine, needs_you = sorted(score_of(run1, run2)["must_pass"]["Property correct or Needs you"],
                                   key=lambda f: "02-wrong-gst.pdf" in f)
    assert "05-alias.pdf" in looks_fine and "run 1" in looks_fine
    assert "Matai Centre" in looks_fine and "Kowhai House" in looks_fine
    assert "02-wrong-gst.pdf" in needs_you and "run 1" in needs_you
    assert "Kowhai House" in needs_you and "Matai Centre" in needs_you


def test_no_property_on_a_needs_you_row_passes(clean_runs):
    (run1, _), (run2, _) = clean_runs
    run1 = copy.deepcopy(run1)
    row, = [r for r in run1 if r["File"] == "02-wrong-gst.pdf"]
    row["Suggested property"] = None  # blank, so nothing wrong is shown

    assert score_of(run1, run2)["must_pass"]["Property correct or Needs you"] == []


def test_a_planted_problem_without_its_flag_fails_naming_the_invoice(clean_runs):
    (run1, _), (run2, _) = clean_runs
    run2 = copy.deepcopy(run2)
    row, = [r for r in run2 if r["File"] == "19-two-problems.pdf"]
    row["Flags"] = row["Flags"].splitlines()[0]  # one of its two Flags missing

    [failure] = score_of(run1, run2)["must_pass"]["Every planted problem flagged"]
    assert "19-two-problems.pdf" in failure and "run 2" in failure


def test_two_runs_with_different_statuses_for_one_invoice_are_inconsistent(clean_runs):
    (run1, _), (run2, _) = clean_runs
    run2 = copy.deepcopy(run2)
    row, = [r for r in run2 if r["File"] == "13-xero-newer.pdf"]
    row["Status"] = "Needs you"

    [failure] = score_of(run1, run2)["must_pass"]["Same status in both runs"]
    assert "13-xero-newer.pdf" in failure


def test_report_says_pass_for_each_criterion_and_shows_accuracy(clean_runs):
    import score
    (run1, _), (run2, _) = clean_runs
    text = score.report(score.score([run1, run2]))
    for criterion in CRITERIA:
        line, = [l for l in text.splitlines() if criterion in l]
        assert "PASS" in line, line
    assert "FAIL" not in text
    assert "100%" in text
    for name in FIELDS + sorted(set(KEY["layout"])):
        assert name in text, name


def test_report_says_fail_and_names_the_invoice_that_broke_it(clean_runs):
    import score
    (run1, _), (run2, _) = clean_runs
    run2 = copy.deepcopy(run2)
    row, = [r for r in run2 if r["File"] == "13-xero-newer.pdf"]
    row["Status"] = "Needs you"

    text = score.report(score.score([run1, run2]))
    line, = [l for l in text.splitlines() if "Same status in both runs" in l]
    assert "FAIL" in line, line
    assert "13-xero-newer.pdf" in text
