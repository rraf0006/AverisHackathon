"""Vercel entry point: serves the whole app (dashboard + API) as one function.

Vercel's filesystem is read-only apart from /tmp, so anything the app writes at
runtime is redirected there. Reviews and live-upload results are persisted to
Supabase instead (SUPABASE_URL / SUPABASE_KEY), which is what makes them survive
between invocations — /tmp does not.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("VERCEL", "1")          # app.api / app.llm then default to /tmp
os.environ.setdefault("UPLOADS_DIR", "/tmp/shipcheck-uploads")
os.environ.setdefault("LLM_CACHE_DIR", "/tmp/shipcheck-llm-cache")

try:
    from app.api import app  # noqa: E402  (ASGI app Vercel serves)
except Exception:
    # If the app cannot even be imported, Vercel reports only
    # FUNCTION_INVOCATION_FAILED, which says nothing about why. Serve the real
    # traceback instead, plus what is actually in the bundle — that is almost
    # always the answer (a folder that was not uploaded, or a dependency that
    # did not install). Contains no secrets: env var names only, never values.
    import traceback

    _tb = traceback.format_exc()

    def _inventory() -> str:
        lines = [f"cwd: {Path.cwd()}", f"ROOT: {ROOT}", f"sys.path[0]: {sys.path[0]}", ""]
        for rel in (".", "src", "src/app", "src/static", "data", "api"):
            d = ROOT / rel
            try:
                names = sorted(p.name for p in d.iterdir())[:25]
                lines.append(f"{rel}/  ->  {', '.join(names) or '(empty)'}")
            except Exception as exc:
                lines.append(f"{rel}/  ->  MISSING ({type(exc).__name__})")
        lines.append("")
        lines.append("env vars set (names only): " + ", ".join(sorted(
            k for k in os.environ
            if k in {"VERCEL", "LLM_PROVIDER", "APP_NAME", "DEEPSEEK_API_KEY",
                     "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"})))
        return "\n".join(lines)

    _body = ("ShipCheck failed to start.\n\n"
             "--- traceback ---\n" + _tb +
             "\n--- what is in the bundle ---\n" + _inventory() + "\n").encode("utf-8")

    async def app(scope, receive, send):        # minimal ASGI, no dependencies
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 500,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": _body})
