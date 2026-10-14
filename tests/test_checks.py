import shutil
from datetime import date
from decimal import Decimal

import pytest

import checks
import check_invoices
from make_test_invoices import line_items
from test_check_invoices import KEY, ROOT, RUN_DATE, fake_extract, read_review

TICKET_04 = {"Wrong entity:", "Property unclear:", "No property:"}


# Seam 2: helpers

@pytest.mark.parametrize("number", ["112-345-671", "49-091-850", "49091850", "112345671"])
def test_gst_number_passing_the_check_digit_is_valid(number):
    assert checks.gst_number_valid(number)


@pytest.mark.parametrize("number", ["112-233-445", "119-753-185", "136-410-132"])
def test_gst_number_whose_first_check_digit_is_10_uses_the_second_weights(number):
    # Bellbird and Pohutukawa in suppliers.csv, and IRD's own example 136410132.
    assert checks.gst_number_valid(number)


def test_every_gst_number_in_the_test_data_passes_except_15s():
    numbers = {s["gst_number"]: "suppliers.csv" for s in checks.SUPPLIERS}
    numbers.update({n: file for file, n in KEY["gst_number"].items() if n})
    assert {n: f for n, f in numbers.items() if not checks.gst_number_valid(n)} == {"119-735-185": "15-bad-gst-number.pdf"}


@pytest.mark.parametrize("number", ["112-345-672", "49-091-851", "136-410-133", "119-735-185", "1234567", "1123456710"])
def test_gst_number_with_changed_last_digit_or_wrong_length_is_invalid(number):
    assert not checks.gst_number_valid(number)


@pytest.mark.parametrize("printed", ["12-3456-0123456-00", "12 3456 0123456 000", "123456012345600"])
def test_bank_accounts_written_differently_are_the_same(printed):
    assert checks.bank_key(printed) == checks.bank_key("12-3456-0123456-000")


def test_a_different_bank_account_is_not_the_same():
    assert checks.bank_key("12-3456-0123456-01") != checks.bank_key("12-3456-0123456-000")


@pytest.mark.parametrize("printed", [
    "Southbridge Electrical Ltd", "SOUTHBRIDGE ELECTRICAL LIMITED", "Southbridge Electrical Ltd.", "Southbridge, Electrical",
])
def test_supplier_names_ignore_case_punctuation_and_ltd(printed):
    assert checks.name_key(printed) == checks.name_key("Southbridge Electrical Limited")


def test_supplier_names_are_not_fuzzy_matched():
    assert checks.name_key("Southbridge Electric Limited") != checks.name_key("Southbridge Electrical Limited")


# Seam 1: run() through review.xlsx, with a fake extract from the answer key

def no_property_match(values, items):
    """Ticket 04 is built in parallel. Keep these tests to checks 1-9 and 11."""
    return None, None, []


def run_on(folder, extract=fake_extract, run_date=RUN_DATE):
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(check_invoices.property_match, "suggest", no_property_match)
        check_invoices.run(folder, folder / "review.xlsx", extract, run_date)
    return {row["File"]: row for row in read_review(folder / "review.xlsx")}


def copy_invoices(folder, files):
    folder.mkdir(exist_ok=True)
    for f in files:
        shutil.copy(ROOT / "invoices" / f, folder)
    return folder


@pytest.fixture(scope="module")
def all_rows(tmp_path_factory):
    """Every test invoice in one run, so in-run duplicate checks see the whole set."""
    return run_on(copy_invoices(tmp_path_factory.mktemp("all"), list(KEY.index)))


def labels(row):
    return [line[:line.index(":") + 1] for line in (row["Flags"] or "").splitlines()]


def expected_labels(file):
    return [f.strip() for f in KEY.loc[file, "expected_flags"].split(";") if f.strip()]


