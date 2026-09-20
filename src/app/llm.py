"""LLM access. Our chosen model is DeepSeek (team account, pay-as-you-go,
fractions of a cent per call). Picked by env vars:

  LLM_PROVIDER=deepseek DEEPSEEK_API_KEY=...  (DEEPSEEK_MODEL=deepseek-flash)
                        Text only. If GEMINI_API_KEY is also set, Gemini's free
                        tier reads scanned PDFs (vision) — DeepSeek does the rest.
  LLM_PROVIDER=gemini   GEMINI_API_KEY=...   (Google AI Studio free key, no card)
                        GEMINI_MODEL=gemini-3.6-flash (reads scanned PDFs too)
  LLM_PROVIDER=openai_compat  LLM_BASE_URL=https://api.groq.com/openai/v1
                        LLM_API_KEY=...  LLM_MODEL=llama-3.3-70b-versatile
                        (Groq free tier, OpenRouter free models, or a local
                         Ollama at http://localhost:11434/v1 — all free)

With no key set, available() is False and the pipeline runs rules-only.
Every response is cached on disk (by prompt hash) so re-runs cost no quota.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import threading
import time
from pathlib import Path

import requests

_default_cache = ("/tmp/shipcheck-llm-cache" if os.environ.get("VERCEL")
                  else Path(__file__).resolve().parents[2] / "data" / "llm_cache")
CACHE_DIR = Path(os.environ.get("LLM_CACHE_DIR") or _default_cache)
MIN_INTERVAL = float(os.environ.get("LLM_MIN_INTERVAL", "0.5"))  # set ~4 for free tiers (≈10–15 req/min)
_lock = threading.Lock()
_last_call = 0.0
last_error: str | None = None


DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def provider() -> str | None:
    p = os.environ.get("LLM_PROVIDER", "").strip().lower()
    if p == "deepseek" and os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if not p and os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if p == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    if p == "openai_compat" and os.environ.get("LLM_BASE_URL"):
        return "openai_compat"
    # Asked-for provider has no key? Use whichever key we do have.
    if os.environ.get("DEEPSEEK_API_KEY"):
        return "deepseek"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    return None


def available() -> bool:
    return provider() is not None


def can_read_pdf() -> bool:
    """Scanned PDFs need a vision model: Gemini, used whenever its key is set."""
    return bool(os.environ.get("GEMINI_API_KEY"))


def gemini_model() -> str:
    # Google retires older Gemini names for new keys (2.5-flash now 404s), and the
    # "-latest" alias is the first to return 503 under load. Pin a real model.
    return os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def model_name() -> str:
    if provider() == "deepseek":
        return os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
    if provider() == "gemini":
        return gemini_model()
    return os.environ.get("LLM_MODEL", "llama-3.3-70b-versatile")


# ------------------------------------------------------------------ plumbing

def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha256(key.encode()).hexdigest()[:32]}.json"


def _throttle():
    global _last_call
    with _lock:
        wait = MIN_INTERVAL - (time.time() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.time()


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _call_gemini(prompt: str, pdf_bytes: bytes | None) -> str:
    parts: list[dict] = [{"text": prompt}]
    if pdf_bytes:
        parts.append({"inline_data": {"mime_type": "application/pdf",
                                      "data": base64.b64encode(pdf_bytes).decode()}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model()}:generateContent"
    r = requests.post(url, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=90,
                      json={"contents": [{"role": "user", "parts": parts}],
                            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}})
    r.raise_for_status()
    data = r.json()
    return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])


def _call_openai_compat(prompt: str) -> str:
    """OpenAI-style /chat/completions — DeepSeek, Groq, OpenRouter, Ollama."""
    if provider() == "deepseek":
        base, key = DEEPSEEK_BASE_URL, os.environ["DEEPSEEK_API_KEY"]
    else:
        base, key = os.environ["LLM_BASE_URL"].rstrip("/"), os.environ.get("LLM_API_KEY")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    r = requests.post(f"{base}/chat/completions", headers=headers, timeout=90,
                      json={"model": model_name(), "temperature": 0,
                            "response_format": {"type": "json_object"},
                            "messages": [{"role": "system", "content": "Reply with one valid json object only, no other text."},
                                         {"role": "user", "content": prompt}]})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def ask_json(prompt: str, pdf_bytes: bytes | None = None, retries: int = 3) -> dict | None:
    """Send a prompt, get a dict back (or None). Cached; retries on 429/5xx."""
    global last_error
    prov = provider()
    if pdf_bytes:                      # scans always go to the vision model
        prov = "gemini" if can_read_pdf() else None
    if prov is None:
        return None
    model = gemini_model() if prov == "gemini" else model_name()
    key = f"{prov}|{model}|{prompt}|{hashlib.sha256(pdf_bytes or b'').hexdigest()}"
    cp = _cache_path(key)
    if cp.exists():
        return json.loads(cp.read_text(encoding="utf-8"))
    for attempt in range(retries):
        _throttle()
        try:
            if prov == "gemini":
                text = _call_gemini(prompt, pdf_bytes)
            else:
                text = _call_openai_compat(prompt)
            out = _parse_json(text)
            if out is not None:
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                cp.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
                last_error = None
            return out
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            last_error = f"HTTP {status}: {exc.response.text[:200] if exc.response is not None else exc}"
            if status in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
                continue
            return None
        except Exception as exc:  # network / parsing
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt < retries - 1:
                time.sleep(3)
                continue
            return None
    return None


# ------------------------------------------------------------------ tasks

def classify_email(email: dict, category_help: dict[str, str]) -> dict | None:
    cats = "\n".join(f"- {k}: {v}" for k, v in category_help.items())
    prompt = f"""You triage a shipping-documentation team's inbox. The email may be in any language
