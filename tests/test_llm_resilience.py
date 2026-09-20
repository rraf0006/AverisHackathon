"""Fault injection for AI providers, response validation, retries, and caching."""
import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import llm  # noqa: E402
from app.classify import classify  # noqa: E402
from app.pipeline import process_email  # noqa: E402


@pytest.fixture
def configured_llm(monkeypatch, tmp_path):
    cache = tmp_path / "answer.json"
    monkeypatch.setattr(llm, "provider", lambda: "deepseek")
    monkeypatch.setattr(llm, "model_name", lambda: "test-model")
    monkeypatch.setattr(llm, "_cache_path", lambda _: cache)
    monkeypatch.setattr(llm, "MIN_INTERVAL", 0)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    return cache


@pytest.mark.parametrize("raw,expected", [
    ('{"ok": true}', {"ok": True}),
    ('```json\n{"ok": true}\n```', {"ok": True}),
    ('Some prose {"ok": true} afterwards', {"ok": True}),
    ('[1, 2, 3]', None),
    ('{"broken":', None),
])
def test_json_response_parser_accepts_only_complete_objects(raw, expected):
    assert llm._parse_json(raw) == expected


def test_invalid_json_returns_none_and_is_not_cached(configured_llm, monkeypatch):
    monkeypatch.setattr(llm, "_call_openai_compat", lambda _: "not json")
    assert llm.ask_json("prompt") is None
    assert not configured_llm.exists()


def test_cache_hit_avoids_an_external_call(configured_llm, monkeypatch):
    configured_llm.write_text('{"cached": true}', encoding="utf-8")
    monkeypatch.setattr(llm, "_call_openai_compat",
                        lambda _: (_ for _ in ()).throw(AssertionError("network called")))
    assert llm.ask_json("prompt") == {"cached": True}


def test_corrupt_cache_is_replaced_by_a_fresh_response(configured_llm, monkeypatch):
    configured_llm.write_text("half-written {", encoding="utf-8")
    monkeypatch.setattr(llm, "_call_openai_compat", lambda _: '{"fresh": true}')
    assert llm.ask_json("prompt") == {"fresh": True}
    assert json.loads(configured_llm.read_text(encoding="utf-8")) == {"fresh": True}


def _http_error(status):
    response = requests.Response()
    response.status_code = status
    response._content = b"provider error"
    return requests.HTTPError(response=response)


def test_rate_limit_is_retried_then_succeeds(configured_llm, monkeypatch):
    calls = 0

    def call(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_error(429)
        return '{"ok": true}'

    monkeypatch.setattr(llm, "_call_openai_compat", call)
    assert llm.ask_json("prompt") == {"ok": True}
    assert calls == 2


def test_authentication_error_is_not_retried(configured_llm, monkeypatch):
    calls = 0

    def call(_):
        nonlocal calls
        calls += 1
        raise _http_error(401)

    monkeypatch.setattr(llm, "_call_openai_compat", call)
    assert llm.ask_json("prompt") is None and calls == 1


def test_timeout_retries_are_bounded(configured_llm, monkeypatch):
    calls = 0

    def call(_):
        nonlocal calls
        calls += 1
        raise requests.Timeout("slow")

    monkeypatch.setattr(llm, "_call_openai_compat", call)
    assert llm.ask_json("prompt", retries=3) is None and calls == 3


def test_no_provider_returns_without_calling_network(monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: None)
    monkeypatch.setattr(llm, "_call_openai_compat",
                        lambda _: (_ for _ in ()).throw(AssertionError("network called")))
    assert llm.ask_json("prompt") is None


def test_unknown_ai_category_falls_back_to_low_confidence(monkeypatch):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "classify_email", lambda *_: {"category": "DELETE_ALL", "confidence": 1})
    result = classify({"from": "x", "subject": "hello", "body": "unclear", "attachments": []})
    assert result["decided_by"] == "rule_low_confidence"


@pytest.mark.parametrize("given,expected", [("high", 0.7), (2, 1.0), (-1, 0.0), (None, 0.7)])
def test_ai_confidence_is_validated_and_clamped(monkeypatch, given, expected):
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "classify_email",
                        lambda *_: {"category": "GENERAL", "confidence": given, "reason": "test"})
    result = classify({"from": "x", "subject": "hello", "body": "unclear", "attachments": []})
    assert result["confidence"] == expected


def test_malformed_ai_field_schema_escalates_without_crashing(monkeypatch):
    si = b"SHIPPING INSTRUCTION\nUnknown heading: value"
    bl = b"BILL OF LADING (DRAFT)\nUnknown heading: value"
    files = {"si.txt": si, "bl.txt": bl}
    email = {"email_id": "bad-ai", "from": "x", "subject": "Check draft BL",
             "body": "Check draft BL against SI.", "attachments": list(files)}
    monkeypatch.setattr(llm, "available", lambda: True)
    monkeypatch.setattr(llm, "extract_fields", lambda *_args, **_kwargs: {"fields": []})
    result = process_email(email, files.__getitem__, use_llm=True)
    assert result["status"] == "NEEDS_REVIEW"
    assert result["review_reason"] == "missing_value"
    assert result["error"] is None


def test_second_opinion_rejects_string_boolean(monkeypatch):
    monkeypatch.setattr(llm, "ask_json",
                        lambda *_args, **_kwargs: {"agrees": "false", "confidence": "high"})
    assert llm.second_opinion("si", "bl", []) is None


def test_gemini_response_without_candidates_fails_safely(configured_llm, monkeypatch):
    monkeypatch.setattr(llm, "provider", lambda: "gemini")
    monkeypatch.setattr(llm, "can_read_pdf", lambda: True)
    monkeypatch.setattr(llm, "gemini_model", lambda: "test-gemini")

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {}

    monkeypatch.setattr(llm.requests, "post", lambda *_args, **_kwargs: Response())
    assert llm.ask_json("scan", pdf_bytes=b"pdf", retries=2) is None
