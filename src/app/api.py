"""FastAPI app: JSON API + the dashboard (static files).

    uvicorn app.api:app --app-dir src --reload      # http://localhost:8000
"""
from __future__ import annotations

import base64
import binascii
import json
import os
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import APP_NAME, ROOT, env, load_env

load_env()

from . import llm  # noqa: E402
from .fields import FIELD_LABELS, FIELDS  # noqa: E402
from .inbox import Inbox  # noqa: E402  (None if data/loader.py isn't deployed)
from .pipeline import process_email, to_submission  # noqa: E402
from .store import get_store  # noqa: E402

DATA = ROOT / "data"
STATIC = ROOT / "src" / "static"
# Serverless hosts have a read-only filesystem apart from /tmp. Vercel sets $VERCEL,
# so we pick a writable default there no matter which entry point it imports.
ON_SERVERLESS = bool(env("VERCEL"))
UPLOADS = Path(env("UPLOADS_DIR")
                or ("/tmp/shipcheck-uploads" if ON_SERVERLESS else DATA / "uploads"))

app = FastAPI(title=f"{APP_NAME} API")


@app.middleware("http")
async def no_cache_static(request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        resp.headers["Cache-Control"] = "no-cache"
    return resp
store = get_store()

# Things that must not take the whole app down when a file is missing from a
# deploy bundle: without these guards a partial upload gives every route an
# opaque 500 with no way to tell what is absent.
BOOT_PROBLEMS: list[str] = []
if Inbox is None:
    BOOT_PROBLEMS.append("data/loader.py is missing, so the organisers' inbox loader is unavailable")
if not (DATA / "results.json").exists():
    BOOT_PROBLEMS.append("data/results.json is missing, so the dashboard has no emails to show")
if not (STATIC / "index.html").exists():
    BOOT_PROBLEMS.append("src/static/ is missing, so the dashboard cannot be served")


def _load_results() -> dict:
    p = DATA / "results.json"
    base = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    try:
        base.update(store.extra_results())
    except Exception as exc:  # cloud store down → still serve the batch results
        print("store unavailable:", exc)
    return base


RESULTS: dict = _load_results()
_results_mtime = (DATA / "results.json").stat().st_mtime if (DATA / "results.json").exists() else 0


def _sync():
    """Pick up a fresh batch run (scripts/run_batch.py) without a restart."""
    global _results_mtime
    p = DATA / "results.json"
    if p.exists() and p.stat().st_mtime != _results_mtime:
        _results_mtime = p.stat().st_mtime
        fresh = json.loads(p.read_text(encoding="utf-8"))
        for k in [k for k in RESULTS if not k.startswith("new_")]:
            RESULTS.pop(k)
        RESULTS.update(fresh)


def _reviews() -> dict:
    try:
        return store.reviews()
    except Exception as exc:
        print("store unavailable:", exc)
        return {}


def _effective(res: dict, review: dict | None) -> dict:
    """The system's answer, overridden by a person's correction if there is one."""
    out = dict(res)
    out["system"] = {k: res.get(k) for k in ("category", "status", "defect_fields", "review_reason")}
    out["review"] = review
    if review and review.get("action") == "correct":
        for k in ("category", "status", "defect_fields"):
            if review.get(k) is not None:
                out[k] = review[k]
        out["has_defect"] = out.get("status") == "MISMATCH"
        if out.get("status") != "NEEDS_REVIEW":
            out["review_reason"] = None
    return out


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return path != root
    except ValueError:
        return False


def _content_path(path: str) -> tuple[Path, Path]:
    """Resolve a stored relative path against data or the separate upload root."""
    rel = Path(path)
    if not rel.is_absolute() and rel.parts and rel.parts[0].casefold() == "uploads":
        root = UPLOADS.resolve()
        return (root.joinpath(*rel.parts[1:]).resolve(), root)
    root = DATA.resolve()
    return ((root / rel).resolve(), root)


def _read_bytes(path: str) -> bytes:
    p, root = _content_path(path)
    if not _is_within(p, root):
        raise HTTPException(400, "bad path")
    return p.read_bytes()


def _row(r: dict) -> dict:
    return {k: r.get(k) for k in ("email_id", "from", "subject", "category", "status", "decided_by",
                                   "review_reason", "defect_fields", "class_confidence")} | \
        {"n_attachments": len(r.get("attachments", [])), "reviewed": bool(r.get("review")),
         "uploaded": r["email_id"].startswith("new_"), "ai": bool(r.get("ai_used")),
         "second_opinion": (r.get("second_opinion") or {}).get("agrees")}


# ------------------------------------------------------------------ API

@app.get("/api/config")
def config():
    return {"app_name": APP_NAME, "ai": llm.available(), "ai_model": llm.model_name() if llm.available() else None,
            "ai_provider": llm.provider(), "ai_can_read_scans": llm.can_read_pdf(), "store": store.kind,
            "fields": FIELD_LABELS}


@app.get("/api/summary")
def summary():
    _sync()
    reviews = _reviews()
    eff = [_effective(r, reviews.get(k)) for k, r in RESULTS.items()]
    cats = Counter(r["category"] for r in eff)
    stats = Counter(r["status"] for r in eff if r["category"] == "BL_COMPARISON")
    open_reviews = sum(1 for r in eff if (r["status"] == "NEEDS_REVIEW" or r.get("decided_by") == "rule_low_confidence")
                       and not r.get("review"))
    auto = sum(1 for r in eff if r["status"] != "NEEDS_REVIEW" and r.get("decided_by") != "rule_low_confidence")
    by = Counter(r.get("decided_by") for r in eff)
    ai_touched = sum(1 for r in eff if r.get("ai_used"))
    val = DATA / "validation.json"
    return {"total": len(eff), "categories": cats, "doc_status": stats, "open_reviews": open_reviews,
            "reviewed": len(reviews), "auto_pct": round(100 * auto / max(1, len(eff)), 1),
            "decided_by": by, "ai_touched": ai_touched, "mismatch_fields": Counter(f for r in eff if r["status"] == "MISMATCH" for f in r["defect_fields"]),
            "validation": json.loads(val.read_text(encoding="utf-8")) if val.exists() else None,
            # rough: 3 min to triage + 10 min per manual SI-vs-BL check
            "minutes_saved": 3 * len(eff) + 10 * (stats.get("OK", 0) + stats.get("MISMATCH", 0))}


@app.get("/api/emails")
def list_emails(category: str | None = None, status: str | None = None, q: str | None = None,
                queue: bool = False, ai: bool = False):
    _sync()
    reviews = _reviews()
    rows = []
    for k, r in RESULTS.items():
        e = _effective(r, reviews.get(k))
        if queue and not ((e["status"] == "NEEDS_REVIEW" or e.get("decided_by") == "rule_low_confidence") and not e.get("review")):
            continue
        if ai and not e.get("ai_used"):
            continue
        if category and e["category"] != category:
            continue
        if status and e["status"] != status:
            continue
        if q and q.lower() not in (e.get("subject", "") + " " + e.get("from", "") + " " + k).lower():
            continue
        rows.append(_row(e))
    rows.sort(key=lambda r: (not r["uploaded"], r["email_id"]))
    return rows


@app.get("/api/emails/{email_id}")
def get_email(email_id: str):
    if email_id not in RESULTS:
        raise HTTPException(404, "not found")
    return _effective(RESULTS[email_id], _reviews().get(email_id))


class Review(BaseModel):
    action: Literal["confirm", "correct"]
    category: Literal["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"] | None = None
    status: Literal["OK", "MISMATCH", "NEEDS_REVIEW", "WAITING_FOR_BL", "NOT_CHECKED"] | None = None
    defect_fields: list[str] | None = None
    note: str | None = None
    reviewer: str | None = None


@app.post("/api/emails/{email_id}/review")
def review(email_id: str, body: Review):
    if email_id not in RESULTS:
        raise HTTPException(404, "not found")
    if body.defect_fields:
        bad = set(body.defect_fields) - set(FIELDS)
        if bad:
            raise HTTPException(400, f"unknown fields {bad}")
    rec = body.model_dump() | {"at": time.strftime("%Y-%m-%d %H:%M")}
    try:
        store.save_review(email_id, rec)
    except Exception as exc:
        raise HTTPException(503, f"Could not save the review: {exc}")
    return get_email(email_id)


@app.post("/api/emails/{email_id}/reprocess")
def reprocess(email_id: str):
    """Retry — e.g. after a processing error or once the AI key is set."""
    if email_id not in RESULTS:
        raise HTTPException(404, "not found")
    r = RESULTS[email_id]
    email = {k: r[k] for k in ("email_id", "from", "subject", "body", "attachments")}
    RESULTS[email_id] = process_email(email, _read_bytes, use_llm=True)
    if email_id.startswith("new_"):
        store.save_result(email_id, RESULTS[email_id])
    return get_email(email_id)


@app.post("/api/emails/{email_id}/draft-reply")
def draft_reply(email_id: str):
    e = get_email(email_id)
    rows = [r for r in e.get("comparison", []) if r["field"] in (e.get("defect_fields") or [])]
    if not rows:
        raise HTTPException(400, "No differences to report.")
    out = llm.draft_correction_email(e, rows) if llm.available() else None
    if not out:
        lines = "\n".join(f"  • {r['label']}: should be \"{r['si']}\" (draft BL shows \"{r['bl']}\")" for r in rows)
        out = {"subject": f"Amendment needed: {e.get('subject', '')}",
               "body": f"Dear team,\n\nThank you for the draft Bill of Lading. Please amend the following so it matches our Shipping Instruction:\n\n{lines}\n\nPlease send the revised draft for our confirmation.\n\nBest regards,\nShipping Documentation"}
        out["generated_by"] = "template"
    else:
        out["generated_by"] = "ai"
    return out


class NewFile(BaseModel):
    name: str
    content_b64: str


class NewEmail(BaseModel):
    sender: str = "demo@example.com"
    subject: str
    body: str = ""
    files: list[NewFile] = Field(default_factory=list)


MAX_FILES = 5
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024


@app.post("/api/process")
def process_new(body: NewEmail):
    """Process an email typed / uploaded in the dashboard, live."""
    if len(body.files) > MAX_FILES:
        raise HTTPException(400, f"At most {MAX_FILES} attachments are allowed.")
    decoded: list[tuple[str, bytes]] = []
    seen_names: set[str] = set()
    total_bytes = 0
    for f in body.files:
        safe = re.sub(r"[^\w.\-]+", "_", Path(f.name).name)[:80] or "file"
        if safe.casefold() in seen_names:
            raise HTTPException(400, f"Duplicate attachment name after sanitising: {safe}")
        seen_names.add(safe.casefold())
        try:
            raw = base64.b64decode(f.content_b64, validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(400, f"Attachment {safe} is not valid base64.")
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(413, f"Attachment {safe} is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB.")
        total_bytes += len(raw)
        if total_bytes > MAX_TOTAL_BYTES:
            raise HTTPException(413, "The combined attachments are too large.")
        decoded.append((safe, raw))

    eid = f"new_{uuid.uuid4().hex}"
    folder = UPLOADS / eid
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for safe, raw in decoded:
        (folder / safe).write_bytes(raw)
        paths.append(f"uploads/{eid}/{safe}")
    email = {"email_id": eid, "from": body.sender, "subject": body.subject, "body": body.body, "attachments": paths}
    res = process_email(email, _read_bytes, use_llm=True)
    RESULTS[eid] = res
    try:
        store.save_result(eid, res)
    except Exception as exc:
        print("could not persist upload:", exc)
    return get_email(eid)


@app.get("/api/submission")
def submission():
    reviews = _reviews()
    sub = {k: to_submission(_effective(r, reviews.get(k))) for k, r in RESULTS.items() if not k.startswith("new_")}
    return JSONResponse(sub, headers={"Content-Disposition": "attachment; filename=submission.json"})


@app.get("/api/files/{path:path}")
def get_file(path: str):
    p, _ = _content_path(path)
    allowed = [(DATA / "attachments").resolve(), UPLOADS.resolve()]
    if not any(_is_within(p, a) for a in allowed) or not p.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(p)


@app.get("/health")
def health():
    return {"ok": not BOOT_PROBLEMS, "emails": len(RESULTS),
            "problems": BOOT_PROBLEMS or None}


if STATIC.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    if not (STATIC / "index.html").exists():
        raise HTTPException(500, "Dashboard files were not deployed. See /health.")
    return FileResponse(STATIC / "index.html")
