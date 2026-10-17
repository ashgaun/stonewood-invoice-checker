# Stonewood invoice checker

Reads contractor invoice PDFs, checks each one against IRD rules and Stonewood's records, and writes `review.xlsx` with one row per invoice marked **Needs you** or **Looks fine**. It never pays, approves or sends anything.

> **AI only reads. Code does every check.**
> OpenAI's only job is to copy text off the invoice. Plain Python code checks that the text is really in the PDF, does all the maths and makes every decision. The AI never decides whether an invoice is fine.

All invoices, suppliers and properties in this repo are made up.

## Why you can trust it

- **AI only reads. Code does every check.** The AI copies text; Python does the maths and makes every decision.
- **Nothing is taken on the AI's word.** Every field it copies is checked against the PDF. If the text is not there, the field is left blank and flagged.
- **It never guesses.** It never fills in a missing value. A blank field that is required gets a Flag.
- **Every Flag shows its working.** Each one says what is wrong and gives the numbers, for example "GST is $80.00 but 15% of the subtotal $600.00 is $90.00".
- **Money is exact to the cent.** Amounts are worked out as exact decimals, never rounded floating-point numbers.
- **It never acts on its own.** It only writes a spreadsheet. It never pays, approves or sends anything, and it is not connected to Xero or ApprovalMax.
- **Invoices can't give it orders.** Text inside an invoice is treated as data, never as instructions, and the AI's answer must match a fixed structure before it is used.
- **Same answer every time.** Live scoring runs every sample twice and requires both runs to give the same status.

## How it works

```
invoice PDFs  ->  AI reads  ->  code checks  ->  review.xlsx
                  (OpenAI)      (plain Python)    Needs you / Looks fine
```

1. **Read the PDF.** `pypdf` pulls the text out of each PDF in the folder.
2. **AI reads.** OpenAI copies each field's exact text off the invoice. That is all it does, and it is the only OpenAI call in the code ([extractor.py](extractor.py)).
3. **Code checks.** Code confirms every copied field really appears in the PDF, then does all the maths and every check: IRD rules, totals and GST, duplicates, GST number, supplier, bank account, dates and property. It uses [suppliers.csv](suppliers.csv), [properties.csv](properties.csv) and [past_invoices.csv](past_invoices.csv).
4. **Write the review.** Any Flag makes the row **Needs you**. Only a row with no Flags is **Looks fine**. Every Flag gives the reason and the numbers behind it.

## Set up (once)

You need Windows with Python 3.12, Git, and an OpenAI API key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys) on an account with billing. Clone into a short folder such as `C:\code`, because long folder paths make `pip install` fail.

```powershell
git clone https://github.com/ashgaun/stonewood-invoice-checker.git
cd stonewood-invoice-checker
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

In Notepad, replace `sk-proj-your-key-here` with your own key and save. Leave the model line as it is:

```
OPENAI_API_KEY=sk-proj-your-key-here
OPENAI_MODEL=gpt-4o-mini
```

`.env` is in `.gitignore`. Never commit it or share the key.

## Run

```powershell
.venv\Scripts\activate
python check_invoices.py invoices/ --open
```

After 1.5 to 2 minutes it prints this and opens `review.xlsx` in Excel:

```
Wrote review.xlsx: 21 invoices, 15 Needs you, 6 Looks fine.
```

That is the right result for the 21 sample invoices. To check other made-up invoices, put the PDFs in a folder and pass that folder instead of `invoices/`.

## Output

| File | Status | Flags | Property |
| --- | --- | --- | --- |
| 19-two-problems.pdf | Needs you | Wrong GST: GST is $80.00 but 15% of the subtotal $600.00 is $90.00 (allowed difference $0.01).<br>Bank account changed: invoice says 99-0177-0987654-000 but suppliers.csv has 99-0103-0345678-002 for Copperleaf Painting Limited. Possible fraud, check with the supplier. | Rimu Plaza |
| 09-quote.pdf | Needs you | Not a bill: document is labelled QUOTE. Not processed. | |
| 01-clean.pdf | Looks fine | | Kowhai House |

The real sheet also has Notes, the reason for the suggested property, and the supplier, dates, invoice number, line items, subtotal, GST and total in Xero bill order, ready to copy.

## How long it takes

| Command | What it does | Time |
| --- | --- | --- |
| `pytest` | 232 offline tests. Free, no key needed | 15 to 25 seconds |
| `python check_invoices.py invoices/` | Checks the 21 sample invoices | 82 seconds to 2 minutes |
| `python score.py invoices/` | Checks the 21 samples twice and scores them against [answer_key.csv](answer_key.csv) | about 3 minutes |

Measured on `gpt-4o-mini`, about 4 to 6 seconds an invoice. The checker's own work takes under a second for all 21. The rest is waiting for OpenAI, one invoice at a time, so runs are slower when OpenAI is busy. The larger `gpt-4o` model also passed every check and took about 62 seconds a run, but costs more per invoice. To use it, set `OPENAI_MODEL=gpt-4o` in `.env`.

## Testing

- **21 sample invoices** in [invoices/](invoices/), each built for one situation: 15 with a planted problem (wrong GST, duplicate, changed bank account, quote, credit note and more) and 6 clean ones. [answer_key.csv](answer_key.csv) says what each must get.
- **232 automated tests** in [tests/](tests/) cover every check, property matching, the spreadsheet and the sample data. They never call OpenAI.
- **Live scoring** with `score.py` reads all 21 twice and must pass four rules: no Flags on clean invoices, every planted problem flagged, property correct or sent to Needs you, and the same status in both runs.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| PowerShell says running scripts is disabled | Run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again |
| `pip install` fails with "No such file or directory" and a hint about long paths | Clone into a shorter folder, delete `.venv`, and install again |
| `No module named ...` | The virtual environment is off. Run `.venv\Scripts\activate` |
| Every row says `Could not read: ... AuthenticationError` | The key in `.env` is wrong or missing, or the file is not named exactly `.env` |
| Every row says `Could not read: ... RateLimitError` or mentions quota | The OpenAI account needs billing set up |
| `PermissionError` on `review.xlsx` | The file is open in Excel. Close it and run again |
| Sample invoices get `Old invoice:`, or invoice 16 is no longer a future date | The checker uses today's date and the samples are dated September to October 2026. `score.py` uses a fixed date and is not affected |

## Get an AI to walk you through it

<details>
<summary>Prompt to paste into Claude Code or ChatGPT</summary>

```
Help me set up and run Stonewood's invoice checker on my Windows PC. Go one step at a time and wait for me to confirm each step worked before moving on. If you can run commands yourself, run them and show me the output.

