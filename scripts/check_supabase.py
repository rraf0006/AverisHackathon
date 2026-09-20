#!/usr/bin/env python3
"""Check the Supabase connection in one command:

    python3 scripts/check_supabase.py

Reads SUPABASE_URL / SUPABASE_KEY from .env, then tells you in plain English
what is wrong (wrong key type, tables not created yet, ...) or confirms a
write + read + delete round trip works. Never prints the key.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import os  # noqa: E402

import requests  # noqa: E402

from app.config import load_env  # noqa: E402

load_env()
url, key = os.environ.get("SUPABASE_URL", "").rstrip("/"), os.environ.get("SUPABASE_KEY", "")
if not url or not key:
    sys.exit("✗ SUPABASE_URL and SUPABASE_KEY are not both set in .env")
if key.startswith("sb_publishable_"):
    sys.exit("✗ That is the PUBLISHABLE key. The app needs the SECRET key (sb_secret_...) or the legacy "
             "service_role key: Supabase → Project Settings → API Keys.")
if not url.startswith("https://") or not url.endswith(".supabase.co"):
    sys.exit(f"✗ SUPABASE_URL should look like https://<project-id>.supabase.co (got {url[:40]!r})")

from app.store import SupabaseStore  # noqa: E402

store = SupabaseStore(url, key)
try:
    store.save_review("__check__", {"action": "confirm", "note": "connection test"})
    got = store.reviews().get("__check__")
    store.save_result("__check__", {"ok": True})
    ok = bool(got) and "__check__" in store.extra_results()
except requests.HTTPError as exc:
    code = exc.response.status_code if exc.response is not None else 0
    body = exc.response.text[:200] if exc.response is not None else ""
    if code == 404 or "PGRST205" in body or "does not exist" in body:
        sys.exit("✗ The tables don't exist yet. Supabase → SQL Editor → paste docs/supabase.sql → Run.")
    if code in (401, 403):
        sys.exit("✗ Supabase rejected the key. Use the SECRET key (sb_secret_...), not the publishable one.")
    sys.exit(f"✗ Supabase error {code}: {body}")
except requests.RequestException as exc:
    sys.exit(f"✗ Could not reach Supabase: {exc}")

# clean up the test rows
for table in ("reviews", "processed"):
    requests.delete(f"{store.base}/{table}?email_id=eq.__check__", headers=store.h, timeout=15)
print("✓ Supabase works: wrote, read back and deleted a test row in both tables." if ok
      else "✗ Wrote OK but could not read the row back.")
