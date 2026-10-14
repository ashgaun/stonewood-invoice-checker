# 02 — One invoice end to end

**What to build:** invoice #1 goes from PDF to a **Looks fine** row in `review.xlsx`. This builds the whole path once:
- `run(folder, output_path, extract, run_date)`, which writes `review.xlsx`.
- The single extractor that calls OpenAI and returns each field with source text and confidence. The only place OpenAI is used.
- A fake `extract` for tests, built from the answer key. `pytest` never calls OpenAI.
- The command line `python check_invoices.py invoices/`, passing the real extractor and today's date.
- Validating the extraction's structure, verifying source text against the PDF text, and working out values from source text (exact decimal amounts, day-first dates).
- Every PDF gets a row: no readable text, a failed OpenAI call, or output in the wrong structure each give one Flag and skip the rest.

Columns: status, Flags, Notes, suggested property and reason, then values in Xero bill field order [assumed]: supplier, date, due date, Bill reference, line items, property, total.

**Blocked by:** 01 — Test invoices and answer key.

**Status:** ready-for-agent

## Tests to write first
Seam 1 (`run` through `review.xlsx`, fake `extract`, fixed run date):
- #1 gives one row, **Looks fine**, values match the answer key in Xero field order.
- A field whose source text is not in the PDF is left blank with a `Source text not found:` Flag.
- A PDF with no text gives one `Unreadable:` Flag, and `extract` is not called.
- `extract` raising an error gives one `Could not read:` Flag with the error.
- `extract` returning the wrong structure gives one `Could not read:` Flag.
- A low self-reported confidence gives a Note, and the status stays **Looks fine**.

Seam 2 (helpers):
- Amounts: "$1,179.90" → 1179.90 exact; negative amounts as printed on a credit note.
- Dates: "03/04/2026" → 3 April 2026; written-out dates; an impossible date is rejected, not guessed.

## Acceptance criteria
- [ ] All tests above pass with no network access.
- [ ] The OpenAI call exists in exactly one place.
- [ ] Running the command on a folder containing only #1, with a real API key, gives **Looks fine** (manual check by you).
