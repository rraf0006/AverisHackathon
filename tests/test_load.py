"""Bounded throughput checks; these complement robustness tests, not benchmarks."""
import concurrent.futures
import sys
import time
import tracemalloc
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from app import llm  # noqa: E402
from app.classify import classify  # noqa: E402
from app.inbox import Inbox  # noqa: E402
from app.pipeline import process_email  # noqa: E402


@pytest.mark.performance
def test_two_thousand_clear_emails_complete_with_bounded_time_and_memory(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    email = {"email_id": "load", "from": "bot@example.com", "subject": "Automated notification",
             "body": "Automated notification. No action required.", "attachments": []}
    tracemalloc.start()
    started = time.perf_counter()
    results = [process_email({**email, "email_id": f"load-{n}"}, lambda _: b"", use_llm=False)
               for n in range(2_000)]
    elapsed = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert all(r["category"] == "GENERAL" and r["error"] is None for r in results)
    assert elapsed < 15
    assert peak < 128 * 1024 * 1024


@pytest.mark.performance
def test_concurrent_rule_classification_is_deterministic(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    email = {"from": "ops@example.com", "subject": "Check draft BL",
             "body": "Please check the draft BL against the SI.", "attachments": ["si.txt", "bl.txt"]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: classify(email, use_llm=False), range(250)))
    assert {r["category"] for r in results} == {"BL_COMPARISON"}
    assert {r["decided_by"] for r in results} == {"rule"}


@pytest.mark.performance
def test_all_organiser_emails_process_without_one_failure_stopping_the_batch(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: False)
    monkeypatch.setattr(llm, "can_read_pdf", lambda: False)
    inbox = Inbox(str(ROOT / "data"))
    emails = inbox.emails()
    started = time.perf_counter()
    results = [process_email(email, inbox.read_bytes, use_llm=False) for email in emails]
    assert len(results) == 520
    assert all(result["error"] is None for result in results)
    assert time.perf_counter() - started < 30
