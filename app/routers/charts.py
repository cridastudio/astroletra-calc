"""Natal, synastry, solar return and transits endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kerykeion import AspectsFactory, CompositeSubjectFactory, PlanetaryReturnFactory

from app.auth import require_calc_key
from app.schemas import BirthData, SolarReturnRequest, SynastryRequest, TransitsRequest
from app.services.astro import (
    ANGLE_POINTS,
    MAJOR_ASPECTS,
    PLANET_POINTS,
    POINT_NAMES,
    build_subject,
    cross_aspect_entry,
    serialize_chart,
)
from app.services.transits import compute_transits
from app.services.wheel import double_wheel_svg, natal_wheel_svg

router = APIRouter(prefix="/v1", dependencies=[Depends(require_calc_key)])


def _natal_payload(data: BirthData, name: str = "Subject") -> tuple[dict[str, Any], Any]:
    subject, has_time = build_subject(data, name=name)
    chart = serialize_chart(subject, has_time, data=data)
    chart["wheel_svg"] = natal_wheel_svg(chart)
    return chart, subject


@router.post("/natal")
def natal(data: BirthData) -> dict[str, Any]:
    chart, _ = _natal_payload(data)
    return chart


@router.post("/synastry")
def synastry(req: SynastryRequest) -> dict[str, Any]:
    """Two charts, inter-aspects (A's point first, B's second, sorted by orb), midpoint
    composite (planets + Ascendant when both times are known) and the double wheel."""
    chart_a, subject_a = _natal_payload(req.a, "A")
    chart_b, subject_b = _natal_payload(req.b, "B")
    both_timed = chart_a["has_time"] and chart_b["has_time"]
    points = PLANET_POINTS + (ANGLE_POINTS if both_timed else [])
    inter = AspectsFactory.dual_chart_aspects(
        subject_a,
        subject_b,
        active_points=points,  # type: ignore[arg-type]
        active_aspects=MAJOR_ASPECTS,  # type: ignore[arg-type]
    )
    inter_aspects = sorted((cross_aspect_entry(a, "a", "b") for a in inter.aspects), key=lambda x: x["orb"])

    if req.a.house_system != req.b.house_system:
        raise HTTPException(422, "both charts must use the same house system")
    composite_model = CompositeSubjectFactory(subject_a, subject_b).get_midpoint_composite_subject_model()
    composite_full = serialize_chart(composite_model, both_timed)
    composite = {
        "method": "midpoint",
        "planets": composite_full["planets"],
        "asc": composite_full["angles"]["asc"] if composite_full["angles"] else None,
        "mc": composite_full["angles"]["mc"] if composite_full["angles"] else None,
        "aspects": composite_full["aspects"],
    }

    return {
        "chart_a": chart_a,
        "chart_b": chart_b,
        "inter_aspects": inter_aspects,
        "composite": composite,
        "double_wheel_svg": double_wheel_svg(chart_a, chart_b, inter_aspects),
    }


@router.post("/solar-return")
def solar_return(req: SolarReturnRequest) -> dict[str, Any]:
    """Solar return of ``year`` cast at ``location``. The response carries the return chart
    under ``return_chart`` and the cross aspects return -> natal under ``return_to_natal_aspects``
    (sorted by orb). The natal chart itself is not repeated (the Worker already has it)."""
    natal_subject, has_time = build_subject(req.natal)
    factory = PlanetaryReturnFactory(
        natal_subject,
        lng=req.location.lon,
        lat=req.location.lat,
        tz_str=req.location.tz,
        online=False,
    )
    # Search from January 1st of the requested year: the return falls on the birthday of that year.
    model = factory.next_return_from_date(req.year, 1, 1, return_type="Solar")
    chart = serialize_chart(model, True)
    chart["moon_range"] = None
    warnings: list[str] = []
    if not has_time:
        warnings.append("return_time_uncertain_without_birth_time")
    points = PLANET_POINTS + ANGLE_POINTS
    natal_points = PLANET_POINTS + (ANGLE_POINTS if has_time else [])
    cross = AspectsFactory.dual_chart_aspects(
        model,
        natal_subject,
        active_points=points,  # type: ignore[arg-type]
        active_aspects=MAJOR_ASPECTS,  # type: ignore[arg-type]
    )
    natal_names = {POINT_NAMES.get(n, n) for n in natal_points}
    cross_aspects = sorted(
        (cross_aspect_entry(a, "return_point", "natal_point") for a in cross.aspects if POINT_NAMES.get(a.p2_name, a.p2_name) in natal_names),
        key=lambda x: x["orb"],
    )
    return {
        "year": req.year,
        "return_datetime": model.iso_formatted_local_datetime,
        "return_datetime_utc": model.iso_formatted_utc_datetime,
        "location": req.location.model_dump(),
        "return_chart": chart,
        "return_to_natal_aspects": cross_aspects,
        "warnings": warnings,
        "wheel_svg": natal_wheel_svg(chart, title="Solar return wheel"),
    }


@router.post("/transits")
def transits(req: TransitsRequest) -> dict[str, Any]:
    return compute_transits(req.natal, req.from_, req.to)
