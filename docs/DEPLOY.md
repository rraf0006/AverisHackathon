# 🚀 Deploying (free hosting, no card)

Hosting and database are **free**. The only paid piece is the DeepSeek API the team
already topped up ($1.99 covers thousands of calls; 12 test requests cost < $0.01).

| Piece | Free service | What it does |
|---|---|---|
| Web app (API + dashboard) | **Vercel** (FastAPI preset) | Public link for judges. Deploys from GitHub on every push |
| AI | **DeepSeek API** (`deepseek-chat`, team account) | Unclear emails, unknown labels |
| Scanned PDFs | **Gemini** free tier (`gemini-flash-latest`) | Reads image-only PDFs that DeepSeek can't |
| Database | **Supabase** free project | Saves human reviews + uploaded emails in the cloud |
| Code | GitHub (`Emmapoky/AverisHackathon`) | Repo judges read; Vercel builds from `main` |

> The app also works with **no AI key and no database**: it falls back to rules only and
> saves reviews to a local file. A missing key never breaks the demo.

> **Why not Hugging Face Spaces?** We used it first, but it now pushes you into a paid
> Pro subscription before a Space will run. Vercel's Hobby tier is genuinely free and
> deploys straight from GitHub. `scripts/deploy_hf.py` has been removed; the
> `Dockerfile` stays so Render or any container host still works as a backup.

---

## 1. DeepSeek API key (2 min)
1. Nandhini (account owner): <https://platform.deepseek.com/api_keys> → **Create new API key**.
2. Share it privately with whoever deploys — never in the repo, Discord or WhatsApp.
   Locally: `cp .env.example .env` and paste it into `DEEPSEEK_API_KEY`.
3. In DeepSeek → Usage → **turn on the balance alert** so the key doesn't run dry during
   judging. If it does run out, the app falls back to rules only instead of breaking.
4. Test it: `python3 scripts/run_batch.py --only email_001` → the first line should say
   `AI: deepseek-chat (deepseek)`.

**Scanned PDFs (free):** DeepSeek can't read scans. Get a free Gemini key at
<https://aistudio.google.com/apikey> (no card) and add `GEMINI_API_KEY=...` to `.env`.
Gemini then reads scans only; DeepSeek does everything else.

**If the DeepSeek balance runs out:** remove `DEEPSEEK_API_KEY` and Gemini takes over
everything (set `LLM_MIN_INTERVAL=4` for its rate limit).

## 2. Create the free Supabase database (5 min)
1. <https://supabase.com> → New project (free).
2. SQL editor → paste and run [`supabase.sql`](supabase.sql).
3. Project Settings → API: copy the **Project URL** → `SUPABASE_URL` and the **secret**
   key (`sb_secret_...`, *not* the publishable one) → `SUPABASE_KEY`.
   The key is only used on the server, never sent to the browser.
4. Check it: `python3 scripts/check_supabase.py` → should print a write/read/delete round trip.

**Supabase matters more on Vercel than it did on a normal server.** Vercel functions have
a read-only filesystem and are thrown away between requests, so Supabase is the only thing
that makes human reviews and uploaded-email results survive.

## 3. Pre-compute results (so the demo is instant and uses no AI quota)
```bash
python3 scripts/run_batch.py                  # uses AI only where rules aren't sure
python3 scripts/run_batch.py --second-opinion # + AI double-checks each mismatch, for the demo
python3 scripts/score.py                      # saves the accuracy numbers for the dashboard
```

`--second-opinion` is worth running before judging: it is what puts the "Where the AI
helped" panel and the **✦ AI stepped in** filter to work in the dashboard. It is advisory
only — tests assert the submitted answer is identical with it on or off — but it costs a
DeepSeek call per mismatch (46 on this dataset), so leave it off for quick reruns.
Commit the updated `data/results.json`.

## 4. Deploy to Vercel (5 min, from GitHub)

Vercel runs the **same** FastAPI app — dashboard and API together, one URL. The catch is
that it is *serverless*, not an always-on server:

- The filesystem is **read-only except `/tmp`**, so `api/index.py` points the live upload
  folder and the LLM cache at `/tmp`.
- `/tmp` is wiped between invocations, so anything that must survive goes to **Supabase**.
- Attachments uploaded through "Check an email" are processed in the same request, so the
  check always works; the *"open the attachment"* link afterwards may 404 if the next
  request lands on a different instance. The 520-email inbox is bundled with the deploy,
  so it is unaffected.

**Set it up:** <https://vercel.com/new> → Import `Emmapoky/AverisHackathon`.

| Setting | Value |
|---|---|
| Application Preset | **FastAPI** |
| Root Directory | `./` — the repo root, **not** `src/app` |
| Build / Output Settings | leave untouched |

**Environment variables** — Vercel detects the *names* from `.env.example` but the values
are blank. Fill in:

```
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_KEY=sb_secret_...
APP_NAME=ShipCheck
```

Then press **Deploy**. After the first deploy, every push to `main` redeploys
automatically — there is nothing to run by hand.

`vercel.json` routes every path to `api/index.py` and bundles `data/**` and `src/**` with
the function (~5 MB, the limit is 250 MB).

**Check afterwards:**
- `/health` → `{"ok": true, "emails": 520}`
- `/api/config` → `"ai": true` and `"store": "Supabase (cloud Postgres)"`
- Open the live link in an **incognito window** so you see what judges see.

**Backup host:** Render (<https://render.com>) → New Web Service → from GitHub → Docker,
using the `Dockerfile` in the repo root. Free, but it sleeps after 15 min idle (~50 s to
wake), so Vercel is the better link to hand judges.

## 5. Before submitting
- [ ] Live link loads in incognito, and "Check an email" works
- [ ] `/health` returns `{"ok": true, "emails": 520}`
- [ ] No keys in the repo (`git grep -nE "sk-[a-z0-9]{20}|AIza"` finds nothing)
- [ ] DeepSeek balance alert is on, and the balance is above $1
- [ ] The live link is pasted into `README.md` (it says _TBD_ until you do)
