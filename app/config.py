"""Runtime configuration read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _default_tarot_dir() -> Path:
    # app/config.py -> project root is one level above "app".
    root = Path(__file__).resolve().parents[1]
    return root / "assets" / "tarot"


@dataclass(frozen=True)
class Settings:
    calc_key: str = field(default_factory=lambda: os.environ.get("CALC_KEY", "").strip())
    tarot_assets_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("TAROT_ASSETS_DIR") or _default_tarot_dir())
    )
    pdf_allowed_hosts: frozenset[str] = field(
        default_factory=lambda: frozenset(
            h.strip().lower() for h in os.environ.get("PDF_ALLOWED_HOSTS", "").split(",") if h.strip()
        )
    )
    # Hard limit for the HTML accepted by /v1/pdf (bytes).
    pdf_max_html_bytes: int = 8 * 1024 * 1024


def get_settings() -> Settings:
    """Build settings on each call so tests can override environment variables."""
    return Settings()
