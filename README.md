# 🚢 ShipCheck: finds Bill of Lading mistakes before they ship

> Averis Hackathon 2026 · Shipping Document Verification
> *(Working name. Change it in one place: `APP_NAME` in `.env`.)*

A shipping team gets **up to 2,000 emails a day** in one inbox. ShipCheck:

1. **Sorts** every email: *Check BL · New SI · Invoice · General · Spam*
2. **Reads** the attachments (txt, PDF, Word, Excel) and finds the 7 key fields
3. **Compares** the draft Bill of Lading against the Shipping Instruction, field by field
4. **Asks a person** when it can't be sure (wrong document, missing file, blank field, unreadable scan), with the reason and the evidence. It never guesses.

A reviewer can confirm or correct any result in one click, and ShipCheck can write the correction email to the shipping line.

👋 **Team: start with [TEAM-GUIDE.md](TEAM-GUIDE.md)** (setup in 10 minutes + who does what).

🚨 **Preliminary deadline: Mon 22 Sep 2026, 12:00 PM.** See [docs/HACKATHON-RULES.md](docs/HACKATHON-RULES.md).

| | |
|---|---|
| Live demo | _TBD (see [docs/DEPLOY.md](docs/DEPLOY.md))_ |
| Demo video (≤ 5 min) | _TBD_ |
| Slides | _TBD_ |

---

## 👥 Team
Erwyna · Nandhini · Charvhi · Riely · Taabish

---

## 📊 Results on the organisers' dataset (520 emails)

| Measure | Score |
|---|---|
| Email sorting accuracy | **100%** (520/520) |
| BL mistakes caught end-to-end (exact fields) | **46 / 46** |
| False alarms | **0** |
| Cases correctly sent to a person | **20 / 20** (wrong doc 5, missing file 5, unreadable 5, blank field 5) |
| Organisers' scorer, final score | **1.000** |
| Handled automatically | 96% (the other 4% go to a person, on purpose) |

Scored with the organisers' own scorer (`scripts/score.py`), using the aggregate numbers only. Rules were written from reading the emails, never from the answer key.

**Generalisation:** the sample data is very templated, so `tests/` checks **new** wording and layouts: Malay and Chinese emails, Malay field labels, `L.L.C.` vs `LLC`, `2x40HC + 1x20GP`, weights in MT, Word/Excel tables. Anything the rules don't recognise is marked "not sure" and handed to the AI (if configured) or to a person.

---

## 🧠 How it works

```
Email ─► ① Sort ──────────────► not a BL check → labelled, done
             (rules → AI if unsure)
         │ BL check
         ▼
        ② Read attachments ──► txt / PDF / Word / Excel parsed; scans → Gemini vision → a person confirms
         ▼
        ③ Find the 7 fields ──► label synonyms (EN / 中文 / BM / ID) → AI for unknown labels
         ▼
        ④ Compare (code, not AI) ─► names, ports, container counts, weights normalised
         ▼
        ✓ Matches   ✗ Doesn't match (which fields, SI vs BL)   ! Needs a person (why)
                                                                   ▼
                                                     Review queue → confirm / correct
```

**Why this design**
- **Rules first, AI where it helps.** Rules are instant, free and explainable. The AI (DeepSeek) handles emails in new wording or other languages, and labels we've never seen. Scanned image PDFs are read by Gemini's free vision model (if its key is set) and then confirmed by a person. Every email records `decided_by: rule | llm`.
- **The AI reads; code compares.** Comparing `21,577` with `21,757`, or `CO., LTD` with `CO LTD`, is maths, not judgement. Code gives the same answer every time and has unit tests.
- **Never guess.** A blank field or an unreadable scan is *not* a mismatch. It goes to a person with the reason.
- **Evidence for every value.** Click any row to see the exact text it came from in each document.

---

## 🧰 Tech stack

| Part | Tech |
|---|---|
| Backend / pipeline | Python 3.12, FastAPI, pypdf, python-docx, openpyxl |
| Dashboard | Plain HTML/CSS/JS served by FastAPI (no build step) |
| AI | **DeepSeek API** (`deepseek-chat`) when rules aren't sure · **Gemini free tier** reads scanned PDFs · both optional, set in `.env` |
| Cloud | Hugging Face Spaces (Docker) + Supabase free Postgres for reviews and uploads, all free tiers |
| Tests | pytest (37 tests) |

---

## 🚀 Run it locally

### Windows PowerShell

After creating `.venv` and installing dependencies, start the dashboard from the project folder:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn app.api:app --app-dir src --port 8000 --reload
```

Open http://localhost:8000. Press Ctrl+C in the terminal to stop the server.
This command does not require activating the environment or changing PowerShell's execution policy.

For a fresh checkout with Python 3.10+ installed:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -X utf8 scripts/run_batch.py --no-llm
.\.venv\Scripts\python.exe -X utf8 -m pytest -q
```

### macOS / Linux / Git Bash

```bash
git clone https://github.com/Emmapoky/AverisHackathon.git
cd AverisHackathon
bash scripts/setup.sh                 # installs everything, processes the emails, runs the tests
bash scripts/start.sh                 # open http://localhost:8000
```

```bash
python3 -m pytest -q                  # tests
python3 scripts/run_batch.py --no-llm # rules only, no network
python3 scripts/score.py              # organisers' scorer (needs _local/scoring-server, see below)
```

**Organisers' scorer (optional):** unzip `sdoc-hackathon-docker.zip` into `_local/scoring-server/`. It's git-ignored because it contains the answer key.

**Deploy for free:** [docs/DEPLOY.md](docs/DEPLOY.md)

---

## 📁 Repo structure

```
├── src/app/
│   ├── classify.py    ① sort emails (rules → AI)
│   ├── parsing.py     ② read txt / pdf / docx / xlsx, detect doc type, catch broken files
│   ├── fields.py      ③ label synonyms + normalising names, ports, counts, weights
│   ├── pipeline.py    ④ compare + decide + escalate; the step-by-step trace
│   ├── llm.py         DeepSeek (or Gemini / any OpenAI-compatible), cached, retries
│   ├── store.py       reviews + uploads: local file or Supabase
│   └── api.py         FastAPI endpoints + serves the dashboard
├── src/static/        dashboard (index.html, app.js, style.css)
├── scripts/           run_batch.py, score.py
├── tests/             37 tests on unseen wording, layouts and languages
├── data/              organisers' synthetic dataset + results.json
└── docs/              brief, rules, decisions, deploy guide
```

## 🗺️ Roadmap
- Connect to the real mailbox (Microsoft Graph / Outlook add-in) instead of JSON files
- Learn from reviewer corrections (new label synonyms, company aliases)
- More languages and document types (packing list ↔ invoice cross-checks)
- Role-based access and an audit export for compliance

---
_Dataset: synthetic data from the hackathon organisers, cleared for public repos._
