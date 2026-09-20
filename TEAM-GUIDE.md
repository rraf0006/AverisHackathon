# 👋 CodePulse Team Guide: read this first

**Team:** Erwyna · Nandhini · Charvhi · Riely · Taabish (leader)
**Project:** ShipCheck (working name): finds Bill of Lading mistakes before they ship
**🚨 Deadline:** Mon 22 Sep 2026, **12:00 PM** (Google Form) · Final pitch Fri 26 Sep, in person, everyone must attend

---

## 1. What we built (30-second version)

A shipping team gets up to 2,000 emails a day. ShipCheck:
1. **Sorts** every email: Check BL / New SI / Invoice / General / Spam
2. **Reads** the attachments (txt, PDF, Word, Excel) and finds 7 key fields
3. **Compares** the draft Bill of Lading against the Shipping Instruction
4. **Asks a person** when it isn't sure, with the reason and the evidence

**It already works:** 100% on the organisers' scorer, 46/46 mistakes caught, 0 false alarms, 100 automated tests passing.
Our job now: **polish, deploy, make slides, record the video.**

---

## 2. Get it running on your laptop (10 minutes)

### You need
- **Python 3.10 or newer**: check with `python3 --version`. If missing, get it from <https://www.python.org/downloads/> (Windows: tick **"Add Python to PATH"** during install).
- **Git**: <https://git-scm.com/downloads> (Windows: this also installs **Git Bash**, which you use for the commands below).
- A code editor: **VS Code** recommended.
- A **GitHub account**. Send your username to Erwyna so you can be added to the repo.

### Steps — **Mac / Linux** (Terminal)
```bash
git clone https://github.com/Emmapoky/AverisHackathon.git
cd AverisHackathon
bash scripts/setup.sh        # one time: installs everything, runs the tests (~1–2 min)
bash scripts/start.sh        # starts the app
```

