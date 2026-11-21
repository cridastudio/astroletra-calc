from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.auth import require_calc_key
from app.config import Settings, get_settings
from app.schemas import TarotDrawRequest
from app.tarot.draw import draw, draw_to_dict
from app.tarot.image import compose, to_png_base64

router = APIRouter(prefix="/v1/tarot", dependencies=[Depends(require_calc_key)])


@router.post("/draw")
def tarot_draw(req: TarotDrawRequest, settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    forced = [(c.card_id, c.reversed) for c in req.cards] if req.cards else None
    try:
        result = draw(req.spread, req.seed, forced)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, f"invalid cards: {exc}") from exc
    payload = draw_to_dict(result, req.lang)
    image, missing = compose(result, settings.tarot_assets_dir, req.lang)
    payload["image_png_b64"] = to_png_base64(image)
    payload["image_width"] = image.width
    payload["image_height"] = image.height
    payload["placeholder_cards"] = missing
    return payload
