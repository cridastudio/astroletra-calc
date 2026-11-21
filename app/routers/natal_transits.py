"""POST /v1/natal-transits: transits over a natal chart per local day (Worker product "Tu cielo")."""

from __future__ import annotations

from datetime import date as date_type
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

from app.auth import require_calc_key
from app.schemas import BirthData, _check_tz_value
from app.services.natal_transits import MAX_DAYS, natal_transits as compute

router = APIRouter(prefix="/v1", dependencies=[Depends(require_calc_key)])

Planet = Literal["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]


class NatalTransitsRequest(BaseModel):
    natal: BirthData
    from_: date_type = Field(alias="from")
    to: date_type
    tz: str = Field(description="IANA zone of the reader: local days and local times")
    planets: list[Planet] | None = Field(default=None, description="Transiting planets; all ten when omitted")
    orb: float = Field(default=1.0, gt=0, le=3)
    include_in_orb: bool = True

    model_config = {"populate_by_name": True}

    @field_validator("tz")
    @classmethod
    def _tz(cls, v: str) -> str:
        return _check_tz_value(v)

    @field_validator("to")
    @classmethod
    def _range(cls, v: date_type, info):  # type: ignore[no-untyped-def]
        start = info.data.get("from_")
        if start is not None:
            if v < start:
                raise ValueError("'to' must not be before 'from'")
            if (v - start).days >= MAX_DAYS:
                raise ValueError(f"range must be shorter than {MAX_DAYS} days")
        return v


@router.post("/natal-transits")
def natal_transits(req: NatalTransitsRequest) -> dict[str, Any]:
    return compute(req.natal, req.from_, req.to, req.tz, planets=req.planets, orb=req.orb, include_in_orb=req.include_in_orb)