# Each planted problem, with numbers or values that must appear in its Flag text.
PLANTED = {
    "02-wrong-gst.pdf": ["$52.00", "$60.00", "$400.00"],
    "03-bad-totals.pdf": ["$445.00", "$455.00"],
    "04-duplicate.pdf": ["INV-3288", "past_invoices.csv", "22/09/2026", "$862.50"],
    "06-bank-changed.pdf": ["99-0188-0876543-000", "99-0105-0567890-000", "Greystone Glazing Limited"],
    "07-no-buyer.pdf": ["buyer name", "buyer identifier", "$1,000", "$1,380.00"],
    "08-credit-note.pdf": ["CN-0112", "-$172.50", "INV-7731", "08/09/2026", "$1,035.00", "past_invoices.csv"],
    "09-quote.pdf": ["QUOTE"],
    "10-statement.pdf": ["STATEMENT OF ACCOUNT"],
    "14-unknown-supplier.pdf": ["Kauri Point Roofing Limited", "103-135-796", "suppliers.csv"],
    "15-bad-gst-number.pdf": ["119-735-185", "check digit"],
    "16-future-date.pdf": ["28/10/2026", "15/10/2026"],
    "19-two-problems.pdf": ["$80.00", "$90.00", "99-0177-0987654-000", "99-0103-0345678-002"],
    "20-no-gst-number.pdf": ["GST number", "$200", "$230.00"],
}


@pytest.mark.parametrize("file", PLANTED)
def test_planted_problem_gets_exactly_the_expected_flags_with_numbers(all_rows, file):
    row = all_rows[file]
    assert sorted(labels(row)) == sorted(expected_labels(file)), row["Flags"]
    assert row["Status"] == KEY.loc[file, "expected_status"] == "Needs you"
    for text in PLANTED[file]:
        assert text in row["Flags"]


# Seam 1 cases no test PDF can show: checks.check with values built from the answer key.

def values_of(file, **changes):
    """values and items as run() would pass them for this invoice, with some fields changed."""
    row = KEY.loc[file]
    values = {f: check_invoices.PARSERS.get(f, str)(row[f]) if row[f] else None
              for f in check_invoices.Extraction.model_fields if f != "line_items"}
    items = [(d, check_invoices.parse_amount(a)) for d, a in line_items(row)]
    values.update(changes)
    return values, items


@pytest.mark.parametrize("gst, flagged", [("15.01", False), ("14.99", False), ("15.02", True), ("14.98", True)])
def test_gst_off_by_exactly_the_tolerance_passes_and_one_cent_more_is_flagged(gst, flagged):
    # #5 has one line item of $320.00, so 15% is $48.00 and the tolerance is $0.01.
    values, items = values_of("05-alias.pdf", gst=Decimal("48.00") + Decimal(gst) - Decimal("15.00"))
    values["total"] = values["subtotal"] + values["gst"]
    flags, _ = checks.check(values, items, RUN_DATE, [])
    assert [f for f in flags if f.startswith("Wrong GST:")] == (
        [f"Wrong GST: GST is ${values['gst']} but 15% of the subtotal $320.00 is $48.00 (allowed difference $0.01)."]
        if flagged else [])


def copies_of_invoice_1(tmp_path, change_copy=lambda out: None):
    """#1 and a copy of it named 01-copy.pdf in one run."""
    folder = copy_invoices(tmp_path / "invoices", ["01-clean.pdf"])
    shutil.copy(folder / "01-clean.pdf", folder / "01-copy.pdf")

    def extract(pdf):
        out = fake_extract(folder / "01-clean.pdf")
        if pdf.name == "01-copy.pdf":
            change_copy(out)
        return out

    return run_on(folder, extract)


def test_two_copies_in_one_run_are_both_flagged_each_naming_the_other(tmp_path):
    rows = copies_of_invoice_1(tmp_path)
    for file, other in [("01-clean.pdf", "01-copy.pdf"), ("01-copy.pdf", "01-clean.pdf")]:
        assert labels(rows[file]) == ["Duplicate:"]
        assert rows[file]["Flags"] == (f"Duplicate: same supplier and invoice number as {other} "
                                       f"(Southbridge Electrical Limited INV-2147, 06/10/2026, $1,179.90) in this run.")


