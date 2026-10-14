"""Regenerate the invented test invoice PDFs in invoices/ from answer_key.csv.

Every printed field value comes from the answer key, so the PDFs and the key cannot drift apart.
The extras below are text the checker does not extract (addresses, statement lines and so on).
"""
import csv
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

ROOT = Path(__file__).parent

# Arial ships with Windows and has the macron in "Kōwhai"; the built-in PDF fonts do not.
pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-Bold", "C:/Windows/Fonts/arialbd.ttf"))

SUPPLIER_ADDRESSES = {
    "Southbridge Electrical Limited": "Unit 4, 22 Harakeke Street, Wellington 6012",
    "Ridgeline Plumbing Limited": "7 Karaka Lane, Porirua 5022",
    "Copperleaf Painting Limited": "31 Tawa Road, Lower Hutt 5010",
    "Tidewater HVAC Services Limited": "150 Wharf Road, Petone 5012",
    "Greystone Glazing Limited": "9 Puriri Place, Upper Hutt 5018",
    "Bellbird Cleaning Limited": "64 Manuka Avenue, Wellington 6021",
    "Fernbrook Handyman Services": "PO Box 812, Paraparaumu 5254",
    "Pohutukawa Landscapes Limited": "18 Kahikatea Drive, Johnsonville 6037",
    "Kauri Point Roofing Limited": "3 Kotukutuku Way, Wellington 6035",
}

EXTRAS = {
    "09-quote.pdf": ["Quote Number: Q-1187", "Valid until: 08/11/2026"],
    "12-job-management.pdf": ["Job No: J-2291"],
}

# Lines on the statement of account (#10): date, invoice, amount
STATEMENT_LINES = [
    ("12/08/2026", "INV-4410", "$345.00"),
    ("02/09/2026", "INV-4466", "$517.50"),
    ("16/09/2026", "INV-4502", "$230.00"),
]


def line_items(row):
    if not row["line_items"]:
        return []
    return [item.rsplit(" = ", 1) for item in row["line_items"].split(" | ")]


class Page:
    def __init__(self, path):
        self.c = Canvas(str(path), invariant=1)  # invariant: same bytes on every run

    def text(self, x, y, s, size=10, bold=False, right=False):
        self.c.setFont("Arial-Bold" if bold else "Arial", size)
        (self.c.drawRightString if right else self.c.drawString)(x, y, s)

    def lines(self, x, y, items, size=10, step=14):
        for s in items:
            self.text(x, y, s, size)
            y -= step
        return y

    def save(self):
        self.c.showPage()
        self.c.save()


def standard(p, row, extras):
    number_label = "Credit Note Number" if row["document_type"] == "CREDIT NOTE" else "Invoice Number"
    p.text(50, 780, row["document_type"], 20, bold=True)
    p.text(350, 780, row["supplier_name"], 11, bold=True)
    supplier = [SUPPLIER_ADDRESSES[row["supplier_name"]]]
    if row["gst_number"]:
        supplier.append(f"GST Number: {row['gst_number']}")
    p.lines(350, 764, supplier, 9)
    if row["buyer_name"]:
        p.lines(50, 730, [row["buyer_name"], row["buyer_identifier"]])
    details = [f"Invoice Date: {row['invoice_date']}"]
    if row["invoice_number"]:
        details.append(f"{number_label}: {row['invoice_number']}")
    details += extras
    if row["reference"]:
        details.append(f"Reference: {row['reference']}")
    if row["due_date"]:
        details.append(f"Due Date: {row['due_date']}")
    p.lines(350, 720, details)
    y = item_table(p, 600, line_items(row), "Description", "Amount NZD")
    totals(p, y, [("Subtotal", row["subtotal"]), ("Total GST 15%", row["gst"]), ("TOTAL NZD", row["total"])])
    if row["bank_account"]:
        p.text(50, 120, f"Payment by direct credit to: {row['bank_account']}")


def sole_trader(p, row, extras):
    p.text(50, 780, row["supplier_name"], 16, bold=True)
    p.lines(50, 762, [SUPPLIER_ADDRESSES[row["supplier_name"]]] + extras, 9)
    p.text(50, 710, row["document_type"], 14, bold=True)
    p.lines(50, 690, [f"Invoice no. {row['invoice_number']}", f"Date: {row['invoice_date']}"])
    p.text(300, 690, "Bill to:", bold=True)
    p.lines(300, 676, [row["buyer_name"], row["buyer_identifier"]])
    y = item_table(p, 620, line_items(row), "Work done", "Amount")
    p.text(350, y - 10, "Total (GST inclusive):", bold=True)
    p.text(545, y - 10, row["total"], bold=True, right=True)
    p.text(50, 120, f"Please pay within 7 days to {row['bank_account']}. Thank you!")


