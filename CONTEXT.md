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
- **Reference**: free-text field printed on the contractor's invoice PDF. Contractors usually put the work order number here [assumed].
- **Bill reference**: the box labelled "Reference" on a bill in Xero and ApprovalMax. It holds the supplier's invoice number (Xero API field `InvoiceNumber`) [confirmed for Xero]. Not the same as Reference.
- **Work order (WO)**: job number the property company issued to the contractor. Not always present.
- **TSI**: taxable supply information, IRD's name for what a valid tax invoice must show.
- **Statement of account**: a list of a contractor's invoices. Not a bill.
- **Quote / estimate / pro forma**: not a bill and must never be treated as one.
- **Credit note**: reduces an earlier bill. Negative amounts. Must be matched to that bill, not paid.
- **Property**: what she codes a bill to. One row in `properties.csv`. Kowhai House and Kowhai Annex are one property [assumed].
- **Other names**: any name, street address or abbreviation that refers to a property (for example "Kowhai Hse", "12 Totara St"). Listed as data in `properties.csv`, not handled in code.
- **Site text**: what the invoice says about where the work was done. Comes from the Reference, the first line of the line item description, or a site or job block near the top.
- **Flag**: a problem she must look at. Any Flag makes the invoice **Needs you**.
- **Note**: information shown to her that does not change the status (for example a missing work order).

## How the workflow runs today
1. Contractor invoice arrives as a PDF [assumed] in a shared mailbox [brief]. Layouts differ by contractor [assumed]. Moving PDFs from the mailbox into `invoices/` is a manual step, out of scope for now [assumed].
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
- Built-in duplicate warning matches supplier + date + amount, or supplier + reference. That reference is probably the Bill reference [assumed]. Our duplicate check overlaps with this.
- After final approval, the bill is pushed to Xero as Awaiting Payment with an audit trail.
- A Public API (OAuth 2.0) can create Xero bill drafts, update them and submit them. No official MCP server was found.

**IRD rules (GST inclusive totals)** [confirmed]
- $200 or less: seller name, date, description, amount.
- Over $200 to $1,000: plus seller GST number, plus either net + GST + gross, or gross with a statement that GST is included.
- Over $1,000: plus buyer name and at least one buyer identifier (address, phone, email, trading name, NZBN or website).
- Invoice number, site address, work order and bank details are NOT legally required. A missing invoice number, work order or bank account is a Note. Missing site text is a Flag, because she cannot pick the property without it (check 11).
- GST rate is 15%.
- GST numbers are IRD numbers, 8 or 9 digits, with a mod 11 check digit [assumed, not yet checked against an IRD source].
- All Stonewood's contractors are GST-registered [assumed]. There is no rule for unregistered suppliers.

## Fields to extract
document type, supplier name, GST number, invoice number, invoice date, due date, buyer name, buyer identifier, reference, work order, site address or building, line items, subtotal, GST, total, bank account.
- Property usually appears in the Reference field, the first line of the line item description, or a site or job block near the top [assumed].
- Work order usually appears in the Reference field [assumed].
- Every extracted field carries the exact source text from the PDF and a confidence. Code verifies the source text appears in the PDF (ignoring differences in spaces and line breaks, case-sensitive). If it does not, the field is left blank and flagged.
- Code works out each value from its source text (amounts as exact decimals, dates read day first). The model's own version of the value is not used.
- The model's self-reported confidence is not trusted. A low confidence is a Note, never a Flag. Accuracy is measured against `answer_key.csv`.

## Reference files (all invented)
- `properties.csv`: each property, its other names, and the entity bills for it should be addressed to [assumed].
- `suppliers.csv`: each known contractor with GST number and bank account.
- `past_invoices.csv`: invented invoices already processed, used by the duplicate check and to find the bill a credit note reduces. Fixed data. The checker only reads it.
- `answer_key.csv`: the correct values and expected flags for every test invoice. Written before any run.

