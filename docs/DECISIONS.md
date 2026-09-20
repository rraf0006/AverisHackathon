# ✅ Decisions: What We're Building & Why

> Each ⭐ question from [BRAINSTORM-QUESTIONS.md](BRAINSTORM-QUESTIONS.md) gets **one recommended decision**, the reasons for it, and a comparison against the alternatives.
> These are recommendations, not orders. If the team disagrees, change the decision and write the new reason in the Decisions Log.
> Team: Erwyna · Nandhini · Charvhi · Riely · Taabish · Deadline **Mon 22 Sep, 12:00 PM**


> ## 🔄 Updated 19 Sep, after building: everything must be **completely FREE**
> | # | Was | Now | Why |
> |---|---|---|---|
> | D1 | BLint | **ShipCheck** (working name; change with `APP_NAME`) | "BLint" too jargony for the judges; pick a final simple name as a team |
> | D8 | Claude API (paid) | **Google Gemini free tier** (AI Studio key, no card), or Groq / Ollama | Must be free. Gemini also reads scanned PDFs. The app still works with **no key** (rules only) |
> | D8 (again) | Gemini free tier | **DeepSeek API (`deepseek-chat`)** | The team bought DeepSeek credit ($1.99 covers thousands of calls; 12 test calls < $0.01). No tight rate limit, so a live demo can't stall the way free tiers can. Only gap: it can't read scanned PDFs, so those go to a person (what the organisers expect anyway). Gemini/Groq stay as free backups in `.env` |
> | D10 | FastAPI + Next.js | **FastAPI + plain HTML/JS dashboard** (no build step) | Built and working now; one container, nothing to learn |
> | D11 | Cloud Run + Vercel + Supabase | **Vercel (FastAPI) + Supabase free** | Cloud Run needs a card. We tried Hugging Face Spaces, but it now requires a paid Pro subscription to run a Space. Vercel's Hobby tier is free and redeploys from GitHub on every push |
>
> **Status:** working prototype in the repo. **100%** on the organisers' scorer, 62 tests pass. See the repo README and `docs/DEPLOY.md`.

---

## 📌 The whole plan in one table

| # | Decision | Our pick |
|---|---|---|
| D1 | Name & pitch | **BLint**, "the spell-checker for Bills of Lading" |
| D2 | Standout angle | **Evidence-backed human review**: every flag shows the exact source text, and reviewer fixes update the report |
| D3 | Architecture | **Agentic pipeline**: 4 specialised AI steps, orchestrated by our code |
| D4 | Classification | **Hybrid**: keyword rules first, LLM for anything uncertain |
| D5 | Extraction | **Parse files to text → LLM extracts fields as JSON with evidence quotes**; vision for scans |
| D6 | Comparison | **Code compares, not the LLM**: deterministic normalisation plus fuzzy name matching |
| D7 | Escalation | **Escalate only on 5 clear triggers**; everything else auto-decides |
| D8 | AI model | **Claude API (Opus 5)** with results cached |
| D9 | Interface | **Web dashboard**: Inbox → Triage → Review Queue |
| D10 | Tech stack | **Python FastAPI backend + Next.js frontend** |
| D11 | Cloud | **Vercel (one FastAPI function: API + dashboard) + Supabase (reviews, uploaded results)** |
| D12 | Roles | 5 lanes (below). Assign names by skill tonight |
| D13 | Scope | Must / Should / Could list (below) |

---

## D1. Name & Pitch

**✅ Decision: "BLint: the spell-checker for Bills of Lading."**
Pitch: *"2,000 emails a day. BLint finds the ones that matter, checks the BL against the SI in seconds, and only asks a human when it genuinely can't be sure."*

**Why:** "Lint" is a term developers know (a tool that catches mistakes before they ship), so judges get it instantly. It's short, and it says both *what* it checks (BL) and *what it does* (catches errors).

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **BLint** | Memorable, explains itself, good for a demo | Non-technical judges may not know "lint" (fix: say "spell-checker" in the tagline) | **Pick** |
| DocCheck AI | Very clear | Generic, forgettable | ❌ |
| ShipShape | Friendly, nautical | Doesn't say what it does | ❌ |
| Manifest | Sounds professional | A manifest is a different shipping document, which would confuse domain experts | ❌ |

---

## D2. Standout Angle (the 30 product/impact points)

**✅ Decision: Evidence-backed human-in-the-loop.** Every flagged field shows the **exact quote from the SI and the BL** it came from, and a confidence level. When BLint escalates, the reviewer sees *why* and can confirm or correct with one click. The report updates, and the correction is logged.