def job_management(p, row, extras):
    p.text(50, 790, row["supplier_name"], 14, bold=True)
    p.lines(50, 775, [SUPPLIER_ADDRESSES[row["supplier_name"]], f"GST No. {row['gst_number']}"], 9)
    p.text(545, 790, row["document_type"], 16, bold=True, right=True)
    p.text(50, 735, "JOB DETAILS", 9, bold=True)
    p.lines(50, 720, [f"Site: {row['site']}"] + extras + [f"Order No: {row['work_order']}"])
    p.text(300, 735, "CUSTOMER", 9, bold=True)
    p.lines(300, 720, [row["buyer_name"], row["buyer_identifier"]], 9)
    p.lines(300, 680, [
        f"Invoice No: {row['invoice_number']}",
        f"Invoice Date: {row['invoice_date']}",
        f"Payment Due: {row['due_date']}",
    ])
    y = item_table(p, 600, line_items(row), "Work Description", "Line Total")
    totals(p, y, [("Sub Total", row["subtotal"]), ("GST", row["gst"]), ("Total Due", row["total"])])
    p.text(50, 120, f"Bank: {row['bank_account']}")


def xero_newer(p, row, extras):
    p.text(50, 785, row["document_type"], 22, bold=True)
    p.text(545, 785, row["supplier_name"], 11, bold=True, right=True)
    p.text(545, 771, SUPPLIER_ADDRESSES[row["supplier_name"]], 9, right=True)
    for x, label, value in [
        (50, "Invoice number", row["invoice_number"]),
        (180, "Issue date", row["invoice_date"]),
        (290, "Due date", row["due_date"]),
        (400, "Reference", row["reference"]),
    ]:
        p.text(x, 735, label, 8, bold=True)
        p.text(x, 721, value)
    p.text(50, 685, "Bill to", 8, bold=True)
    p.lines(50, 671, [row["buyer_name"], row["buyer_identifier"]])
    p.text(545, 685, "Amount due NZD", 8, bold=True, right=True)
    p.text(545, 669, row["total"], 16, bold=True, right=True)
    y = item_table(p, 600, line_items(row), "Item", "Amount NZD")
    totals(p, y, [("Subtotal", row["subtotal"]), ("GST 15%", row["gst"]), ("Total NZD", row["total"])])
    p.lines(50, 130, [f"GST number {row['gst_number']}", f"Pay by bank transfer to {row['bank_account']}"], 9)


def statement(p, row, extras):
    p.text(50, 780, row["document_type"], 18, bold=True)
    p.text(350, 780, row["supplier_name"], 11, bold=True)
    p.lines(350, 764, [SUPPLIER_ADDRESSES[row["supplier_name"]], f"GST Number: {row['gst_number']}"], 9)
    p.lines(50, 730, [row["buyer_name"], row["buyer_identifier"]])
    p.text(350, 700, f"Statement Date: {row['invoice_date']}")
    p.text(50, 640, "Date", bold=True)
    p.text(150, 640, "Invoice", bold=True)
    p.text(545, 640, "Amount NZD", bold=True, right=True)
    y = 620
    for date, number, amount in STATEMENT_LINES:
        p.text(50, y, date)
        p.text(150, y, number)
        p.text(545, y, amount, right=True)
        y -= 16
    totals(p, y - 10, [("Balance Due", row["total"])])
    p.text(50, 120, f"Please pay the balance to: {row['bank_account']}")


def item_table(p, y, items, description_header, amount_header):
    p.text(50, y, description_header, bold=True)
    p.text(545, y, amount_header, bold=True, right=True)
    y -= 20
    for description, amount in items:
        p.text(50, y, description)
        p.text(545, y, amount, right=True)
        y -= 16
    return y


def totals(p, y, rows):
    for label, value in rows:
        y -= 16
        if value:
            p.text(350, y, label, bold=True)
            p.text(545, y, value, right=True)


LAYOUTS = {
    "standard": standard,
    "sole_trader": sole_trader,
    "job_management": job_management,
    "xero_newer": xero_newer,
    "statement": statement,
}


def main():
    out = ROOT / "invoices"
    with open(ROOT / "answer_key.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            page = Page(out / row["file"])
            LAYOUTS[row["layout"]](page, row, EXTRAS.get(row["file"], []))
            page.save()
            print(f"wrote {row['file']}")


if __name__ == "__main__":
    main()
