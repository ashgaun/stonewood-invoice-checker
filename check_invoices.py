"""Check contractor invoice PDFs and write review.xlsx, one row per invoice.

Usage: python check_invoices.py invoices/
"""
import re
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from openpyxl import Workbook
from pydantic import BaseModel, ConfigDict, ValidationError
from pypdf import PdfReader


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    source_text: str | None  # exactly as printed on the invoice, None if not there
    confidence: Literal["high", "medium", "low"]


class LineItem(Strict):
    description: Source
    amount: Source


class Extraction(Strict):
    """What the model must return. Values are worked out from source_text by code, never by the model."""
    document_type: Source
    supplier_name: Source
    gst_number: Source
    invoice_number: Source
    invoice_date: Source
    due_date: Source
    buyer_name: Source
    buyer_identifier: Source
    reference: Source
    work_order: Source
    site: Source
    line_items: list[LineItem]
    subtotal: Source
    gst: Source
    total: Source
    bank_account: Source


COLUMNS = [
    "File", "Status", "Flags", "Notes", "Suggested property", "Property reason",
    # Xero bill field order [assumed], with subtotal and GST next to total.
    "Supplier", "Date", "Due date", "Bill reference", "Line items", "Site", "Subtotal", "GST", "Total",
]
VALUE_COLUMNS = {
    "Supplier": "supplier_name", "Date": "invoice_date", "Due date": "due_date", "Bill reference": "invoice_number",
    "Site": "site", "Subtotal": "subtotal", "GST": "gst", "Total": "total",
}


def squash(text):
    """Ignore differences in spaces and line breaks, keep case."""
    return " ".join(text.split())


def parse_amount(text):
    """'$1,179.90' -> Decimal('1179.90'). Negative as printed on a credit note: '-$150.00'."""
    cleaned = re.sub(r"[\s$,]", "", text)
    if not re.fullmatch(r"-?\d+(\.\d{1,2})?", cleaned):
        raise ValueError(f"'{text}' is not an amount")
    return Decimal(cleaned)


def parse_date(text):
    """Day first: '03/04/2026' is 3 April 2026. Also '9 October 2026' and '7 Oct 2026'."""
    for fmt in ("%d/%m/%Y", "%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(squash(text), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"'{text}' is not a valid date")


PARSERS = {"invoice_date": parse_date, "due_date": parse_date, "subtotal": parse_amount, "gst": parse_amount,
           "total": parse_amount}


def pdf_text(pdf):
    return "\n".join(page.extract_text() or "" for page in PdfReader(pdf).pages)


def check_invoice(pdf, extract):
    """One row for one PDF: status, Flags, Notes and the values worked out from verified source text."""
    flags, notes = [], []
    row = {"File": pdf.name, "Flags": flags, "Notes": notes}

    # Each failure below is one Flag and the rest is skipped, so every PDF still gets a row.
    try:
        text = squash(pdf_text(pdf))
    except Exception as e:
        flags.append(f"Unreadable: the PDF could not be opened ({e}).")
        return row
    if not text:
        flags.append("Unreadable: no text in the PDF, it may be a scan.")
        return row
    try:
        raw = extract(pdf)
    except Exception as e:
        error = re.sub(r"sk-[\w*-]+", "[key hidden]", str(e))  # OpenAI auth errors echo part of the key
        flags.append(f"Could not read: the invoice reader failed ({type(e).__name__}: {error}).")
        return row
    try:
        extraction = Extraction.model_validate(raw)
    except ValidationError as e:
        first = e.errors()[0]
        where = ".".join(str(part) for part in first["loc"])
        flags.append(f"Could not read: the invoice reader returned the wrong structure "
                     f"({e.error_count()} problems, first: {where}: {first['msg']}).")
        return row

    def read(name, found, parse=squash):
        label = name.replace("_", " ")
        if found.confidence == "low":
            shown = f"'{found.source_text}'" if found.source_text else "(nothing found)"
            notes.append(f"Low confidence: the reader was unsure about {label} {shown}.")
        if not found.source_text:
            return None
        if squash(found.source_text) not in text:
            flags.append(f"Source text not found: {label} '{found.source_text}' is not in the PDF text.")
            return None
        try:
            return parse(found.source_text)
        except ValueError as e:
            flags.append(f"Could not read: {label} {e}.")
            return None

    values = {name: read(name, getattr(extraction, name), PARSERS.get(name, squash))
              for name in Extraction.model_fields if name != "line_items"}
    items = [(read("line item", i.description), read("line item amount", i.amount, parse_amount))
             for i in extraction.line_items]
    row.update({column: values[name] for column, name in VALUE_COLUMNS.items()})
    row["Line items"] = " | ".join(f"{d or ''} = {'' if a is None else f'${a:,.2f}'}" for d, a in items)
    return row


def write_review(rows, output_path):
    wb = Workbook()
    ws = wb.active
    ws.title = "Review"
    ws.append(COLUMNS)
    for row in rows:
        ws.append([row.get(c) for c in COLUMNS])
    for column in ws.iter_cols(min_row=2):
        for cell in column:
            if isinstance(cell.value, Decimal):
                cell.number_format = "#,##0.00"
            elif isinstance(cell.value, date):
                cell.number_format = "DD/MM/YYYY"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(output_path)


def run(folder, output_path, extract, run_date):
    """Check every PDF in folder and write one row per invoice to output_path."""
    rows = []
    for pdf in sorted(Path(folder).glob("*.pdf")):
        row = check_invoice(pdf, extract)
        row["Status"] = "Needs you" if row["Flags"] else "Looks fine"
        row["Flags"] = "\n".join(row["Flags"]) or None
        row["Notes"] = "\n".join(row["Notes"]) or None
        rows.append(row)
    write_review(rows, output_path)
    return rows


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python check_invoices.py invoices/")
    from extractor import extract
    rows = run(sys.argv[1], "review.xlsx", extract, date.today())
    needs_you = sum(r["Status"] == "Needs you" for r in rows)
    print(f"Wrote review.xlsx: {len(rows)} invoices, {needs_you} Needs you, {len(rows) - needs_you} Looks fine.")