**Why:** The brief and Sergio both kept coming back to *"ask for help instead of guessing."* Most teams will build classify + compare and stop. Showing the evidence is what makes a real ops team **trust** it, which scores on innovation *and* practical value. Multilingual is a cheap bonus on top (the LLM handles it almost for free), not our main story.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Evidence-backed HITL** | Directly answers the brief; builds trust; great demo moment | Needs a decent UI | **Pick** |
| Multilingual support (Malay, Indonesian, Mandarin) | Organizers hinted at it | Nothing in the dataset to prove it; thin as the main story | ➕ Add as a bonus |
| Auto-draft a correction email to the carrier | Closes the loop; clear time saving | Nice-to-have, easy to cut | ➕ Could |
| Learning loop (corrections become new rules) | Impressive "gets smarter" story | Hard to show convincingly in 2.5 days | ➕ Stretch |

---

## D3. Architecture Style

**✅ Decision: An agentic pipeline. Four specialised AI "agents" (Triage → Extractor → Verifier → Escalation), run in a fixed order by our own code.**

**Why:** The organizers welcomed agentic designs, so calling it one gets credit. But **our code controls the order**, so it's predictable, debuggable and fast. A fully autonomous multi-agent system is fun to pitch but unreliable, slow and hard to debug with 2.5 days left.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Agentic pipeline (code orchestrates, LLM per step)** | Reliable, testable, each step is swappable, still "agentic" | Less flashy than autonomous agents | **Pick** |
| One big LLM prompt per email | Fastest to build | Black box; hard to debug; weak on architecture points (15) | ❌ |
| Autonomous multi-agent (agents talking to each other) | Buzzword-rich | Unpredictable, slow, costly, risky to demo live | ❌ |
| No AI (rules only) | Cheap, deterministic | **Breaks the "AI must be meaningful" requirement** | ❌ |

```
Email ─► ① Triage (rules → LLM) ─► BL_COMPARISON? ─► ② Extractor (parse → LLM JSON + quotes)
                                        │                         │
                           other: label & done          ③ Verifier (code: normalise + compare)
                                                                  │
                                              OK / MISMATCH / ④ Escalation ─► Review Queue (human)
```

---

## D4. Classification

**✅ Decision: Hybrid. Keyword and regex rules on the subject and body first; if no rule is confident, the LLM decides. Every email records `decided_by: rule | llm`.**

**Why:** Subject lines are heavily coded (`TO CONFIRM DOCS`, `REQUEST BL DRAFT`, `SI - …`, `BILLING`), so rules will get most emails right instantly and for free. The LLM handles misleading subjects, forwarded threads and other languages. The rule/LLM split is also great for the pitch: *"78% decided instantly by rules, 22% needed AI"* (placeholder numbers until we measure).

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Hybrid (rules → LLM)** | Fast, cheap, explainable, strong on unseen emails | Two systems to maintain | **Pick** |
| LLM only | Simplest code; handles anything | Slower, costs more; can't show a speed story | 🥈 Fallback |
| Rules only | Free, instant | Brittle on unseen or foreign-language emails; weak on "AI" requirement | ❌ |
| Train our own classifier (e.g. fine-tuned BERT) | "We trained a model" story | 500 synthetic emails is too little; overfits; takes too long | ❌ |

---

## D5. Extraction

**✅ Decision: Convert every attachment to text with normal libraries (`pdfplumber`, `python-docx`, `openpyxl`), then have the LLM map it to the 7 fields as strict JSON, including the exact source quote for each field. If a PDF has no text layer, send the page image to the LLM's vision instead.**

**Why:** Converting to text is free and reliable for 95% of files. The LLM mapping step solves the "same field, different label" problem **for labels we've never seen**, which matters because the finals test on unseen data. The quotes power our D2 evidence feature. Also check the email body, because SIs are sometimes pasted in there.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Parse to text → LLM JSON + quotes; vision fallback** | Robust to new labels; gives evidence; cheap | Needs a good prompt and schema | **Pick** |
| Regex and synonym table only | Free, deterministic | Breaks on any unseen label; the finals will have some | 🥈 Use as a fast path and sanity check |
| Send every file to vision | One path for everything | Slower, costs more, worse on clean text files | ❌ |
| OCR (Tesseract) for scans | Offline, free | Extra install; the cloud container gets heavier; poor on tables | ❌ (vision instead) |

---

## D6. Comparison

