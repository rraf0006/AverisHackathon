"""Tiny .env loader (no extra dependency) + app-wide settings."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_NAME = os.environ.get("APP_NAME", "ShipCheck")


def load_env(path: Path = ROOT / ".env"):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
