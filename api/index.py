"""Vercel entry point: serves the whole app (dashboard + API) as one function.

Vercel's filesystem is read-only apart from /tmp, so anything the app writes at
runtime is redirected there. Reviews and live-upload results are persisted to
Supabase instead (SUPABASE_URL / SUPABASE_KEY), which is what makes them survive
between invocations — /tmp does not.

`app` must be assigned at the top level: Vercel's Python builder looks for it by
reading the file, not by importing it, so an `app` defined inside a try/except
is invisible to it and the build fails with "Could not find a top-level app".
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("VERCEL", "1")          # app.api / app.llm then default to /tmp
os.environ.setdefault("UPLOADS_DIR", "/tmp/shipcheck-uploads")
os.environ.setdefault("LLM_CACHE_DIR", "/tmp/shipcheck-llm-cache")


def _inventory() -> str:
    """What actually made it into the deploy bundle. Names only, never values."""
    lines = [f"cwd: {Path.cwd()}", f"ROOT: {ROOT}", f"sys.path[0]: {sys.path[0]}", ""]
    for rel in (".", "src", "src/app", "src/static", "data", "api"):
        try:
            names = sorted(p.name for p in (ROOT / rel).iterdir())[:25]
            lines.append(f"{rel}/  ->  {', '.join(names) or '(empty)'}")
        except Exception as exc:
            lines.append(f"{rel}/  ->  MISSING ({type(exc).__name__})")
    lines.append("")
    lines.append("env vars set (names only): " + ", ".join(sorted(
        k for k in os.environ
        if k in {"VERCEL", "LLM_PROVIDER", "APP_NAME", "DEEPSEEK_API_KEY",
                 "GEMINI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"})))
    return "\n".join(lines)


def _load_app():
    """The real app, or a minimal ASGI app that explains why it could not load.

    Without this, an import failure reaches the browser as a bare
    FUNCTION_INVOCATION_FAILED with no traceback anywhere except the CLI logs.
    """
    try:
        from app.api import app as shipcheck
        return shipcheck
    except Exception:
        import traceback
        body = ("ShipCheck failed to start.\n\n"
                "--- traceback ---\n" + traceback.format_exc() +
                "\n--- what is in the bundle ---\n" + _inventory() + "\n").encode("utf-8")

        async def failed(scope, receive, send):     # no dependencies of its own
            if scope["type"] != "http":
                return
            await send({"type": "http.response.start", "status": 500,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
            await send({"type": "http.response.body", "body": body})

        return failed


# Top level, so the builder can find it by reading the file. Deliberately NOT
# also aliased to `handler`: the builder treats `handler` as a
# BaseHTTPRequestHandler subclass, and would try to drive this ASGI app as one.
app = _load_app()
