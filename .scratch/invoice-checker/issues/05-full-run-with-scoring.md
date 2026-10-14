# 05 — Full run with scoring

**What to build:** the whole folder of 21 test invoices checked in one run, and the live scoring command. `review.xlsx` lists **Needs you** rows first. The scoring command runs the real extractor twice on the test invoices, using the answer key's fixed run date (so #16 stays in the future), and reports:
- the four must-pass criteria from the spec, each pass or fail with the invoices that broke it;
- field accuracy by field and by layout (reported, not required to pass);
- any invoice whose status differed between the two runs.

Not part of `pytest`.

**Blocked by:** 03 — The checks; 04 — Property matching.

**Status:** ready-for-agent

## Tests to write first
Seam 1 (`run` through `review.xlsx`, fake `extract` from the answer key):
- All 21 invoices: status, Flag labels and property match the answer key.
- **Needs you** rows come before **Looks fine** rows.

Scoring (offline, with the fake `extract`):
- Scoring the fake extractor's output gives every must-pass criterion as pass and 100% field accuracy.
- A deliberately wrong extraction (a wrong total, a wrong property) is reported as a failure naming the invoice and field.
- Two runs with different statuses for one invoice are reported as inconsistent.

## Acceptance criteria
- [ ] The full-folder test passes with no network access.
- [ ] The live scoring report, from two real runs, shows all four must-pass criteria met: no Flags on #1, #11, #18; every planted problem flagged; property correct or **Needs you**; same status in both runs.
- [ ] Field accuracy by field and by layout is in the report.
