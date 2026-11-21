"""Transits of the ten planets over a natal chart, day by day in the reader's zone ("Tu cielo").

For every local civil day of the range (midnight to midnight in ``tz``, daylight saving
included) the ten planets are sampled every two hours; a sign change of the signed
distance to an exact aspect (conjunction, sextile, square, trine, opposition) with a natal
point is refined by bisection to the minute. Natal points: the ten planets, plus the
Ascendant and the MC when the birth time is known.

Houses: Placidus cusps of the natal chart when the birth time is known; otherwise solar
houses (whole signs counted from the natal Sun), flagged with ``house_system: "solar"``.
Each event carries the natal house the transiting planet crosses at the exact moment
(``transit_house``) and the house of the natal point it touches (``natal_point_house``).

Slow planets (Jupiter to Pluto) that stay within ``orb`` of an aspect without perfecting
that day are reported once per day with ``exact: false`` and their orb at local noon.
New and full Moons of the range come with the natal house where they fall.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from kerykeion import LunationFinderFactory
from kerykeion.ephemeris_backend.backend import ephemeris_session

from app.schemas import BirthData
from app.services.astro import HOUSE_ATTRS, SIGN_NAMES, TEN_PLANETS, build_subject
from app.services.sky import UTC, _longitude, _parse_utc, _signed_diff

ASPECTS: dict[str, int] = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
SLOW_PLANETS: list[str] = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
STEP_HOURS = 2
DEFAULT_ORB = 1.0
MAX_DAYS = 62


def _sign_of(deg: float) -> tuple[str, int, float]:
    deg = deg % 360.0
    n = int(deg // 30)
    return SIGN_NAMES[n], n, round(deg - 30 * n, 2)


def _house_of(deg: float, cusps: list[float]) -> int:
    deg = deg % 360.0
    for i in range(12):
        a, b = cusps[i], cusps[(i + 1) % 12]
        span = (b - a) % 360.0
        if (deg - a) % 360.0 < span:
            return i + 1
    return 12


def _natal(subject: Any, has_time: bool) -> tuple[dict[str, float], list[float], str]:
    points = {name: float(getattr(subject, name.lower()).abs_pos) for name in TEN_PLANETS}
    if has_time:
        points["Ascendant"] = float(subject.ascendant.abs_pos)
        points["MC"] = float(subject.medium_coeli.abs_pos)
        cusps = [float(getattr(subject, attr).abs_pos) for attr in HOUSE_ATTRS]
        return points, cusps, "placidus"
    sun_sign = int(points["Sun"] // 30)
    cusps = [((sun_sign + i) % 12) * 30.0 for i in range(12)]
    return points, cusps, "solar"


def _local_midnight(day: date_type, tz: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=tz).astimezone(UTC)


def _bisect(planet: str, target: float, signed: float, lo: datetime, hi: datetime, f_lo: float) -> datetime:
    for _ in range(20):
        mid = lo + (hi - lo) / 2
        f_mid = _signed_diff(_longitude(planet, mid)[0] - target, signed)
        if (f_mid < 0) == (f_lo < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def _event_id(day: str, planet: str, aspect: str, point: str, used: set[str]) -> str:
    base = f"{day}:{planet}_{aspect}_{point}".lower().replace(" ", "_")
    out, n = base, 2
    while out in used:
        out, n = f"{base}_{n}", n + 1
    used.add(out)
    return out


def natal_transits(natal: BirthData, start: date_type, end: date_type, tz: str, *, planets: list[str] | None = None,
                   orb: float = DEFAULT_ORB, include_in_orb: bool = True) -> dict[str, Any]:
    zone = ZoneInfo(tz)
    subject, has_time = build_subject(natal)
    points, cusps, house_system = _natal(subject, has_time)
    moving = [p for p in TEN_PLANETS if planets is None or p in planets]
    events: list[dict[str, Any]] = []
    used: set[str] = set()

    def describe(planet: str, when: datetime, point: str, aspect: str, exact: bool, orb_value: float, retro: bool) -> dict[str, Any]:
        local = when.astimezone(zone)
        lon = _longitude(planet, when)[0]
        t_sign, t_num, t_deg = _sign_of(lon)
        n_sign, n_num, n_deg = _sign_of(points[point])
        day = local.date().isoformat()
        return {
            "id": _event_id(day, planet, aspect, point, used),
            "date_local": day,
            "datetime_local": local.isoformat(timespec="minutes") if exact else None,
            "time_local": local.strftime("%H:%M") if exact else None,
            "datetime_utc": when.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z") if exact else None,
            "transiting": planet,
            "aspect": aspect,
            "degrees": ASPECTS[aspect],
            "natal_point": point,
            "exact": exact,
            "orb": round(orb_value, 2),
            "retrograde": retro,
            "slow": planet in SLOW_PLANETS,
            "transit_sign": t_sign,
            "transit_sign_num": t_num,
            "transit_degree": t_deg,
            "transit_house": _house_of(lon, cusps),
            "natal_point_sign": n_sign,
            "natal_point_sign_num": n_num,
            "natal_point_degree": n_deg,
            "natal_point_house": _house_of(points[point], cusps),
        }

    with ephemeris_session():
        day = start
        while day <= end:
            t0 = _local_midnight(day, zone)
            t1 = _local_midnight(day + timedelta(days=1), zone)
            samples: list[datetime] = []
            t = t0
            while t < t1:
                samples.append(t)
                t += timedelta(hours=STEP_HOURS)
            samples.append(t1)
            noon = t0 + (t1 - t0) / 2
            for planet in moving:
                lons = [_longitude(planet, s) for s in samples]
                for point, target in points.items():
                    for aspect, degrees in ASPECTS.items():
                        for signed in ((degrees,) if degrees in (0, 180) else (degrees, -degrees)):
                            orbs = [_signed_diff(lon - target, signed) for lon, _ in lons]
                            exact_found = False
                            for i in range(len(samples) - 1):
                                a, b = orbs[i], orbs[i + 1]
                                if abs(a) > 30 or abs(b) > 30:
                                    continue
                                if (a <= 0 < b) or (b <= 0 < a):
                                    at = _bisect(planet, target, signed, samples[i], samples[i + 1], a)
                                    if t0 <= at < t1:
                                        events.append(describe(planet, at, point, aspect, True, 0.0, lons[i][1] < 0))
                                        exact_found = True
                            if exact_found or not include_in_orb or planet not in SLOW_PLANETS:
                                continue
                            lon_noon, speed = _longitude(planet, noon)
                            o = abs(_signed_diff(lon_noon - target, signed))
                            if o <= orb:
                                ev = describe(planet, noon, point, aspect, False, o, speed < 0)
                                # Applying when the distance to the exact aspect shrinks during the day.
                                ev["applying"] = abs(orbs[-1]) < abs(orbs[0])
                                events.append(ev)
            day += timedelta(days=1)

    # Outside the session: the lunation factory opens its own (nested sessions are not supported).
    lunations: list[dict[str, Any]] = []
    found = LunationFinderFactory.from_iso_range((start - timedelta(days=1)).isoformat(), (end + timedelta(days=2)).isoformat(), phases=["new", "full"])
    for lun in found.lunations:
        utc = _parse_utc(lun.iso_utc)
        local = utc.astimezone(zone)
        if not (start <= local.date() <= end):
            continue
        moon = float(lun.moon.abs_pos)
        sign, num, deg = _sign_of(moon)
        lunations.append({
            "phase": lun.phase,
            "date_local": local.date().isoformat(),
            "datetime_local": local.isoformat(timespec="minutes"),
            "time_local": local.strftime("%H:%M"),
            "datetime_utc": utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "sign": sign,
            "sign_num": num,
            "degree": deg,
            "house": _house_of(moon, cusps),
        })

    events.sort(key=lambda e: (e["date_local"], not e["exact"], e["datetime_utc"] or "", e["transiting"]))
    natal_out = {}
    for name, deg in points.items():
        s, n, d = _sign_of(deg)
        natal_out[name] = {"sign": s, "sign_num": n, "degree": d, "house": _house_of(deg, cusps)}
    return {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "tz": tz,
        "has_time": has_time,
        "house_system": house_system,
        "orb": orb,
        "planets": moving,
        "natal": natal_out,
        "cusps": [round(c, 3) for c in cusps],
        "events": events,
        "lunations": lunations,
    }
