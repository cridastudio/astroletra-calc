"""Mundane sky endpoints for the free web content: lunations, retrogrades, the sky of
the day, the sky of a day, week, month and year for a solar sign and the next solar return."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.auth import require_calc_key
from app.schemas import (
    LunationsRequest,
    RetrogradesRequest,
    SignDayRequest,
    SignMonthRequest,
    SignWeekRequest,
    SignYearRequest,
    SolarReturnNextRequest,
    TodayRequest,
)
from app.services import sign_sky, sky

router = APIRouter(prefix="/v1", dependencies=[Depends(require_calc_key)])


@router.post("/lunations")
def lunations(req: LunationsRequest) -> dict[str, Any]:
    return sky.lunations(req.from_, req.to, req.tz)


@router.post("/retrogrades")
def retrogrades(req: RetrogradesRequest) -> dict[str, Any]:
    return sky.retrogrades(req.from_, req.to, planets=list(req.planets) if req.planets else None, shadow=req.shadow)


@router.post("/today")
def today(req: TodayRequest) -> dict[str, Any]:
    return sky.today(req.date, req.tz)


@router.post("/sign-year")
def sign_year(req: SignYearRequest) -> dict[str, Any]:
    return sky.sign_year(req.sign_num, req.year, req.tz)


@router.post("/sign-day")
def sign_day(req: SignDayRequest) -> dict[str, Any]:
    return sign_sky.sign_day(req.sign_num, req.date, req.tz, req.lang)


@router.post("/sign-week")
def sign_week(req: SignWeekRequest) -> dict[str, Any]:
    return sign_sky.sign_week(req.sign_num, req.from_, req.tz, req.lang)


@router.post("/sign-month")
def sign_month(req: SignMonthRequest) -> dict[str, Any]:
    return sign_sky.sign_month(req.sign_num, req.year, req.month, req.tz, req.lang)


@router.post("/solar-return-next")
def solar_return_next(req: SolarReturnNextRequest) -> dict[str, Any]:
    return sky.solar_return_next(req.natal, req.after, req.tz)
