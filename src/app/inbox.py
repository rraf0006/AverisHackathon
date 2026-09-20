"""Same interface as the organisers' data/loader.py (local folder or their
HTTP server), so the app can point at either with INBOX_SOURCE.

loader.py is a data file, not a package module, so it is loaded from disk. On a
host where data/ was not deployed that raises at import time and takes the whole
app with it, so a failure here is reported rather than raised: nothing in the web
app uses Inbox (only scripts/run_batch.py does), and a dashboard that loads and
says what is wrong beats every route returning 500.
"""
import importlib.util

from .config import ROOT

Inbox = None
LOAD_ERROR: str | None = None

_path = ROOT / "data" / "loader.py"
try:
    _spec = importlib.util.spec_from_file_location("organiser_loader", _path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    Inbox = _mod.Inbox
except Exception as exc:                      # missing file, or a broken loader
    LOAD_ERROR = f"{type(exc).__name__}: {exc}"