## Checks (run in plain code, not by the model)
1. Document type is an invoice. Quotes, estimates, pro formas, drafts and statements are flagged, not processed. A credit note is always a Flag pointing to the bill it reduces in `past_invoices.csv`, or saying that bill was not found. Maths checks still run on its amounts, ignoring the minus sign. The duplicate check is skipped.
2. Required fields present for the invoice's value band (IRD rules above).
3. Maths: line items add up to the subtotal and subtotal + GST = total, both exact to the cent. GST = 15% of subtotal within $0.01 per line item, because Xero rounds GST per line. Tolerance is configurable. An invoice of $200 or less that shows only a GST-inclusive total (no subtotal or GST) passes: line items add up to the total, and there is no GST to check (#11).
4. Duplicates: same supplier + invoice number (ignoring spaces and hyphens, so "INV 3288" is "INV-3288"), or same supplier + date + amount. Checked against `past_invoices.csv` and within the run. Within a run, both copies are flagged, each pointing to the other. A resend of a past invoice flags only the new one.
5. GST number present when required, and passes the IRD check digit. A missing required GST number is `Missing for IRD:` (#20). A GST number that fails the check digit is `GST number invalid:`.
6. Supplier is on `suppliers.csv`. Match on GST number first, then on the name ignoring case, punctuation and "Ltd"/"Limited". No fuzzy matching. Unknown suppliers are flagged. A GST number matching one supplier and a name matching another is flagged.
7. Bank account matches the one on `suppliers.csv`, comparing digits only with the suffix padded to 3 digits. A change is flagged as a possible fraud sign, showing both numbers.
8. Date sanity: not after the run date, not more than 90 days before it (configurable). Tests use a fixed run date.
9. Buyer details present over $1,000. Flag a bill whose buyer name does not match the entity of the matched property in `properties.csv`, ignoring case, punctuation and "Ltd"/"Limited" as in check 6. Skipped when no property matched or there is no buyer name (#7, #18).
10. Property match against `properties.csv` including other names. Search only the site text, never the buyer or supplier address. Match whole words, ignoring case, macrons, punctuation and extra spaces. No fuzzy matching. One match = suggest it with the reason. Several matches, places that disagree, or none = flag. Never guess. Site text that names only part of a property name, such as "Kowhai" alone, matches every property whose name contains it as whole words, so it is `Property unclear:`, not `No property:` (#17). Part of a name counts only in the Reference and site block, not in the line item description, where everyday words ("food court", "rimu floorboards") would make clear bills unclear. A site text place that contains the whole buyer address is not matched from: it is `Property unclear:`, because the reader may have taken the buyer's address for the site.
11. Extraction: source text not found in the PDF = Flag. A blank field is a Flag only if IRD requires it for the invoice's value band, or she needs it to enter the bill (supplier, date, total, site text). Any other blank field is a Note. Low self-reported confidence = Note.

Every PDF in the folder gets a row, no matter what. No readable text (for example a scan), a failed OpenAI call, or model output in the wrong structure each give one clear Flag, and the other checks are skipped for that invoice. A crash inside the checks or property matching gives that invoice one `Could not read:` Flag, and the other invoices still get their rows. The no-text case is covered by a pytest test, not a test invoice.

Unusual amounts are not checked, because there is no invoice history to compare against.

Known false Flag: an invoice over $200 that shows only a GST-inclusive total with a "GST included" statement is lawful, but gets `Missing for IRD:`, because that statement is not extracted. Accepted, because erring towards Needs you is right for her.

Output status per invoice is **Needs you** (any Flag) or **Looks fine** (no Flags), with a plain-English reason and the numbers for every Flag and Note.

## How it runs
`python check_invoices.py invoices/` reads every PDF in the folder and writes `review.xlsx`, one row per invoice.

## Test invoices (all invented data)
| # | Invoice | Planted problem |
|---|---|---|
| 1 | Southbridge Electrical to Harbourline Property Holdings, INV-2147, Kowhai House, WO-30418, total $1,179.90 | None. Clean base case. Use a GST number that passes the check digit, such as 112-345-671 |
| 2 | Wrong GST | GST not 15% of subtotal |
| 3 | Bad totals | Line items do not add up to the subtotal |
| 4 | Duplicate | Resend of an invoice already in `past_invoices.csv` (not a copy of #1) |
| 5 | Alias | Kowhai House under another name from `properties.csv` |
| 6 | Changed bank details | Known supplier, different bank account |
| 7 | Over $1,000, no buyer details | Fails the IRD buyer rule |
| 8 | Credit note | Negative amounts referencing an earlier invoice |
| 9 | Quote | Labelled quote, no invoice number |
| 10 | Statement of account | Lists several invoices, not a bill |
| 11 | Sole trader template | None. $180 GST-inclusive, no GST number. Should be Looks fine |
| 12 | Job management style layout | Site and job number near the top, not in Reference |
| 13 | Xero newer layout (optional) | Same fields, different positions |
| 14 | Unknown supplier | Supplier not on `suppliers.csv` |
| 15 | Bad GST number | GST number fails the check digit |
| 16 | Future date | Invoice dated after the run date |
| 17 | Ambiguous property | Site text says only "Kowhai", matching several properties |
| 18 | Exactly $1,000.00, no buyer details | None. Should be Looks fine (buyer rule is over $1,000) |
| 19 | Two problems | Wrong GST and changed bank account. Both Flags shown |
| 20 | Over $200, no GST number | $230 with no GST number. Fails the IRD rule |
| 21 | Wrong entity | Buyer name does not match the matched property's entity |

Scanned PDFs are left out for now and noted for later.

## Decisions made
- AI extracts fields with source text and confidence. All checks run in deterministic code.
- The checker is for catching errors and saving time. Output is a spreadsheet she can sort by status, with extracted values in ApprovalMax field order so she can copy from it. Until Stonewood confirms that order, use Xero's bill field order [assumed]: supplier, date, due date, Bill reference, line items, property, total.
- PDF text is extracted with `pypdf`. Switch to `pdfplumber` only if layout #12 extracts badly.
- The checker never writes to ApprovalMax or Xero. If she later trusts it, the next step is creating ApprovalMax drafts through the API that she submits herself.
- Only invented test data is used. No real names, branding or bank numbers.
- The answer key is written before any run. Score by field and by layout, and run twice to check consistency.
- Must pass: every planted problem is flagged, no Flags on the clean invoices (#1, #11, #18), the property is either correct or sent to Needs you (never wrong), and both runs give the same status for every invoice. Field accuracy is reported, not required to pass.
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
9. Are buildings that share a site (for example Kowhai House and Kowhai Annex) one property or two?
10. Are all contractors GST-registered, or do some unregistered sole traders invoice them?
11. Where does she record the work order in ApprovalMax, if anywhere?
12. In what order do the bill fields appear in her ApprovalMax?
13. How do contractors write a property's street address? A street-address other name matches inside a longer address ("3-5 Nikau St", "12 Totara Street, Christchurch"). Should `properties.csv` carry the city, and how are address ranges written?
