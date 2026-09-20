"""Where results, human reviews and newly uploaded emails live.

- Default: local JSON files in data/ (zero setup).
- Cloud: set SUPABASE_URL + SUPABASE_KEY (free tier, no card) and reviews /
  uploaded emails are stored in Supabase Postgres instead, so they survive
  restarts of the free web host. Create the tables with docs/supabase.sql.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import requests

from .config import ROOT

DATA = ROOT / "data"
_lock = threading.Lock()


class LocalStore:
    kind = "local file"

    def __init__(self):
        self.reviews_path = DATA / "reviews.json"
        self.extra_path = DATA / "processed_extra.json"

    def _read(self, p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

    def _write(self, p: Path, d: dict):
        with _lock:
            p.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")

    def reviews(self) -> dict:
        return self._read(self.reviews_path)

    def save_review(self, email_id: str, review: dict):
        d = self.reviews()
        d[email_id] = review
        self._write(self.reviews_path, d)

    def extra_results(self) -> dict:
        return self._read(self.extra_path)

    def save_result(self, email_id: str, result: dict):
        d = self.extra_results()
        d[email_id] = result
        self._write(self.extra_path, d)


class SupabaseStore:
    kind = "Supabase (cloud Postgres)"

    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/") + "/rest/v1"
        self.h = {"apikey": key, "Content-Type": "application/json"}
        # Legacy keys (service_role) are JWTs and also go in Authorization. New-style
        # keys (sb_secret_...) are not JWTs and must only be sent as `apikey`.
        if key.startswith("eyJ"):
            self.h["Authorization"] = f"Bearer {key}"

    def _get(self, table: str) -> dict:
        r = requests.get(f"{self.base}/{table}?select=email_id,data", headers=self.h, timeout=15)
        r.raise_for_status()
        return {row["email_id"]: row["data"] for row in r.json()}

    def _upsert(self, table: str, email_id: str, data: dict):
        r = requests.post(f"{self.base}/{table}", timeout=15,
                          headers={**self.h, "Prefer": "resolution=merge-duplicates"},
                          json={"email_id": email_id, "data": data,
                                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        r.raise_for_status()

    def reviews(self):
        return self._get("reviews")

    def save_review(self, email_id, review):
        self._upsert("reviews", email_id, review)

    def extra_results(self):
        return self._get("processed")

    def save_result(self, email_id, result):
        self._upsert("processed", email_id, result)


def get_store():
    url, key = os.environ.get("SUPABASE_URL"), os.environ.get("SUPABASE_KEY")
    if url and key:
        return SupabaseStore(url, key)
    return LocalStore()
