#!/usr/bin/env python3
"""Process the whole inbox once and save the results.

    python3 scripts/run_batch.py                    # rules first, AI fills the gaps
    python3 scripts/run_batch.py --no-llm           # rules only, no network
    python3 scripts/run_batch.py --only email_001   # just these emails
    python3 scripts/run_batch.py --second-opinion   # + AI double-checks each mismatch

    python3 scripts/run_batch.py --mode agents      # AI agents read/sort first (needs app/agents.py)

Writes data/results.json (what the dashboard shows) and submission.json (the
organisers' scorer format). `--mode agents` writes results-agents.json and
submission-agents.json instead, so a mode you are still testing can never
overwrite the run you already scored. Score either one with:

    python3 scripts/score.py                        # scores submission.json
    python3 scripts/score.py submission-agents.json
"""
import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app.config import load_env  # noqa: E402

load_env()

from app import llm  # noqa: E402
from app.inbox import Inbox  # noqa: E402
from app.pipeline import process_email, to_submission  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--source", default=str(ROOT / "data"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--mode", choices=("rules", "agents"), default="rules",
                    help="rules: keyword rules decide, AI fills gaps (proven). "
                         "agents: AI reads and sorts first, rules are the fallback.")
    ap.add_argument("--second-opinion", action="store_true",
                    help="after a mismatch is found, ask the AI to check it independently. "
                         "Advisory only — it never changes the submitted answer.")
    args = ap.parse_args()

    suffix = "" if args.mode == "rules" else f"-{args.mode}"
    if args.out is None:
        args.out = str(ROOT / "data" / f"results{suffix}.json")
    sub_path = ROOT / f"submission{suffix}.json"

    process = process_email
    if args.mode == "agents":
        os.environ["PIPELINE_MODE"] = "agents"      # Taabish's agents layer reads this
        try:
            from app import agents                  # noqa: F401
        except ImportError:
            sys.exit("--mode agents needs src/app/agents.py, which isn't in this checkout yet.\n"
                     "Pull the branch that adds it, or run without --mode to use the rules pipeline.")
        process = getattr(agents, "process_email", process_email)

    if Inbox is None:
        from app.inbox import LOAD_ERROR
        sys.exit(f"Could not load data/loader.py ({LOAD_ERROR}). Is the data/ folder present?")
    inbox = Inbox(args.source)
    emails = inbox.emails()
    if args.only:
        emails = [e for e in emails if e["email_id"] in set(args.only)]
    use_llm = not args.no_llm and llm.available()
    if args.mode == "agents" and not use_llm:
        sys.exit("--mode agents needs an AI key. Set DEEPSEEK_API_KEY (or GEMINI_API_KEY) in .env.")
    if args.second_opinion and not use_llm:
        print("note: --second-opinion ignored, no AI key available")
    print(f"{len(emails)} emails · mode: {args.mode} · "
          f"AI: {llm.model_name() + ' (' + llm.provider() + ')' if use_llm else 'off (rules only)'}"
          f"{' · second opinion on' if args.second_opinion and use_llm else ''}")

    out_path = Path(args.out)
    results = json.loads(out_path.read_text(encoding="utf-8")) if (args.only and out_path.exists()) else {}
    t0 = time.time()
    for i, e in enumerate(emails, 1):
        results[e["email_id"]] = process(e, inbox.read_bytes, use_llm=use_llm,
                                          second_opinion=args.second_opinion)
        if i % 50 == 0:
            print(f"  {i}/{len(emails)}  ({time.time() - t0:.0f}s)")

    results = dict(sorted(results.items()))
    out_path.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    sub = {k: to_submission(v) for k, v in results.items()}
    sub_path.write_text(json.dumps(sub, indent=2), encoding="utf-8")

    print(f"done in {time.time() - t0:.1f}s -> {out_path.relative_to(ROOT)}, {sub_path.name}")
    print("categories:", dict(Counter(r["category"] for r in results.values())))
    print("status:    ", dict(Counter(r["status"] for r in results.values())))
    print("decided_by:", dict(Counter(r["decided_by"] for r in results.values())))
    print("review:    ", dict(Counter(r["review_reason"] for r in results.values() if r["review_reason"])))


if __name__ == "__main__":
    main()
