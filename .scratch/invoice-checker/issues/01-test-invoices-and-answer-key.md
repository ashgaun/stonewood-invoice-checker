# 01 — Test invoices and answer key

**What to build:** the invented test data everything else is scored against. 21 invoice PDFs (#1–#21 in `CONTEXT.md`, including #13), a script that regenerates them, and the four reference files: properties (with other names and entity), suppliers (GST number, bank account), past invoices (read-only), and the answer key. The answer key is written before any run and is never edited to make a test pass.

The answer key holds, per invoice: every field value **as printed** on the invoice, the expected status, the expected Flag labels, the expected property (or none), and the layout. It also records the fixed run date the date checks are relative to.

Flags start with a fixed label, and the answer key lists the labels. Use this set so tickets 03 and 04 agree: `Not a bill:`, `Credit note:`, `Missing for IRD:`, `Missing:`, `Maths:`, `Wrong GST:`, `Duplicate:`, `GST number invalid:`, `Unknown supplier:`, `Supplier mismatch:`, `Bank account changed:`, `Future date:`, `Old invoice:`, `Wrong entity:`, `Property unclear:`, `No property:`, `Source text not found:`, `Unreadable:`, `Could not read:`.

Edge cases to plant in the data (so seam 1 tests them without extra fixtures):
- #1 prints its bank account with a 2-digit suffix; suppliers list it with 3.
- #1's buyer address is at another property, so searching the whole page would suggest the wrong one.
- #12 prints "Kōwhai House" with a macron.
- #4 is a resend of an invoice in past invoices. #8 reduces a bill that is in past invoices.

Installs `pypdf` (first ticket that reads PDFs).

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

## Tests to write first
- The answer key has exactly one row per test PDF, and every PDF has a row.
- Every value in the answer key appears in its PDF's text as `pypdf` reads it (ignoring differences in spaces and line breaks).
- Clean invoices (#1, #11, #18) list no Flags. Every other invoice except the layout tests (#12, #13) lists at least one.
- Every Flag label in the answer key is from the fixed set.
- For the clean invoices, the printed line items, subtotal, GST and total add up (catches typos in the answer key itself).
- #1's GST number is 112-345-671 or another number that passes the check digit.

## Acceptance criteria
- [ ] 21 PDFs regenerate from the script, all invented data, no real names, branding or bank numbers.
- [ ] Reference files exist with the columns above, including entity on properties [assumed].
- [ ] All the tests above pass.
- [ ] `pypdf` is installed and added to requirements.
