"""Tiny .env loader (no extra dependency) + app-wide settings."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def env(name: str, default: str | None = None) -> str | None:
    """os.environ.get, except that a variable set to "" counts as unset.

    Hosts create environment variables from a .env.example and leave the values
    blank, so os.environ.get(name, default) hands back "" instead of the default
    — the key exists, it is just empty. That turned float(...) on a blank
    LLM_MIN_INTERVAL into a ValueError at import time, which took the whole app
    down on Vercel with no route left to report it.
    """
    value = os.environ.get(name)
    return default if value is None or not value.strip() else value.strip()


APP_NAME = env("APP_NAME", "ShipCheck")


def load_env(path: Path = ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
