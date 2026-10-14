# 03 — The checks

**What to build:** checks 1–9 and 11 from `CONTEXT.md`, everything except property matching. Each Flag starts with its fixed label from ticket 01 and shows the plain-English reason and the numbers (or values) behind it. Missing optional fields are Notes. Tolerances are configurable: GST within $0.01 per line item, date age 90 days.

Includes the helpers: GST number check digit, bank account normalising (digits only, suffix padded to 3), supplier matching (GST number first, then name ignoring case, punctuation and "Ltd"/"Limited", no fuzzy matching).

**Blocked by:** 02 — One invoice end to end. Runs in parallel with 04.

**Status:** ready-for-agent

## Tests to write first
Seam 2 (helpers):
- Check digit: 112-345-671 passes; a valid 8-digit number passes; a changed last digit fails; wrong length fails.
- Bank accounts: "12-3456-0123456-00", "12 3456 0123456 000" and "123456012345600" are the same; a different account is not.
- Supplier names: "Southbridge Electrical Limited" matches "Southbridge Electrical Ltd"; case and punctuation ignored.

Seam 1 (`run` through `review.xlsx`, fake `extract` from the answer key):
- #2, #3, #4, #6, #7, #8, #9, #10, #14, #15, #16, #19, #20 each get exactly the Flag labels the answer key expects, with the numbers in the text.
- #11 and #18 are **Looks fine**. #1 stays **Looks fine**.
- #19 shows both Flags.
- Two copies of one invoice in the same run are both flagged, each naming the other.
- Same supplier + date + amount, different invoice number, is flagged as a duplicate.
- A credit note whose original is not in past invoices says so.
- GST off by exactly the tolerance passes; one cent more is flagged.
- An invoice exactly 90 days old passes; 91 days is flagged.

## Acceptance criteria
- [ ] Every invoice listed above matches the answer key's status and Flag labels.
- [ ] A missing work order, invoice number or bank account is a Note, never a Flag.
- [ ] All tests pass with no network access.