About the project:
- Repo: https://github.com/ashgaun/stonewood-invoice-checker (Python 3.12, Windows, PowerShell).
- It reads the invoice PDFs in invoices/, sends each one's text to OpenAI to copy out the fields, checks everything in plain Python code, and writes review.xlsx with one row per invoice marked "Needs you" or "Looks fine".
- All the invoices and data in the repo are made up.

Steps:
1. Clone into a short folder such as C:\code (long folder paths make pip install fail):
   git clone https://github.com/ashgaun/stonewood-invoice-checker.git
   cd stonewood-invoice-checker
2. Install:
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
3. Check the install with the offline tests (free, no API key needed):
   pytest
   Expected: 232 passed.
4. Make the settings file:
   copy .env.example .env
   notepad .env
   I will paste my own OpenAI API key into it myself and save. The model line stays OPENAI_MODEL=gpt-4o-mini.
5. Run the checker:
   python check_invoices.py invoices/ --open
   Expected after 1.5 to 2 minutes (the time depends on how fast OpenAI responds): "Wrote review.xlsx: 21 invoices, 15 Needs you, 6 Looks fine." and Excel opens review.xlsx.
6. Optional, to score the results against the answer key (about 3 minutes, calls OpenAI twice per invoice):
   python score.py invoices/
   Expected: PASS on all four "Must pass" lines.

Rules:
- Never ask me to paste my API key into this chat. Never open, read, print or show the contents of .env.
- Do not change any code, answer_key.csv or the sample invoices to make something pass. If a result is different from what is expected above, stop and tell me exactly what you saw.
- Explain any error in plain English and give me the exact command to fix it.

Known problems and fixes:
- PowerShell says running scripts is disabled: run Set-ExecutionPolicy -Scope CurrentUser RemoteSigned, then activate again.
- pip install fails with "No such file or directory" and a hint about long paths: clone into a shorter folder, delete .venv, repeat step 2.
- "No module named ..." errors: the virtual environment is off. Run .venv\Scripts\activate.
- Every row says "Could not read ... AuthenticationError": the key in .env is wrong or missing, or the file is not named exactly .env.
- Every row says "Could not read ... RateLimitError" or mentions quota: the OpenAI account needs billing set up.
- PermissionError on review.xlsx: the file is open in Excel. Close it and run again.
- Sample invoices get "Old invoice" or invoice 16 is no longer a future date: the checker uses today's date and the samples are dated September to October 2026. score.py uses a fixed date and is not affected.
```

</details>

## More

- [CONTEXT.md](CONTEXT.md): glossary, IRD rules, every check, the sample invoices and open questions.
- [CLAUDE.md](CLAUDE.md): the rules the code follows.
