# CONTEXT.md: Stonewood invoice checker

Read this before every task. If something is not written here, do not guess. Flag it as unknown.
Labels: [brief] = stated in Stonewood's task brief, [confirmed] = checked in official docs, [assumed] = our working assumption, not yet confirmed by Stonewood.

## Problem and user
Stonewood Group is a NZ commercial property company. Its finance administrator processes contractor invoices by hand, about two hours a day [brief], with over a hundred invoices a day at month end [brief]. A normal day is probably lighter than month end [assumed]. She is fast and has said she does not trust software to get it right [brief]. We are building a small checker. It reads invoice PDFs, extracts the key fields, suggests the property, runs checks, and writes one spreadsheet row per invoice for her to review. It is judged on whether she can trust it at a glance. It never acts on its own.

## Glossary
- **ApprovalMax**: approval workflow tool that sits in front of Xero. She keys bills into it.
- **Xero**: the accounting system. ApprovalMax uses Xero's bill fields and data.
- **Bill**: an invoice received from a contractor, as entered in Xero or ApprovalMax.
- **Tracking category**: Xero label used to tag bills (for example by property) and to route approvals.
- **Reference**: free-text field on Xero invoices. Contractors usually put the work order number here [assumed].
- **Work order (WO)**: job number the property company issued to the contractor. Not always present.
- **TSI**: taxable supply information, IRD's name for what a valid tax invoice must show.
- **Statement of account**: a list of a contractor's invoices. Not a bill.
- **Quote / estimate / pro forma**: not a bill and must never be treated as one.
- **Credit note**: reduces an earlier bill. Negative amounts. Must be matched to that bill, not paid.

## How the workflow runs today
1. Contractor invoice arrives as a PDF [assumed] in a shared mailbox [brief]. Layouts differ by contractor [assumed].
2. She opens each one [brief].
3. She keys the details into ApprovalMax by hand [brief].
4. She picks the property [brief], usually from the name on the invoice [assumed]. Slow when a building has more than one name [assumed].
5. She routes it for approval [brief]. Route depends on property and amount [assumed].
6. An approver approves it in ApprovalMax [assumed].
7. She reconciles against Xero [brief]. What this checks is unknown.

## Confirmed facts
**ApprovalMax** [confirmed]
- Bill fields mirror Xero. ApprovalMax cannot add or rename fields. Due date is set from the contact's payment terms.
- Tracking categories sync from Xero and can route approvals. Whether Stonewood codes property this way is unknown.
- ApprovalMax Capture (OCR) exists as a paid add-on. We assume Stonewood does not have it, because she keys invoices by hand.
- Built-in duplicate warning matches supplier + date + amount, or supplier + reference. Our duplicate check overlaps with this.
- After final approval, the bill is pushed to Xero as Awaiting Payment with an audit trail.
- A Public API (OAuth 2.0) can create Xero bill drafts, update them and submit them. No official MCP server was found.

**IRD rules (GST inclusive totals)** [confirmed]
- $200 or less: seller name, date, description, amount.
- Over $200 to $1,000: plus seller GST number, plus either net + GST + gross, or gross with a statement that GST is included.
- Over $1,000: plus buyer name and at least one buyer identifier (address, phone, email, trading name, NZBN or website).
- Invoice number, site address, work order and bank details are NOT legally required. Missing ones are flagged for her, not treated as a compliance failure.
- GST rate is 15%.
- GST numbers are IRD numbers, 8 or 9 digits, with a mod 11 check digit [assumed, not yet checked against an IRD source].

## Fields to extract
document type, supplier name, GST number, invoice number, invoice date, due date, buyer name, buyer identifier, reference, work order, site address or building, line items, subtotal, GST, total, bank account.
- Property usually appears in the Reference field, the first line of the line item description, or a site or job block near the top [assumed].
- Work order usually appears in the Reference field [assumed].
- Every extracted field carries the exact source text from the PDF and a confidence. Code verifies the source text appears in the PDF. If it does not, the field is left blank and flagged.

## Reference files (all invented)
- `properties.csv`: each building and its other names.
- `suppliers.csv`: each known contractor with GST number and bank account.
- `answer_key.csv`: the correct values and expected flags for every test invoice. Written before any run.

## Checks (run in plain code, not by the model)
1. Document type is an invoice. Quotes, estimates, pro formas and statements are flagged, not processed. Credit notes are flagged to match against the earlier bill.
2. Required fields present for the invoice's value band (IRD rules above).
3. Maths: line items add up to the subtotal, subtotal + GST = total, and GST = 15% of subtotal. Rounding tolerance is not yet decided. Keep it configurable.
4. Duplicates: same supplier + invoice number, or same supplier + date + amount.
5. GST number present when required, and passes the IRD check digit.
6. Supplier is on `suppliers.csv`. Unknown suppliers are flagged.
7. Bank account matches the one on `suppliers.csv`. A change is flagged as a possible fraud sign.
8. Date sanity: not in the future, not months old.
9. Buyer details present over $1,000. Flag a bill addressed to the wrong entity.
10. Property match against `properties.csv` including other names. One match = suggest it with the reason. Several matches or none = flag. Never guess.
11. Low AI confidence on any field = flag.

Unusual amounts are not checked, because there is no invoice history to compare against.

Output status per invoice is **Needs you** or **Looks fine**, with a plain-English reason and the numbers for every flag.

## How it runs
`python check_invoices.py invoices/` reads every PDF in the folder and writes `review.xlsx`, one row per invoice.

## Test invoices (all invented data)
| # | Invoice | Planted problem |
|---|---|---|
| 1 | Southbridge Electrical to Harbourline Property Holdings, INV-2147, Kowhai House, WO-30418, total $1,179.90 | None. Clean base case. Use a GST number that passes the check digit, such as 112-345-671 |
| 2 | Wrong GST | GST not 15% of subtotal |
| 3 | Bad totals | Line items do not add up to the subtotal |
| 4 | Duplicate | Same supplier and INV-2147 again |
| 5 | Alias | Kowhai House under another name from `properties.csv` |
| 6 | Changed bank details | Known supplier, different bank account |
| 7 | Over $1,000, no buyer details | Fails the IRD buyer rule |
| 8 | Credit note | Negative amounts referencing an earlier invoice |
| 9 | Quote | Labelled quote, no invoice number |
| 10 | Statement of account | Lists several invoices, not a bill |
| 11 | Sole trader template | No GST number, tests the $200 threshold |
| 12 | Job management style layout | Site and job number near the top, not in Reference |
| 13 | Xero newer layout (optional) | Same fields, different positions |

Scanned PDFs are left out for now and noted for later.

## Decisions made
- AI extracts fields with source text and confidence. All checks run in deterministic code.
- Output is a spreadsheet she can sort by status.
- The checker never writes to ApprovalMax or Xero. If she later trusts it, the next step is creating ApprovalMax drafts through the API that she submits herself.
- Only invented test data is used. No real names, branding or bank numbers.
- The answer key is written before any run. Score by field and by layout, and run twice to check consistency.
- Keep the build small.

## Open questions for Stonewood
1. Is two hours typical every day, or does month end take longer?
2. How is property coded: tracking category, separate Xero orgs, or account codes?
3. Does each building sit in its own company, and which entity should bills be addressed to?
4. What are the approval rules by property and amount?
5. What does her reconciliation against Xero check?
6. Can we confirm they don't subscribe to ApprovalMax Capture?
7. Can we have a sample of real invoices and the list of buildings with their other names?
8. Are they comfortable sending invoice PDFs to an external AI service?