**✅ Decision: Our code does the comparison, not the LLM.** Normalise both sides first, then compare:
- **Names:** uppercase, strip punctuation and legal suffixes (`CO., LTD` = `CO LTD`), then fuzzy match (≥ 0.92 similarity counts as the same). Compare the **party name**; address differences are shown as a *note*, not a mismatch.
- **Ports:** strip the country and UN/LOCODE, then match (`PORT KLANG (WESTPORT), MALAYSIA (MYPKG)` → `PORT KLANG`).
- **Container count:** add up every `N x 20'/40'…` (`2x40HC + 1x20GP` = 3).
- **Gross weight:** parse the number and convert MT to KG. Only an exact difference is a mismatch.

**Why:** Half the self-score depends on getting the **exact** field list, and false alarms lose points. LLMs sometimes "see" differences that aren't there, or miss 21,577 vs 21,757. Code is 100% consistent and testable. The AI's job is *reading*; judging a match is *math*.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Deterministic code + fuzzy names** | Exact, repeatable, unit-testable, no false alarms from formatting | Must write the normalisers | **Pick** |
| LLM compares | Handles weird cases | Inconsistent; can hallucinate differences; can't be unit-tested | ❌ |
| Exact string match | Trivial | Flags every formatting difference as a mismatch | ❌ |
| Code first, LLM as tie-breaker on borderline names | Best of both | Extra complexity | ➕ Only if time allows |

---

## D7. When to Escalate (NEEDS_REVIEW)

**✅ Decision: Escalate on exactly these 5 triggers. Everything else is decided automatically.**

| Trigger | review_reason | How we detect it |
|---|---|---|
| The "BL" is really an invoice, packing list or certificate of origin | `wrong_doc_type` | The extractor labels the document type |
| Comparison request with only an SI, or with some attachments missing | `missing_attachment` | Attachment count or types |
| 0-byte file, broken PDF, or scan the vision step can't read | `unreadable` | Parse error or empty text |
| A required SI field is `???`, `____`, `TBA` or blank | `missing_value` | Placeholder pattern |
| The extractor isn't confident about a field | `missing_value` (+ note) | Low-confidence flag in the JSON |

**Doc-check request with *no* attachments at all** ("please send the draft BL"): shown in the UI as **"⏳ Waiting for BL"**. For the self-scorer we submit it as `OK`, which matches how the organizers labelled these emails.

**Why:** Clear triggers mean we escalate the right cases and not everything. A tool that escalates everything is useless, and one that never escalates is dangerous.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **5 explicit triggers** | Predictable; each maps to a review_reason; easy to explain | Might miss odd cases | **Pick** |
| Escalate whenever LLM confidence < X | Flexible | LLM confidence scores are poorly calibrated | ❌ on its own |
| Escalate every mismatch for a human to confirm | Safest | Defeats the purpose; judges will ask what the tool saves | ❌ |

---

## D8. AI Model

**✅ Decision: Claude API, model `claude-opus-5`, used for classification (uncertain cases only), extraction (JSON output) and vision on scans. Run the full dataset once, then store the results so the live demo loads instantly and costs nothing.**

**Why:** One strong model that handles text, strict JSON, **vision** and multiple languages, so nothing needs to be stitched together. Estimated cost for a full run of 520 emails: roughly **US$5–10**, and much less since rules handle most classification. Pricing is Opus 5 at $5 per million input tokens and $25 per million output tokens. The organizers said not to worry about budget.

| Option | Price (in / out per 1M tokens) | Pros | Cons | Verdict |
|---|---|---|---|---|
| ⭐ **Claude Opus 5** | $5 / $25 | Most accurate at extraction and JSON; vision; multilingual | Priciest of the three | **Pick** |
| Claude Sonnet 5 | $2 / $10 | Cheaper, still strong | Slightly less careful on messy docs | 🥈 If cost or speed becomes an issue |
| Claude Haiku 4.5 | $1 / $5 | Cheapest, fastest | Weaker on hard extraction | ➕ Could handle classification only |
| Other providers' free tiers | ~$0 | Free | Rate limits could break a live demo; check current terms | ❌ as the main model |
| Self-hosted open model | $0 API | "Our own model" story | Needs a GPU in the cloud; slow; lots of setup | ❌ |

> ⚠️ Someone needs to own the **API key and billing**. Keep the key in `.env` / cloud secrets and **never commit it** to the public repo.

---

## D9. Interface