def test_same_supplier_date_and_amount_with_a_different_invoice_number_is_a_duplicate(tmp_path):
    def change_copy(out):
        out["invoice_number"]["source_text"] = "WO-30418"  # printed on #1, so it passes the source text check

    rows = copies_of_invoice_1(tmp_path, change_copy)
    assert rows["01-copy.pdf"]["Flags"] == ("Duplicate: same supplier, date and amount as 01-clean.pdf "
                                           "(Southbridge Electrical Limited INV-2147, 06/10/2026, $1,179.90) in this run.")
    assert labels(rows["01-clean.pdf"]) == ["Duplicate:"]
    assert "01-copy.pdf (Southbridge Electrical Limited WO-30418," in rows["01-clean.pdf"]["Flags"]


@pytest.mark.parametrize("number", ["INV 3288", "INV3288", "INV - 3288"])
def test_invoice_numbers_are_compared_ignoring_spaces_and_hyphens(number):
    # A resend of past invoice INV-3288 with a different date, so only the invoice number can match it.
    values, items = values_of("04-duplicate.pdf", invoice_number=number, invoice_date=date(2026, 10, 1))
    flags, _ = checks.check(values, items, RUN_DATE, [])
    assert [f[:f.index(":") + 1] for f in flags] == ["Duplicate:"]
    assert "same supplier and invoice number" in flags[0] and "INV-3288" in flags[0]


def test_gst_number_of_one_supplier_and_name_of_another_is_a_supplier_mismatch():
    values, items = values_of("01-clean.pdf", supplier_name="Ridgeline Plumbing Ltd")
    flags, _ = checks.check(values, items, RUN_DATE, [])
    assert flags == ["Supplier mismatch: GST number 112-345-671 belongs to Southbridge Electrical Limited in "
                     "suppliers.csv, but the invoice is from Ridgeline Plumbing Ltd."]


def test_known_name_with_a_valid_gst_number_that_is_not_theirs_is_a_supplier_mismatch():
    values, items = values_of("01-clean.pdf", gst_number="49-091-850")  # passes the check digit, on no supplier
    flags, _ = checks.check(values, items, RUN_DATE, [])
    assert flags == ["Supplier mismatch: Southbridge Electrical Limited has GST number 112-345-671 in "
                     "suppliers.csv, but the invoice shows 49-091-850."]


@pytest.mark.parametrize("run_date, flags", [
    (date(2027, 1, 4), None),  # #1 is dated 06/10/2026: exactly 90 days before
    (date(2027, 1, 5), "Old invoice: invoice date 06/10/2026 is 91 days before the run date 05/01/2027 "
                       "(limit 90 days)."),
])
def test_invoice_exactly_90_days_old_passes_and_91_days_is_flagged(tmp_path, run_date, flags):
    rows = run_on(copy_invoices(tmp_path / "invoices", ["01-clean.pdf"]), run_date=run_date)
    assert rows["01-clean.pdf"]["Flags"] == flags


@pytest.mark.parametrize("label", [
    "PRO FORMA INVOICE", "Pro-forma", "Pro. Forma Invoice", "Estimate", "Quotation", "Receipt", "Draft Invoice",
])
def test_anything_not_labelled_an_invoice_or_credit_note_is_not_a_bill_and_not_processed(label):
    values, items = values_of("01-clean.pdf", document_type=label)
    assert checks.check(values, items, RUN_DATE, []) == ([f"Not a bill: document is labelled {label}. Not processed."], [])


def test_blank_document_type_is_flagged_because_it_cannot_be_confirmed_as_a_bill():
    values, items = values_of("01-clean.pdf", document_type=None)
    flags, _ = checks.check(values, items, RUN_DATE, [])
    assert flags == ["Missing: document type is blank, so it cannot be confirmed as an invoice."]


def test_credit_note_whose_original_is_not_in_past_invoices_says_so(tmp_path):
    def extract(pdf):
        out = fake_extract(pdf)
        out["reference"]["source_text"] = "Matai Centre"  # printed on #8, but names no invoice
        return out

    rows = run_on(copy_invoices(tmp_path / "invoices", ["08-credit-note.pdf"]), extract)
    assert rows["08-credit-note.pdf"]["Flags"] == (
        "Credit note: CN-0112 for -$172.50. The bill it reduces was not found in past_invoices.csv "
        "(reference: Matai Centre). Do not pay it.")


