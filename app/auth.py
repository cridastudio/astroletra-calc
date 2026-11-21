"""X-Calc-Key authentication (constant-time comparison)."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def require_calc_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_calc_key: Annotated[str | None, Header(alias="X-Calc-Key")] = None,
) -> None:
    if not settings.calc_key:
        # Fail closed: a deployment without a key must not serve calculations.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "CALC_KEY is not configured")
    if x_calc_key is None or not hmac.compare_digest(x_calc_key.encode(), settings.calc_key.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing X-Calc-Key")