(English, Malay, Indonesian, Chinese...). Pick exactly one category:
{cats}

Trust the body over the subject (subjects are often stale or misleading).
Ignore signatures, external-sender warning banners and quoted earlier messages.

Return JSON: {{"category": "<one of the names above>", "confidence": <0..1>, "reason": "<one short sentence in English>"}}

From: {email.get('from', '')}
Subject: {email.get('subject', '')}
Attachments: {', '.join(email.get('attachments', [])) or 'none'}
Body:
{email.get('body', '')[:4000]}"""
    return ask_json(prompt)


EXTRACT_SCHEMA = """{
  "doc_type": "SI" | "BL" | "COMMERCIAL_INVOICE" | "PACKING_LIST" | "CERTIFICATE_OF_ORIGIN" | "OTHER",
  "fields": {
    "shipper":          {"value": "<company name only, no address>" | null, "quote": "<exact text copied from the document>" | null},
    "consignee":        {...same shape...},
    "notify_party":     {...},
    "port_of_loading":  {...},
    "port_of_discharge":{...},
    "container_count":  {"value": <integer total number of containers> | null, "quote": ...},
    "gross_weight_kg":  {"value": <number in kg> | null, "quote": ...}
  },
  "readable": true | false,
  "notes": "<anything unclear, in English>"
}"""


def extract_fields(text: str | None, pdf_bytes: bytes | None = None, hint: str = "") -> dict | None:
    """Map a document to the 7 fields. Labels vary ("Load Port" = port of
    loading, "To the Order of" = consignee...). Use null when a value is
    blank or a placeholder like ???, ____, TBA — never guess."""
    source = "the attached PDF (it may be a scan)" if pdf_bytes else "the document text below"
    prompt = f"""Read {source}. It is a shipping document {hint}.
Extract these 7 fields, matching by meaning, not by exact label
(e.g. "Load Port"/"POL" = port_of_loading, "To the Order of" = consignee,
"Gross Wt (kgs)"/"毛重" = gross_weight_kg, "No. of Containers or Packages" = container_count).
Labels may be in English, Chinese, Malay or Indonesian.
If a value is missing, blank, or a placeholder (???, ____, TBA, TBC), return null — do NOT guess.
For every value, "quote" must be copied exactly from the document.
Return JSON exactly in this shape:
{EXTRACT_SCHEMA}
"""
    if text:
        prompt += f"\n--- DOCUMENT ---\n{text[:8000]}"
    return ask_json(prompt, pdf_bytes=pdf_bytes)


def second_opinion(si_text: str, bl_text: str, mismatches: list[dict]) -> dict | None:
    """Ask the AI to independently check a mismatch the rules already found.

    Advisory only. The answer is shown to the reviewer as a second pair of eyes and
    never changes the category, the status or the comparison — the rules stay in
    charge of the decision. It exists because a confidently wrong rule is otherwise
    never questioned by anything.
    """
    rows = "\n".join(
        f"- {m.get('label') or m.get('field')}: Shipping Instruction says {m.get('si') or '(blank)'!r}, "
        f"draft Bill of Lading says {m.get('bl') or '(blank)'!r}"
        for m in mismatches)
    prompt = f"""You are a second reviewer on a shipping-documentation team. Another system
compared a Shipping Instruction against a draft Bill of Lading and flagged these fields as
NOT matching:
{rows}

Read both documents yourself and say whether you agree these are real differences that a
customer would need to correct. Treat these as the SAME: different spacing or punctuation,
"LTD"/"LIMITED", "L.L.C."/"LLC", upper vs lower case, and the same weight written in
different units. Treat these as DIFFERENT: a different company, a different port, a
different container count or a genuinely different number.

Return JSON: {{"agrees": true|false, "note": "<one short sentence in plain English>", "confidence": <0..1>}}

--- SHIPPING INSTRUCTION ---
{si_text[:6000]}

--- DRAFT BILL OF LADING ---
{bl_text[:6000]}"""
    out = ask_json(prompt)
    if not out or "agrees" not in out:
        return None
    return {"agrees": bool(out.get("agrees")), "note": str(out.get("note") or "").strip(),
            "confidence": float(out.get("confidence") or 0.0), "model": model_name()}


def draft_correction_email(email: dict, mismatches: list[dict]) -> dict | None:
    lines = "\n".join(f"- {m['label']}: SI says '{m['si']}', draft BL says '{m['bl']}'" for m in mismatches)
    prompt = f"""Write a short, polite, plain-English email to the shipping line asking them to
amend the draft Bill of Lading so it matches the Shipping Instruction.
Original request subject: {email.get('subject', '')}
Differences found:
{lines}
Return JSON: {{"subject": "...", "body": "..."}}"""
    return ask_json(prompt)
