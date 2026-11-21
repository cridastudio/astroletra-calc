"""Transits of the slow planets over the natal chart, Mercury retrogrades and ingresses.

Daily sweep of Jupiter..Pluto positions (EphemerisDataFactory), detection of
exact aspects (sign change of the signed orb between two consecutive days) and
refinement of the exact moment by bisection with the ephemeris backend.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from kerykeion import EphemerisDataFactory, RetrogradeStationFactory, SignIngressFactory

from app.schemas import BirthData
from app.services.astro import (
    POINT_NAMES,
    TEN_PLANETS,
    SIGN_NAMES,
    build_subject,
    local_iso_to_tz,
    subject_from_utc,
)

TRANSITING = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
ASPECTS = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
ORB = 1.0
# Natal points receiving transits: the ten planets plus the angles when the time is known.
NATAL_TARGETS = TEN_PLANETS


def _signed_orb(transit_deg: float, natal_deg: float, aspect_deg: float) -> float:
    """Signed distance (degrees) from the exact aspect, in (-180, 180]."""
    d = (transit_deg - natal_deg - aspect_deg + 180.0) % 360.0 - 180.0
    return d


def _natal_points(subject: Any, has_time: bool) -> dict[str, float]:
    points = {POINT_NAMES.get(n, n): float(getattr(subject, n.lower()).abs_pos) for n in NATAL_TARGETS}
    if has_time:
        points["Ascendant"] = float(subject.ascendant.abs_pos)
        points["MC"] = float(subject.medium_coeli.abs_pos)
    return points


def _refine(planet: str, natal_deg: float, aspect_deg: float, t0: datetime, t1: datetime, data: BirthData) -> datetime:
    """Bisection between two UTC instants with opposite signed orb."""
    lo, hi = t0, t1
    f_lo = _signed_orb(_planet_pos(planet, lo, data), natal_deg, aspect_deg)
    for _ in range(14):  # ~6 s precision on a 1-day bracket
        mid = lo + (hi - lo) / 2
        f_mid = _signed_orb(_planet_pos(planet, mid, data), natal_deg, aspect_deg)
        if (f_mid < 0) == (f_lo < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def _is_retro(series: list[float], i: int) -> bool:
    nxt = series[i + 1] if i + 1 < len(series) else series[i]
    return ((nxt - series[i] + 180.0) % 360.0 - 180.0) < 0


def _event(local: datetime, planet: str, aspect: str, natal_name: str, orb: float, exact: bool, retro: bool) -> dict[str, Any]:
    return {
        "date": local.date().isoformat(),
        "datetime_local": local.isoformat(timespec="minutes") if exact else None,
        "transiting": planet,
        "aspect": aspect,
        "natal_point": natal_name,
        "orb": orb,
        "exact": exact,
        "retrograde": retro,
    }


def _planet_pos(planet: str, when: datetime, data: BirthData) -> float:
    subject = subject_from_utc(when.isoformat(), data.lat, data.lon, data.tz, [planet])
    return float(getattr(subject, planet.lower()).abs_pos)


def compute_transits(data: BirthData, start: date_type, end: date_type) -> dict[str, Any]:
    natal, has_time = build_subject(data)
    tz = ZoneInfo(data.tz)
    targets = _natal_points(natal, has_time)

    # Daily positions at 00:00 UTC, one extra day to close the last interval.
    first = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    last = datetime(end.year, end.month, end.day, tzinfo=timezone.utc) + timedelta(days=1)
    factory = EphemerisDataFactory(
        first.replace(tzinfo=None),
        last.replace(tzinfo=None),
        step_type="days",
        step=1,
        lat=data.lat,
        lng=data.lon,
        tz_str="Etc/UTC",
        active_points=TRANSITING,  # type: ignore[arg-type]
        max_days=None,
    )
    samples = factory.get_ephemeris_data_as_astrological_subjects()
    days = [first + timedelta(days=i) for i in range(len(samples))]
    positions = {p: [float(getattr(s, p.lower()).abs_pos) for s in samples] for p in TRANSITING}

    events: list[dict[str, Any]] = []
    for planet in TRANSITING:
        series = positions[planet]
        for natal_name, natal_deg in targets.items():
            for aspect, base_deg in ASPECTS.items():
                # A sextile, square or trine forms with the transit ahead of the natal point
                # (+deg) or behind it (-deg); conjunction and opposition are their own mirror.
                for aspect_deg in ((base_deg,) if base_deg in (0, 180) else (base_deg, -base_deg)):
                    orbs = [_signed_orb(x, natal_deg, aspect_deg) for x in series]
                    for i in range(len(orbs) - 1):
                        a, b = orbs[i], orbs[i + 1]
                        if abs(a) > 5 or abs(b) > 5:
                            continue  # far from the aspect; cannot cross the opposite side within a day
                        if (a <= 0 < b) or (b <= 0 < a):
                            exact_utc = _refine(planet, natal_deg, aspect_deg, days[i], days[i + 1], data)
                            local = exact_utc.astimezone(tz)
                            if start <= local.date() <= end:
                                events.append(_event(local, planet, aspect, natal_name, 0.0, True, _is_retro(series, i)))
                    # Closest approach without an exact pass (the planet stations near the aspect).
                    for i in range(1, len(orbs) - 1):
                        o = abs(orbs[i])
                        if o <= ORB and o <= abs(orbs[i - 1]) and o <= abs(orbs[i + 1]) and (orbs[i - 1] < 0) == (orbs[i] < 0) == (orbs[i + 1] < 0):
                            local = days[i].astimezone(tz)
                            if not (start <= local.date() <= end):
                                continue
                            if any(
                                e["transiting"] == planet and e["natal_point"] == natal_name and e["aspect"] == aspect
                                and abs((date_type.fromisoformat(e["date"]) - local.date()).days) <= 3
                                for e in events
                            ):
                                continue
                            events.append(_event(local, planet, aspect, natal_name, round(o, 2), False, _is_retro(series, i)))
    events.sort(key=lambda e: (e["date"], e["transiting"]))

    months: dict[str, list[dict[str, Any]]] = {}
    cursor = date_type(start.year, start.month, 1)
    while cursor <= end:
        months[cursor.strftime("%Y-%m")] = []
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    for e in events:
        months.setdefault(e["date"][:7], []).append(e)

    retro = RetrogradeStationFactory.retrograde_periods_from_iso_range(
        start.isoformat(), (end + timedelta(days=1)).isoformat(), planets=["Mercury"]
    )
    retrogrades = [
        {
            "planet": p.planet,
            "from": local_iso_to_tz(p.start, data.tz).date().isoformat(),
            "to": local_iso_to_tz(p.end, data.tz).date().isoformat(),
            "from_clipped": bool(p.start_clipped),
            "to_clipped": bool(p.end_clipped),
        }
        for p in retro.periods
    ]

    ing = SignIngressFactory.from_iso_range(start.isoformat(), (end + timedelta(days=1)).isoformat(), planets=["Jupiter", "Saturn"])
    ingresses = [
        {
            "planet": i.planet,
            "sign": SIGN_NAMES[int(i.sign_num)],
            "sign_num": int(i.sign_num),
            "date": local_iso_to_tz(i.iso_utc, data.tz).date().isoformat(),
            "retrograde": bool(i.retrograde),
        }
        for i in ing.ingresses
        if start <= local_iso_to_tz(i.iso_utc, data.tz).date() <= end
    ]

    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "has_time": has_time,
        "orb": ORB,
        "transiting": TRANSITING,
        "natal_points": list(targets.keys()),
        "months": [{"month": m, "events": evs} for m, evs in months.items()],
        "retrogrades": retrogrades,
        "ingresses": ingresses,
    }