### Steps — **Windows** (PowerShell, no Git Bash needed)
Open **PowerShell** from the Start menu, then:
```powershell
git clone https://github.com/Emmapoky/AverisHackathon.git
cd AverisHackathon
.\scripts\setup.ps1          # one time: installs everything, runs the tests (~1–2 min)
.\scripts\start.ps1          # starts the app
```
If you get **"running scripts is disabled on this system"**, run this once in the same
window and try again (it only affects that window):
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```
Open **http://localhost:8000** in your browser. Press **Ctrl+C** in the terminal to stop it.

✅ You should see the Inbox with **520 emails sorted** and **46 mistakes caught**.

> **You don't need any API keys to run it.** Without keys the app runs on rules only, which is enough for all 520 sample emails. Keys only add AI for *new* kinds of emails (see section 4).

---

## 3. Who does what

| Person | Prototype | Files you own | Slides & video |
|---|---|---|---|
| **Erwyna** | **Full-stack + integration:** backend and frontend, merges everyone's work, deploys to Vercel, connects Supabase, keeps README current | `src/app/api.py`, `src/app/store.py`, `src/static/*`, `api/index.py`, `vercel.json`, `Dockerfile` | Closes the pitch: roadmap + **live demo** + technical Q&A |
| **Taabish** (leader) | **Agentic AI backend:** the AI prompts that sort emails and read documents, the correction-email writer, making the 4 steps read as "agents" (Sort → Read → Verify → Escalate) | `src/app/llm.py`, AI parts of `src/app/classify.py` (bottom: `classify()`) and `src/app/pipeline.py` (`_fill_with_llm`) | Opens the pitch (title + team) · edits the video · **Submits the Google Form** |
| **Charvhi** | **Malay + Chinese feature:** more field labels and email phrases in both languages, test emails, the "Malay email" demo example. **UI review:** double-checks Erwyna's UI and improves it if needed | `src/app/fields.py` (`FIELD_PATTERNS`), keyword rules at the top of `src/app/classify.py` (`RULES`), language tests in `tests/`, `EXAMPLES` in `src/static/app.js`; reviews `src/static/*` | Speaks on Impact + Challenges · slide images and team photos |
| **Nandhini** | **AI accounts & balance alerts:** owns DeepSeek (replace the leaked key, **turn on the balance alert**, watch spend), creates the Supabase project, runs the AI batch + accuracy score. *Optional:* in-app "AI credit low" indicator | `.env` key handling (sharing keys privately), `scripts/run_batch.py`, `scripts/score.py`, `docs/supabase.sql` | Speaks on Where the AI Helps + Results |
| **Riely** | **Stress-tester:** writes 5–10 new test emails (other wording and languages) and runs them through **Try it**; times the demo flow | New test emails → hand to Charvhi or add to `tests/` | Speaks on Problem, Solution, How it works · **Q&A prep** |

### Your first 3 steps
- **Erwyna:** ① push to GitHub — Vercel redeploys `main` automatically ② add everyone as collaborators ③ share the live link in the group.
- **Taabish:** ① read `src/app/llm.py` and `pipeline.py` ② get a free Gemini key (section 4) so you can test the AI locally ③ draft the video script (section 5).
- **Charvhi:** ① read `FIELD_PATTERNS` in `fields.py` and `RULES` in `classify.py` ② add 5 more Malay and 5 more Chinese labels/phrases + a test for each ③ click through every screen of the app and list UI fixes.
- **Nandhini:** ① DeepSeek → delete the old key, create a new one, send it **privately** to Erwyna ② turn on the balance alert ③ create the Supabase project (`docs/DEPLOY.md` step 2).
- **Riely:** ① run the app, open **Try it**, and paste 5 made-up emails ② note anything it gets wrong ③ start the Q&A list.

---

## 4. API keys (only if you want to test the AI)

| Key | Who | How |
|---|---|---|
| **DeepSeek** (main AI, paid, team account) | Nandhini owns it | Nandhini shares it **privately** with whoever deploys. Don't share it with the whole team |
| **Gemini** (reads scanned PDFs, **free**) | Anyone can get their own | <https://aistudio.google.com/apikey> → Create API key (no card) |

Put keys **only** in the `.env` file in the project folder (it was created by `setup.sh`):
```
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-latest
```
No quotes, no spaces.

🔒 **Key rules:** never paste a key into the chat, Discord, WhatsApp, slides, screenshots or the code. `.env` is never uploaded to GitHub. **If a key leaks, delete it and make a new one.**

---

## 5. Slides & video

### Speaking order (everyone speaks once, in one block; no hand-backs)
| Block | Slides (Canva) | Speaker | Owns the slide content |
|---|---|---|---|
| 1 | Title → Meet Team CodePulse | **Taabish** | Taabish (team photos: Charvhi) |
| 2 | The Inbox Problem → Our Solution → How ShipCheck Works | **Riely** | Riely (architecture checked by Erwyna) |
| 3 | Where the AI Helps → Proven on 520 Emails | **Nandhini** | Nandhini (Malay/Chinese examples: Charvhi) |
| 4 | The Impact → Challenges We Solved | **Charvhi** | Charvhi |
| 5 | Stop BL mistakes before they ship (roadmap) → **live demo** → leads technical Q&A | **Erwyna** | Erwyna |

Full scripts are in each slide's **Notes** in Canva (Presenter View). Each block ends with a one-line hand-over to the next speaker.

### 5-minute video (aim for 4:30; −1 mark for every 30 s over 5:00)
| Time | Content | Who |
|---|---|---|
| 0:00–0:30 | Title + team | Taabish |
| 0:30–1:45 | Problem, solution, how it works | Riely |
| 1:45–2:30 | Where the AI helps + accuracy results | Nandhini |
| 2:30–3:10 | Impact + challenges | Charvhi |
| 3:10–4:30 | Roadmap + **live demo** (inbox → mismatch → evidence → review queue → Malay email → correction email) | Erwyna |

Upload as **YouTube unlisted** (not private) or Google Drive "anyone with the link".

---

## 6. Timeline

| When | Milestone |
|---|---|
| **Fri 19 (tonight)** | Everyone runs the app locally · Nandhini replaces the DeepSeek key · Erwyna deploys + pushes to GitHub · Charvhi sets up the slide template |
| **Sat 20** (+ Workshop 1) | Branches merged by evening · Riely's test emails → Charvhi · **slide drafts done** |
| **Sun 21** (+ Workshop 2) | UI review done · final deploy · slides finished by afternoon · **record video in the evening** |
| **Mon 22, before 10:00** | Taabish checks every link in incognito → **submit before 12:00** |

---

## 7. How we work in Git (so we don't break each other's code)

```bash
git pull                                  # get the latest before you start
git checkout -b yourname/what-youre-doing # e.g. charvhi/malay-labels
# ... make your changes ...
source .venv/bin/activate                 # Windows Git Bash: source .venv/Scripts/activate
python -m pytest -q                       # all tests must pass
git add -A && git commit -m "Add Malay labels for weight and ports"
git push -u origin yourname/what-youre-doing
```
Then open a **Pull Request** on GitHub. **Erwyna merges and redeploys.**
Charvhi and Taabish both touch `classify.py` (Charvhi: `RULES` at the top, Taabish: `classify()` at the bottom), so merge Charvhi's first.

---

## 8. Project map

```
src/app/classify.py   ① Sort: keyword RULES → AI if unsure
src/app/parsing.py    ② Read: txt / pdf / docx / xlsx, detect wrong or broken files
src/app/fields.py     ③ Field labels (EN / 中文 / BM / ID) + normalising names, ports, numbers
src/app/pipeline.py   ④ Compare, decide, escalate, plus the step-by-step trace
src/app/llm.py        AI: DeepSeek (text) + Gemini (scans), cached
src/app/api.py        Web API + serves the dashboard
src/app/store.py      Saves reviews: local file or Supabase
src/static/           Dashboard (index.html, app.js, style.css)
scripts/              setup.sh/.ps1, start.sh/.ps1, run_batch.py, score.py, check_supabase.py
tests/                100 tests: run with  python -m pytest -q
data/                 The organisers' 520 emails + attachments + results.json
docs/                 Brief, rules, decisions, DEPLOY.md
```

---

## 9. Handy commands

| I want to… | Run |
|---|---|
| Start the app | Mac: `bash scripts/start.sh` · Windows: `.\scripts\start.ps1` → <http://localhost:8000> |
| Re-process all emails after changing rules | `python scripts/run_batch.py` (add `--no-llm` to skip AI) |
| Run the tests | `python -m pytest -q` |
| Check accuracy with the organisers' scorer | Unzip `sdoc-hackathon-docker.zip` (Google Drive) into `_local/scoring-server/`, then `python scripts/score.py` |
| Deploy the live site (Erwyna) | `git push` — Vercel rebuilds `main` by itself |

(Activate the environment first in each new terminal: `source .venv/bin/activate` on Mac/Linux,
or `.\.venv\Scripts\Activate.ps1` in Windows PowerShell. On Windows the command is `python`,
not `python3`.)

---

## 10. If something goes wrong

| Problem | Fix |
|---|---|
| `python3: command not found` | Install Python 3.10+ (Windows: tick "Add Python to PATH") and reopen the terminal |
| `bash: scripts/setup.sh: No such file` | You're not in the project folder: `cd AverisHackathon` |
| Windows: `bash` / `setup.sh` not recognised | Use the PowerShell version instead: `.\scripts\setup.ps1` |
| Windows: "running scripts is disabled on this system" | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then run the script again |
| Windows: `python3` not recognised | On Windows the command is just `python` (or `py -3`) |
| Port 8000 already in use | Mac: `PORT=8001 bash scripts/start.sh` · Windows: `$env:PORT=8001; .\scripts\start.ps1` |
| Tests fail after your change | Read the first failing test name; it says what broke. Ask in the group before pushing |
| App says "Rules only" | That's fine without keys. For AI, add a key to `.env` and restart |
| `git push` rejected | `git pull` first, then push again |

Questions → team group chat. Organiser questions → the hackathon **Discord**.
