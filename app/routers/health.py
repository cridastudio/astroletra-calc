from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.services.astro import EPHEMERIS_BACKEND
from app.services import pdf as pdf_service

router = APIRouter()


@router.get("/v1/health")
def health() -> dict:
    return {
        "ok": True,
        "version": __version__,
        "ephemeris_backend": EPHEMERIS_BACKEND,
        "pdf_available": pdf_service.is_available(),
    }
