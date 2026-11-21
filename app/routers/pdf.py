from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth import require_calc_key
from app.config import Settings, get_settings
from app.schemas import PdfRequest
from app.services.pdf import PdfUnavailable, render_pdf

router = APIRouter(prefix="/v1", dependencies=[Depends(require_calc_key)])


@router.post("/pdf", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def pdf(req: PdfRequest, settings: Settings = Depends(get_settings)) -> Response:
    if len(req.html.encode("utf-8")) > settings.pdf_max_html_bytes:
        raise HTTPException(413, "HTML too large")
    try:
        data = render_pdf(req.html, base_url=req.base_url, allowed_hosts=settings.pdf_allowed_hosts)
    except PdfUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(content=data, media_type="application/pdf")
