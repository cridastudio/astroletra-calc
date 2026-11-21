"""FastAPI application entry point."""

from __future__ import annotations

import logging
import warnings

from fastapi import FastAPI

from app import __version__
from app.routers import charts, health, natal_transits, pdf, sky, tarot

# Kerykeion warns about libephemeris Keplerian fallbacks for bodies we do not use.
warnings.filterwarnings("ignore", category=DeprecationWarning, module="kerykeion")
logging.getLogger("kerykeion").setLevel(logging.WARNING)

app = FastAPI(
    title="Astroletra calc",
    version=__version__,
    description="Astrology calculations, tarot spreads and PDF rendering for Astroletra. AGPL-3.0-only.",
    docs_url=None,
    redoc_url=None,
)
app.include_router(health.router)
app.include_router(charts.router)
app.include_router(sky.router)
app.include_router(natal_transits.router)
app.include_router(tarot.router)
app.include_router(pdf.router)