**✅ Decision: A web dashboard with 3 screens:**
1. **Inbox:** every email with a category badge, status and `decided_by`
2. **Email detail:** SI vs BL side by side, mismatches highlighted in red, evidence quotes, and a **"Draft correction email"** button
3. **Review Queue:** escalated cases showing the reason and **Confirm / Correct** buttons. The fix updates the report.
Plus a small **Stats** panel: category counts, % auto-decided, self-score accuracy, and estimated hours saved.

**Why:** A dashboard matches how an ops team actually works (a queue of work), shows everything at a glance in a 5-minute video, and makes the human-review step visual. The organizers said to justify the choice, and this is ours: *a queue maps to their workflow; a chatbot makes them ask for every email one by one.*

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Web dashboard** | Matches the ops workflow; great for demos; review queue is natural | More frontend work | **Pick** |
| Chat assistant | Trendy; quick to build | Doesn't scale to 2,000 emails/day; review is awkward | ➕ Could add a small "Ask BLint" panel later |
| Outlook add-in mock | Most realistic | Hard to build and host in 2.5 days | 📍 Put it on the Roadmap slide |
| CLI + JSON only | Easy | Scores badly on product/impact; no demo value | ❌ |

---

## D10. Tech Stack

**✅ Decision: Python + FastAPI for the pipeline and API; Next.js (React) + Tailwind/shadcn for the dashboard.**

**Why:** Python has the best PDF, Word and Excel libraries and the Anthropic SDK. FastAPI is quick and documents itself. Next.js deploys to Vercel with one click and looks polished. Splitting frontend and backend also lets 5 people work at once without conflicts, and it scores on architecture.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **FastAPI + Next.js** | Clean split; parallel work; polished; scales | Two codebases | **Pick** |
| Streamlit (all Python) | Fastest to build; one codebase | Looks like a prototype; weaker "architecture" story; clunky review flows | 🥈 **Fallback if no one knows React** |
| Node.js everywhere | One language | Weaker document-parsing libraries | ❌ |
| Gradio | Very fast | Built for ML demos, not ops tools | ❌ |

> ❓ **Check tonight:** does at least one person know React or Next.js? If not, switch to Streamlit. Don't learn React under a 2.5-day deadline.

---

## D11. Cloud (mandatory)

**✅ Decision:**
- **Google Cloud Run** runs the FastAPI pipeline as a Docker container. It scales automatically with inbox volume and has a generous free tier.
- **Vercel** hosts the Next.js dashboard (free, one-click deploys from GitHub).
- **Supabase** (free) provides Postgres for results, review decisions and the audit trail, plus Storage for the SI/BL attachments.
- **Claude API** for the AI.

**Why:** This is *meaningful* cloud, not just "we hosted it": auto-scaling processing, cloud storage for documents, a cloud database for the human-review audit trail, and a cloud AI service. That tells the scalability story for 2,000 emails a day. All of it has free tiers.

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| ⭐ **Cloud Run + Vercel + Supabase** | Real scalability story; free tiers; Docker-based | 3 services to set up (needs a card on Google Cloud, even when free) | **Pick** |
| Render / Railway (one host) | Simplest | Render's free tier **sleeps**, so a judge could wait ~50 s on a cold start; Railway is trial credit only | 🥈 If Google Cloud setup blocks us |
| AWS (Lambda + S3 + DynamoDB) | Most "enterprise" | Slowest to set up; easy to misconfigure | ❌ for 2.5 days |
| Streamlit Community Cloud | Free, easy | Weak "cloud infrastructure" story | Only together with the D10 fallback |

> ⚠️ **Deploy a "hello world" on Saturday**, not Sunday night. The live link must stay up for the whole judging period.

**🔄 What we actually shipped (Sun 20 Sep):** one **Vercel** function serving both the API
and the dashboard, plus **Supabase** for reviews and uploaded-email results. No Cloud Run
(needs a card), no separate Next.js front end (D10 dropped it).

We deployed to **Hugging Face Spaces** first and wrote `scripts/deploy_hf.py` for it, but
HF now gates running a Space behind a paid **Pro** subscription, which breaks the
free-only rule we set in D8. Moved to Vercel and deleted the HF script. The `Dockerfile`
stays so **Render** remains a same-day backup if Vercel misbehaves during judging.

**The Vercel trade-off to know for Q&A:** Vercel is serverless, so the filesystem is
read-only apart from `/tmp` and instances are discarded between requests. That is exactly
why Supabase is load-bearing here rather than a nice-to-have — without it, a reviewer's
decision would vanish on the next click. `api/index.py` redirects the upload folder and
the LLM cache to `/tmp`.

