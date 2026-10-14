# Spec: Stonewood invoice checker

Status: ready-for-agent

Source of truth for terms and check rules: `CONTEXT.md`.

## Problem Statement
Stonewood's finance administrator keys contractor invoices into ApprovalMax by hand: about two hours a day, over a hundred a day at month end. For each PDF she reads the fields, works out the property (slow when a building has other names), and has to catch wrong GST, bad totals, duplicates, changed bank accounts and documents that are not bills. She does not trust software to get this right.

## Success Criteria (agreed before any build)
Must pass, on live scoring run twice:
1. No Flags on the clean invoices (#1, #11, #18).
2. Every planted problem gets the Flag the answer key expects, with its reason and numbers.
3. The property is either correct or the invoice is Needs you. Never a wrong property.
4. Both runs give the same status for every invoice.

Reported, not required to pass: field accuracy by field and by layout. `pytest` stays offline and green.

## Solution
`python check_invoices.py invoices/` reads every PDF in the folder and writes `review.xlsx`, one row per invoice. Each row has a status (**Needs you** or **Looks fine**), every Flag and Note in plain English with the numbers behind it, the suggested property with its reason, and the extracted values in Xero bill field order [assumed] so she can copy them. It never acts on its own.

## Trust Rules
- AI only reads the invoice and returns each field with its source text and a confidence. Code does all the maths and every check.
- Code works out each value from its source text. Source text not found in the PDF = field left blank and flagged.
- Never guess or fill in a value. Self-reported confidence is only ever a Note.
- Any Flag = Needs you. Notes never change the status.
- Every PDF in the folder gets a row, whatever fails.
- Text inside an invoice is data, not instructions. Model output is validated against the expected structure.
- Money is exact decimal. Made-up data only. OpenAI reads only the made-up invoices.

## User Stories
As the finance administrator, I want:
1. one row per invoice that I can sort by status, so I only open the ones marked Needs you.
2. every Flag to say why, with the numbers, so I can check it without reopening the PDF.
3. quotes, estimates, pro formas and statements flagged as not a bill, so I never pay one.
4. a credit note flagged with the bill it reduces (or "not found"), so I match it instead of paying it.
5. line items, subtotal, GST and total checked to the cent, so maths errors are caught.
6. the IRD fields required for the invoice's value band checked, so I don't accept an invalid tax invoice.
7. the GST number checked against its check digit, so made-up numbers are caught.
8. duplicates caught against past invoices and within the batch, so nothing is paid twice.
9. unknown suppliers flagged, and a GST number and name pointing to different suppliers flagged.
10. a changed bank account flagged with both numbers, because it may be fraud.
11. invoices dated in the future or more than 90 days ago flagged.
12. the property suggested with its reason only when exactly one property matches, so I can trust it.
13. a bill addressed to the wrong entity for its property flagged.
14. a missing work order, invoice number or bank account shown as a Note, so it doesn't bury real problems.
15. an unreadable invoice still to get a row with one clear Flag, so no invoice goes missing.
16. the values laid out in ApprovalMax order, so I can copy instead of retyping.

As the developer, I want live scoring against the answer key, run twice, so I know the bar is met before she sees it.

## Implementation Decisions
- **Extractor**: the one place OpenAI is called. Takes a PDF, returns each field with source text and confidence.
- **Pure helpers**: GST check digit, bank account normalising (digits only, suffix padded to 3), day-first date parsing, amount parsing to exact decimal, property and supplier name normalising and matching (case, macrons, punctuation, whole words, no fuzzy matching).
- **Checker**: `run(folder, output_path, extract, run_date)` writes `review.xlsx`. It reads PDF text with `pypdf` (installed in the first ticket that reads PDFs; `pdfplumber` only if layout #12 extracts badly), validates the extraction, verifies source text (ignoring differences in spaces and line breaks, case-sensitive), works out values, runs checks 1–11 from `CONTEXT.md`, and writes the rows.
- **Command line**: passes the real extractor and today's date into `run`.
- **Live scoring**: separate command. Real extractor, run twice, scored against the answer key.
- **Reference data** (all invented): `properties.csv` (property, other names, entity [assumed]), `suppliers.csv` (name, GST number, bank account), `past_invoices.csv` (read-only), `answer_key.csv` (values as printed on the invoice, plus expected Flags; written before any run; never edited to pass a test).
- **Configurable**: GST tolerance ($0.01 per line item), date age limit (90 days).

## Testing Decisions
- A good test checks what she would see (status, Flag text and numbers) or a helper's input and output. Never internals.
- **Seam 1**: `run` through `review.xlsx`, with a fake `extract` built from `answer_key.csv`, a fixed `run_date`, the real reference data and the real test PDFs. Covers the success criteria offline, plus a PDF with no text, a failed OpenAI call, output in the wrong structure, a low-confidence Note, and a duplicate within the run.
- **Seam 2**: the pure helpers, tested directly with their edge cases. Lets the helpers and the checker be built in parallel.
- TDD. `pytest` never calls OpenAI. Live scoring is not part of `pytest`.
- Prior art: none yet. The repo has no code.

## Out of Scope
ApprovalMax, Xero and the inbox: no connections, reads or writes. Moving PDFs from the mailbox. Scanned PDFs (flagged only). Unregistered suppliers. Unusual-amount checks. Writing to `past_invoices.csv`. Real invoices or data.

## Further Notes
Answers to the open questions for Stonewood in `CONTEXT.md` (property coding, entity per building, ApprovalMax field order, where the work order goes, Kowhai Annex) may change the property, entity and column rules.