@pytest.mark.parametrize("file", ["01-clean.pdf", "11-sole-trader.pdf", "18-exactly-1000.pdf"])
def test_clean_invoices_look_fine(all_rows, file):
    assert all_rows[file]["Status"] == KEY.loc[file, "expected_status"] == "Looks fine"
    assert all_rows[file]["Flags"] is None


@pytest.mark.parametrize("file", list(KEY.index))
def test_every_invoice_gets_the_answer_key_flags_apart_from_property_ones(all_rows, file):
    expected = [f for f in expected_labels(file) if f not in TICKET_04]
    assert sorted(labels(all_rows[file])) == sorted(expected), all_rows[file]["Flags"]


def test_missing_work_order_invoice_number_and_bank_account_are_a_note_not_a_flag(tmp_path):
    def extract(pdf):
        out = fake_extract(pdf)
        for field in ("invoice_number", "work_order", "bank_account"):
            out[field]["source_text"] = None
        return out

    row = run_on(copy_invoices(tmp_path / "invoices", ["01-clean.pdf"]), extract)["01-clean.pdf"]
    assert row["Status"] == "Looks fine"
    assert row["Flags"] is None
    assert row["Notes"] == "Not on the invoice (not required): invoice number, work order, bank account."


# Review fixes

@pytest.mark.parametrize("subtotal, gst, total, flags", [
    ("550.00", "82.50", "632.50", ["Maths: line items add up to $450.00 but the subtotal is $550.00."]),
    ("450.00", "67.50", "517.50", []),
])
def test_a_discount_line_on_a_tax_invoice_keeps_its_minus_sign(subtotal, gst, total, flags):
    values, _ = values_of("05-alias.pdf", subtotal=Decimal(subtotal), gst=Decimal(gst), total=Decimal(total))
    items = [("Repaint lobby ceiling", Decimal("500.00")), ("Discount", Decimal("-50.00"))]
    assert checks.check(values, items, RUN_DATE, [])[0] == flags


@pytest.mark.parametrize("label", ["QUOTE", "STATEMENT OF ACCOUNT", "CREDIT NOTE"])
def test_in_run_duplicates_leave_out_documents_that_are_not_bills_or_are_credit_notes(label):
    values, items = values_of("01-clean.pdf")
    other, _ = values_of("01-clean.pdf", document_type=label)
    assert checks.check(values, items, RUN_DATE, [("other.pdf", other)]) == ([], [])


def test_a_label_containing_the_word_credit_is_not_by_itself_a_credit_note():
    values, items = values_of("01-clean.pdf", document_type="Credit card invoice")
    assert checks.check(values, items, RUN_DATE, []) == ([], [])


def test_a_credit_note_is_not_matched_to_its_own_invoice_number():
    values, items = values_of("08-credit-note.pdf", invoice_number="INV-7731", reference="Matai Centre")
    assert checks.check(values, items, RUN_DATE, [])[0] == [
        "Credit note: INV-7731 for -$172.50. The bill it reduces was not found in past_invoices.csv "
        "(reference: Matai Centre). Do not pay it."]


def test_supplier_name_punctuation_is_removed_not_turned_into_a_space():
    assert checks.name_key("Tidewater H.V.A.C. Services Limited") == checks.name_key("Tidewater HVAC Services Limited")


def test_gst_number_with_a_leading_zero_matches_the_8_digit_one_in_suppliers_csv(monkeypatch):
    southbridge = dict(checks.SUPPLIERS[0], gst_number="49-091-850")  # an 8-digit number that passes the check digit
    monkeypatch.setattr(checks, "SUPPLIERS", [southbridge])
    values, items = values_of("01-clean.pdf", gst_number="049-091-850")
    assert checks.check(values, items, RUN_DATE, []) == ([], [])
