"""Checks 1-9 and 11 from CONTEXT.md, in plain code. Property matching is in property_match.py."""
import csv
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

GST_RATE = Decimal("0.15")
GST_TOLERANCE_PER_ITEM = Decimal("0.01")  # Xero rounds GST per line item
MAX_AGE_DAYS = 90


def read_csv(name):
    with open(Path(__file__).parent / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


PAST = [{"supplier_name": p["supplier_name"], "invoice_number": p["invoice_number"],
         "invoice_date": date.fromisoformat(p["invoice_date"]), "total": Decimal(p["total"])}
        for p in read_csv("past_invoices.csv")]
SUPPLIERS = read_csv("suppliers.csv")


def gst_number_valid(text):
    """IRD mod 11 check digit on an 8 or 9 digit number, e.g. '112-345-671'.

    If the primary weights give a check digit of 10, IRD reruns with the secondary weights; 10 again is invalid.
    """
    digits = re.sub(r"\D", "", text)
    if len(digits) not in (8, 9):
        return False
    digits = digits.zfill(9)
    for weights in ((3, 2, 7, 6, 5, 4, 3, 2), (7, 4, 3, 2, 5, 2, 7, 6)):
        check_digit = -sum(int(d) * w for d, w in zip(digits, weights)) % 11  # 11 - remainder, 0 when remainder is 0
        if check_digit != 10:
            return check_digit == int(digits[8])
    return False


def bank_key(text):
    """Digits only, suffix padded to 3: '12-3456-0123456-00' and '123456012345600' -> '1234560123456000'."""
    parts = re.findall(r"\d+", text)
    if len(parts) == 1 and len(parts[0]) == 15:  # run together: bank 2, branch 4, account 7, suffix 2
        parts = [parts[0][:13], parts[0][13:]]
    return "".join(parts[:-1]) + parts[-1].zfill(3) if parts else ""


def name_key(name):
    """Supplier name ignoring case, punctuation and 'Ltd'/'Limited'. Exact otherwise, no fuzzy matching."""
    words = re.sub(r"[^\w\s]", "", name.lower()).split()
    return " ".join(w for w in words if w not in ("ltd", "limited"))


def check(values, items, run_date, others):
    """Flags and Notes for one invoice.

    values: field name -> value worked out from verified source text (str, date or Decimal), None if blank.
    items: [(description or None, amount Decimal or None)] per line item.
    others: [(file name, values)] for every other invoice in this run, for the in-run duplicate check.
    Returns (flags, notes), lists of plain-English strings. Each Flag starts with its fixed label.
    """
    flags, notes = [], []
    kind = kind_of(values)
    if kind == "not a bill":
        return [f"Not a bill: document is labelled {values['document_type']}. Not processed."], []
    if not values["document_type"]:
        flags.append("Missing: document type is blank, so it cannot be confirmed as an invoice.")
    flags += ird_fields(values, items)
    blank = [name for name, value in values.items() if value is None and name not in required_fields(values)]
    if blank:
        notes.append(f"Not on the invoice (not required): {', '.join(LABELS.get(n, n.replace('_', ' ')) for n in blank)}.")
    credit = kind == "credit note"
    flags += maths(values, items, credit)
    if credit:
        flags.append(credit_note(values, items))  # it reduces a bill, so the duplicate check is skipped
    else:
        flags += duplicates(values, others)
    day = values["invoice_date"]
    if day and day > run_date:
        flags.append(f"Future date: invoice date {day:%d/%m/%Y} is after the run date {run_date:%d/%m/%Y}.")
    if day and (run_date - day).days > MAX_AGE_DAYS:
        flags.append(f"Old invoice: invoice date {day:%d/%m/%Y} is {(run_date - day).days} days before the run date "
                     f"{run_date:%d/%m/%Y} (limit {MAX_AGE_DAYS} days).")
    if values["gst_number"] and not gst_number_valid(values["gst_number"]):
        flags.append(f"GST number invalid: {values['gst_number']} fails the IRD check digit.")
    supplier = by_gst(values["gst_number"]) or by_name(values["supplier_name"])
    name = values["supplier_name"]
    if supplier and name and name_key(name) != name_key(supplier["name"]):
        # Also when the name matches no supplier at all: a known GST number under a strange name goes to her.
        flags.append(f"Supplier mismatch: GST number {values['gst_number']} belongs to {supplier['name']} in "
                     f"suppliers.csv, but the invoice is from {name}.")
    gst = values["gst_number"]
    if supplier and gst and gst_number_valid(gst) and not by_gst(gst):  # an invalid one is already flagged (#15)
        flags.append(f"Supplier mismatch: {supplier['name']} has GST number {supplier['gst_number']} in "
                     f"suppliers.csv, but the invoice shows {gst}.")
    if not supplier and (values["supplier_name"] or values["gst_number"]):
        flags.append(f"Unknown supplier: {values['supplier_name'] or 'no supplier name'} "
                     f"(GST number {values['gst_number'] or 'blank'}) is not in suppliers.csv.")
    if supplier and values["bank_account"] and bank_key(values["bank_account"]) != bank_key(supplier["bank_account"]):
        flags.append(f"Bank account changed: invoice says {values['bank_account']} but suppliers.csv has "
                     f"{supplier['bank_account']} for {supplier['name']}. Possible fraud, check with the supplier.")
    return flags, notes


LABELS = {"gst_number": "GST number", "gst": "GST"}


def required_fields(values):
    """Fields whose blank is a Flag: IRD's for the value band, document type, and site (a ticket 04 Flag)."""
    total = None if values["total"] is None else abs(values["total"])
    required = {"document_type", "supplier_name", "invoice_date", "total", "site"}
    if total is not None and total > 200:
        required |= {"gst_number", "subtotal", "gst"}
    if total is not None and total > 1000:
        required |= {"buyer_name", "buyer_identifier"}
    return required


def ird_fields(values, items):
    """Check 2: what IRD requires for the invoice's value band (GST-inclusive total)."""
    total = None if values["total"] is None else abs(values["total"])
    required = {"supplier name": values["supplier_name"], "invoice date": values["invoice_date"],
                "line item description": next((d for d, _ in items if d), None), "total": total}
    missing = [f"{field} (required on every tax invoice)" for field, value in required.items() if value is None]
    if total is not None and total > 200:
        if not values["gst_number"]:
            missing.append("GST number (required over $200)")
        if values["subtotal"] is None or values["gst"] is None:
            # A printed "GST included" statement would also do, but it is not extracted, so she checks it.
            missing.append("subtotal and GST, or a statement that GST is included (required over $200)")
    if total is not None and total > 1000:
        missing += [f"{field} (required over $1,000)" for field in ("buyer name", "buyer identifier")
                    if not values[field.replace(" ", "_")]]
    if not missing:
        return []
    return [f"Missing for IRD: {', '.join(missing)}. Total is {money(total) if total is not None else 'blank'}."]


def by_gst(gst_number):
    digits = re.sub(r"\D", "", gst_number or "").zfill(9)
    return next((s for s in SUPPLIERS if gst_number and re.sub(r"\D", "", s["gst_number"]).zfill(9) == digits), None)


def by_name(name):
    return next((s for s in SUPPLIERS if name and name_key(s["name"]) == name_key(name)), None)


def kind_of(values):
    """Check 1: 'not a bill', 'credit note' or 'bill'. A blank document type is processed as a bill (and flagged)."""
    label = (values["document_type"] or "").lower()
    if re.search(r"quot(e|ation)|estimate|pro\W*forma|statement|draft", label) or (label and not re.search(r"invoice|credit note", label)):
        return "not a bill"
    if "credit note" in label or (values["total"] is not None and values["total"] < 0):
        return "credit note"
    return "bill"


def same_bill(a, b):
    """Check 4: what a and b share if they look like the same bill, else None."""
    if not a["supplier_name"] or not b["supplier_name"] or name_key(a["supplier_name"]) != name_key(b["supplier_name"]):
        return None
    number = lambda bill: re.sub(r"[\s-]", "", bill["invoice_number"] or "")  # 'INV 3288' is 'INV-3288'
    if number(a) and number(a) == number(b):
        return "same supplier and invoice number"
    if a["invoice_date"] and a["total"] is not None and (a["invoice_date"], a["total"]) == (b["invoice_date"], b["total"]):
        return "same supplier, date and amount"
    return None


def credit_note(values, items):
    """Check 1: point to the bill in past_invoices.csv that this credit note reduces, or say it was not found."""
    printed = " ".join([v for k, v in values.items() if isinstance(v, str) and k != "invoice_number"]  # not its own
                       + [d for d, _ in items if d])
    found = [p for p in PAST if values["supplier_name"] and name_key(p["supplier_name"]) == name_key(values["supplier_name"])
             and re.search(rf"\b{re.escape(p['invoice_number'])}\b", printed)]
    this = f"{values['invoice_number'] or 'no number'} for {money(values['total']) if values['total'] is not None else 'no total'}"
    if not found:
        return (f"Credit note: {this}. The bill it reduces was not found in past_invoices.csv "
                f"(reference: {values['reference'] or 'blank'}). Do not pay it.")
    return (f"Credit note: {this} reduces {', '.join(describe(p) for p in found)} in past_invoices.csv. "
            f"Match it to that bill, do not pay it.")


def describe(bill):
    shown = [bill["invoice_number"] or "no invoice number",
             f"{bill['invoice_date']:%d/%m/%Y}" if bill["invoice_date"] else "no date",
             money(bill["total"]) if bill["total"] is not None else "no total"]
    return f"{bill['supplier_name']} {', '.join(shown)}"


def duplicates(values, others):
    flags = [f"Duplicate: {why} as {describe(p)} already in past_invoices.csv."
             for p in PAST if (why := same_bill(values, p))]
    return flags + [f"Duplicate: {why} as {file} ({describe(other)}) in this run."
                    for file, other in others if kind_of(other) == "bill" and (why := same_bill(values, other))]


def money(amount):
    return f"{'-' if amount < 0 else ''}${abs(amount):,.2f}"


def maths(values, items, credit):
    """Check 3. A credit note's amounts are compared without their sign, so it is checked the same way."""
    flags = []
    sign = abs if credit else (lambda v: v)
    subtotal, gst, total = (None if v is None else sign(v) for v in (values["subtotal"], values["gst"], values["total"]))
    amounts = [None if a is None else sign(a) for _, a in items]
    if None in amounts:
        flags.append(f"Missing: {amounts.count(None)} of {len(amounts)} line item amounts blank, so the line items "
                     f"cannot be added up.")
    added = sum(a for a in amounts if a is not None)
    if subtotal is None and gst is None:
        # GST-inclusive total only (allowed at $200 or less): line items add up to the total, no GST to check.
        if items and None not in amounts and total is not None and added != total:
            flags.append(f"Maths: line items add up to {money(added)} but the total is {money(total)}.")
        return flags
    if subtotal is None or gst is None:
        shown = f"GST {money(gst)}" if subtotal is None else f"subtotal {money(subtotal)}"
        flags.append(f"Missing: {'subtotal' if subtotal is None else 'GST'} blank while {shown} is shown, "
                     f"so the maths cannot be checked.")
        return flags
    if items and None not in amounts and added != subtotal:
        flags.append(f"Maths: line items add up to {money(added)} but the subtotal is {money(subtotal)}.")
    if total is not None and subtotal + gst != total:
        flags.append(f"Maths: subtotal {money(subtotal)} + GST {money(gst)} = {money(subtotal + gst)} "
                     f"but the total is {money(total)}.")
    allowed = GST_TOLERANCE_PER_ITEM * max(len(items), 1)
    if abs(gst - subtotal * GST_RATE) > allowed:
        flags.append(f"Wrong GST: GST is {money(gst)} but 15% of the subtotal {money(subtotal)} is "
                     f"{money(subtotal * GST_RATE)} (allowed difference {money(allowed)}).")
    return flags