---

## D12. Roles (5 people, 5 lanes)

**✅ Decision: one owner per lane, each with a backup. Match names by skill tonight.**

| Lane | Owns | Best fit | Name |
|---|---|---|---|
| 1. Pipeline & AI lead | Triage (D4), orchestration, LLM prompts, caching | Strongest Python + AI person | |
| 2. Extraction | pdf/docx/xlsx parsing, vision fallback, extraction JSON (D5) | Likes messy data | |
| 3. Verifier & Validation | Normalisers, comparison (D6), escalation (D7), **scoring loop and tests** | Detail-oriented; likes testing | |
| 4. Frontend | Dashboard, review queue, stats panel (D9) | Knows React/Next.js | |
| 5. Cloud, Product & Pitch | Cloud Run, Vercel, Supabase (D11), README, slides, **the 5-min video** | Organised communicator; comfortable with DevOps | |

Team: Erwyna · Nandhini · Charvhi · Riely · Taabish

---

## D13. Scope

| 🟥 Must (by Sat night) | 🟧 Should (Sun) | 🟩 Could (if time) |
|---|---|---|
| Classify all 520 emails | Review queue with Confirm / Correct | Draft correction email to the carrier |
| Extract + compare txt pairs | pdf / docx / xlsx pairs | Multilingual test emails (Malay, Indonesian, Mandarin) |
| Submission JSON + first self-score | Vision on scanned PDFs | "Ask BLint" chat panel |
| Basic dashboard, live on the cloud | Evidence quotes in the UI | Learning loop from corrections |
| README with setup | Stats panel (accuracy, % auto) | Outlook integration mock |

**Cut order if we're behind:** Could → multilingual → vision (scans escalate as `unreadable` instead) → stats panel. **Never cut:** the live link, the video, or the review queue.

---

## 🗓️ Timeline

| When | Milestone |
|---|---|
| **Fri 19 (tonight)** | Agree on these decisions · assign lanes · everyone clones the repo · API key sorted |
| **Sat 20** (+ Workshop 1) | End-to-end on txt pairs · first self-score · hello-world deployed to Cloud Run + Vercel |
| **Sun 21** (+ Workshop 2) | Binary formats + escalation · dashboard + review queue live · slides · **record the video Sunday night** |
| **Mon 22, before 10 AM** | Test the live link in incognito · video set to unlisted · repo public → **submit before 12:00** |

## 📝 Decisions Log (changes after team discussion)

| # | Changed decision | New choice | Why | Date |
|---|---|---|---|---|
| D8 | Claude API (paid) → Gemini free tier | **DeepSeek (`deepseek-chat`)** for text, **Gemini** for scanned PDFs | Team bought DeepSeek credit; no tight rate limit, so a live demo can't stall. Gemini's vision covers the scans DeepSeek can't read | Sat 19 Sep |
| D10 | FastAPI + Next.js | **FastAPI + plain HTML/CSS/JS** | No build step, one deployable, nothing new for the team to learn | Sat 19 Sep |
| D11 | Cloud Run + Vercel + Supabase | **Hugging Face Spaces (Docker) + Supabase** | Cloud Run asks for a card even on the free tier | Sat 19 Sep |
| D11 | Hugging Face Spaces | **Vercel (FastAPI preset) + Supabase** | HF now requires a paid **Pro** subscription to run a Space — breaks our free-only rule. Vercel Hobby is free and redeploys from GitHub on push | Sun 20 Sep |
| D8 | AI only fills gaps the rules missed | **+ an AI second opinion on every mismatch** (`--second-opinion`, advisory) | On the organisers' data the rules decide 520/520, so the AI was invisible and a confidently wrong rule was never questioned. The second opinion is recorded and shown, but never edits the answer — four tests assert the submitted JSON is byte-identical with it on or off | Sun 20 Sep |
| D3 | One pipeline | **`--mode rules` (default) / `--mode agents`**, scored separately | An AI-first pipeline is worth measuring, not assuming. `--mode agents` writes `submission-agents.json`, so a mode still being tested can never overwrite the run that scored 1.000 | Sun 20 Sep |
| D9 | Averis-inspired cream/serif dashboard | **Dark sidebar + orange accent console** | The first pass looked like a copy of the client's own site — unoriginal, and the floating sticky header visibly bounced on scroll. Rebuilt as a fixed dark rail with a flat, static top bar | Sun 20 Sep |
