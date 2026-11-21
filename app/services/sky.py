"""Mundane sky data for the free web content.

Lunations with eclipses, retrograde periods with stations and shadows, the
sky of a given day (Moon, exact aspects, active retrogrades), the relevant
transits of a year for a solar sign and the next solar return.

Everything is geocentric and tropical. Instants are computed in UTC and then
expressed in the requested IANA zone; the Worker never converts times itself.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from kerykeion import (
    EclipseFactory,
    LunationFinderFactory,
    PlanetaryReturnFactory,
    RetrogradeStationFactory,
    SignIngressFactory,
)
from kerykeion.ephemeris_backend.backend import ephe, ephemeris_session

from app.schemas import BirthData
from app.services.astro import (
    SIGN_NAMES,
    TEN_PLANETS,
    build_subject,
    local_iso_to_tz,
    moon_phase_of,
    subject_from_utc,
)

UTC = timezone.utc

# Planets whose retrograde periods are published (fast and social planets).
RETROGRADE_PLANETS: list[str] = ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
# Slow planets whose ingresses and whole-sign aspects feed the sign forecast.
OUTER_PLANETS: list[str] = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
# Planets that can be retrograde (the Sun and the Moon never are).
RETRO_CAPABLE: list[str] = TEN_PLANETS[2:]

ASPECTS: dict[str, int] = {"conjunction": 0, "sextile": 60, "square": 90, "trine": 120, "opposition": 180}
# Whole-sign distance (in signs) -> aspect name.
SIGN_DISTANCE_ASPECT: dict[int, str] = {0: "conjunction", 2: "sextile", 3: "square", 4: "trine", 6: "opposition"}
DAILY_ASPECT_ORB = 1.0

# Longest retrograde period among RETROGRADE_PLANETS is Saturn's (~140 days);
# the search window is widened by this much so clipped periods get real stations.
_STATION_MARGIN_DAYS = 240
# Coarse step (days) of the shadow search before bisection, per planet.
_SHADOW_STEP_DAYS: dict[str, int] = {"Mercury": 1, "Venus": 2, "Mars": 3, "Jupiter": 6, "Saturn": 8}
_SHADOW_MAX_DAYS: dict[str, int] = {"Mercury": 60, "Venus": 90, "Mars": 150, "Jupiter": 240, "Saturn": 300}

_PLANET_IDS: dict[str, int] = {
    name: getattr(ephe, name.upper(), getattr(ephe, f"SE_{name.upper()}", None))
    for name in TEN_PLANETS
}
_FLAGS = getattr(ephe, "FLG_SWIEPH", 2) | getattr(ephe, "FLG_SPEED", 256)


# --------------------------------------------------------------------------- helpers


def _sign_fields(abs_degree: float) -> dict[str, Any]:
    abs_degree = abs_degree % 360.0
    sign_num = int(abs_degree // 30)
    return {
        "sign": SIGN_NAMES[sign_num],
        "sign_num": sign_num,
        "degree": round(abs_degree - 30 * sign_num, 2),
        "abs_degree": round(abs_degree, 3),
    }


def _jd(when: datetime) -> float:
    u = when.astimezone(UTC)
    return ephe.julday(u.year, u.month, u.day, u.hour + u.minute / 60 + u.second / 3600 + u.microsecond / 3.6e9)


def _longitude(planet: str, when: datetime) -> tuple[float, float]:
    """Geocentric tropical longitude and daily speed of ``planet`` at ``when``.
    Must be called inside ``ephemeris_session()``."""
    values, _ = ephe.calc_ut(_jd(when), _PLANET_IDS[planet], _FLAGS)
    return float(values[0]) % 360.0, float(values[3])


def _signed_diff(a: float, b: float) -> float:
    """Signed angular distance a - b in (-180, 180]."""
    return (a - b + 180.0) % 360.0 - 180.0


def _to_local(iso_utc: str, tz: str) -> datetime:
    return local_iso_to_tz(iso_utc, tz)


def _local_fields(utc: datetime, tz: str) -> dict[str, str]:
    local = utc.astimezone(ZoneInfo(tz))
    return {
        "datetime_utc": utc.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "datetime_local": local.isoformat(timespec="minutes"),
        "date_local": local.date().isoformat(),
    }


def _parse_utc(iso_utc: str) -> datetime:
    return datetime.fromisoformat(iso_utc.replace("Z", "+00:00")).astimezone(UTC)


def _local_midnight(day: date_type, tz: str) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=ZoneInfo(tz))


def _whole_sign_aspect(sign_a: int, sign_b: int) -> str | None:
    distance = min((sign_a - sign_b) % 12, (sign_b - sign_a) % 12)
    return SIGN_DISTANCE_ASPECT.get(distance)


# --------------------------------------------------------------------------- eclipses


def _eclipses_between(start: date_type, end: date_type) -> list[dict[str, Any]]:
    """Global solar and lunar eclipses whose maximum falls between the two dates (UTC)."""
    years = end.year - start.year + 1
    result = EclipseFactory.search_global(start_year=start.year, count=years * 4 + 2)
    out: list[dict[str, Any]] = []
    for kind, items in (("solar", result.solar_eclipses), ("lunar", result.lunar_eclipses)):
        for e in items:
            when = _parse_utc(e.datestamp)
            if not (start <= when.date() <= end):
                continue
            entry: dict[str, Any] = {
                "type": kind,
                "kind": e.type,
                "datetime_utc": when.isoformat(timespec="seconds").replace("+00:00", "Z"),
                "saros": e.saros,
            }
            entry.update(_sign_fields(float(e.ecliptic_longitude)))
            if kind == "solar":
                entry["duration_minutes"] = round(float(e.duration_minutes), 1) if e.duration_minutes else None
            else:
                entry["magnitude_umbral"] = round(float(e.magnitude_umbral), 3) if e.magnitude_umbral is not None else None
            out.append(entry)
    out.sort(key=lambda x: x["datetime_utc"])
    return out


# --------------------------------------------------------------------------- lunations


def lunations(start: date_type, end: date_type, tz: str) -> dict[str, Any]:
    """New and full Moons between ``start`` and ``end`` (local dates in ``tz``), eclipses marked."""
    # Widen by one day on both sides so local dates near the range edges are not lost.
    found = LunationFinderFactory.from_iso_range(
        (start - timedelta(days=1)).isoformat(), (end + timedelta(days=2)).isoformat(), phases=["new", "full"]
    )
    eclipses = _eclipses_between(start - timedelta(days=2), end + timedelta(days=2))
    items: list[dict[str, Any]] = []
    for lun in found.lunations:
        utc = _parse_utc(lun.iso_utc)
        local = utc.astimezone(ZoneInfo(tz))
        if not (start <= local.date() <= end):
            continue
        entry: dict[str, Any] = {"phase": lun.phase}
        entry.update(_local_fields(utc, tz))
        entry.update(_sign_fields(float(lun.moon.abs_pos)))
        entry["sun"] = _sign_fields(float(lun.sun.abs_pos))
        entry["moon"] = _sign_fields(float(lun.moon.abs_pos))
        wanted = "solar" if lun.phase == "new" else "lunar"
        match = None
        for e in eclipses:
            if e["type"] != wanted:
                continue
            if abs((_parse_utc(e["datetime_utc"]) - utc).total_seconds()) <= 36 * 3600:
                match = dict(e)
                match.update({k: v for k, v in _local_fields(_parse_utc(e["datetime_utc"]), tz).items() if k != "datetime_utc"})
                break
        entry["eclipse"] = match
        items.append(entry)
    return {"from": start.isoformat(), "to": end.isoformat(), "tz": tz, "lunations": items}


# --------------------------------------------------------------------------- retrogrades


def _station_entry(station: Any) -> dict[str, Any]:
    utc = _parse_utc(station.iso_utc)
    entry: dict[str, Any] = {
        "datetime_utc": utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "date": utc.date().isoformat(),
    }
    entry.update(_sign_fields(float(station.ecliptic_longitude)))
    return entry


def _find_crossing(planet: str, target: float, origin: datetime, direction: int, before_sign: int) -> datetime | None:
    """Walk from ``origin`` in ``direction`` (+1 forward, -1 backward) until the signed
    difference longitude - target changes sign, then bisect. ``before_sign`` is the sign
    of the difference at ``origin`` (+1 or -1)."""
    step = timedelta(days=_SHADOW_STEP_DAYS[planet]) * direction
    limit = _SHADOW_MAX_DAYS[planet]
    prev = origin
    f_prev = _signed_diff(_longitude(planet, prev)[0], target)
    elapsed = 0
    while elapsed <= limit:
        cur = prev + step
        f_cur = _signed_diff(_longitude(planet, cur)[0], target)
        if (f_cur < 0) != (f_prev < 0) and abs(f_cur) < 90 and abs(f_prev) < 90:
            lo, hi, f_lo = prev, cur, f_prev
            for _ in range(20):
                mid = lo + (hi - lo) / 2
                f_mid = _signed_diff(_longitude(planet, mid)[0], target)
                if (f_mid < 0) == (f_lo < 0):
                    lo, f_lo = mid, f_mid
                else:
                    hi = mid
            return lo + (hi - lo) / 2
        prev, f_prev = cur, f_cur
        elapsed += abs(step.days)
    return None


def retrogrades(start: date_type, end: date_type, *, planets: list[str] | None = None, shadow: bool = True) -> dict[str, Any]:
    """Retrograde periods of ``planets`` that overlap ``start``..``end`` (UTC dates), with
    the exact stations, the signs of each station and (optionally) the shadow dates."""
    planets = planets or RETROGRADE_PLANETS
    wide_start = start - timedelta(days=_STATION_MARGIN_DAYS)
    wide_end = end + timedelta(days=_STATION_MARGIN_DAYS)
    stations = RetrogradeStationFactory.from_iso_range(wide_start.isoformat(), wide_end.isoformat(), planets=planets)
    by_planet: dict[str, list[Any]] = {p: [] for p in planets}
    for s in stations.stations:
        by_planet.setdefault(s.planet, []).append(s)

    periods: list[dict[str, Any]] = []
    with ephemeris_session():
        for planet in planets:
            seq = sorted(by_planet.get(planet, []), key=lambda s: s.julian_day)
            for i, s in enumerate(seq):
                if s.station_type != "SR":
                    continue
                nxt = seq[i + 1] if i + 1 < len(seq) else None
                if nxt is None or nxt.station_type != "SD":
                    continue
                sr, sd = _station_entry(s), _station_entry(nxt)
                sr_date, sd_date = date_type.fromisoformat(sr["date"]), date_type.fromisoformat(sd["date"])
                if sd_date < start or sr_date > end:
                    continue
                entry: dict[str, Any] = {
                    "planet": planet,
                    "from": sr["date"],
                    "to": sd["date"],
                    "days": (sd_date - sr_date).days,
                    "station_retrograde": sr,
                    "station_direct": sd,
                    # Signs in travel order: a retrograde arc is < 30 degrees, so at most two.
                    "signs": [sr["sign"]] + ([sd["sign"]] if sd["sign"] != sr["sign"] else []),
                    "shadow_from": None,
                    "shadow_to": None,
                }
                if shadow:
                    sr_utc, sd_utc = _parse_utc(sr["datetime_utc"]), _parse_utc(sd["datetime_utc"])
                    pre = _find_crossing(planet, sd["abs_degree"], sr_utc, -1, +1)
                    post = _find_crossing(planet, sr["abs_degree"], sd_utc, +1, -1)
                    entry["shadow_from"] = pre.date().isoformat() if pre else None
                    entry["shadow_to"] = post.date().isoformat() if post else None
                periods.append(entry)
    periods.sort(key=lambda p: (p["from"], p["planet"]))
    return {"from": start.isoformat(), "to": end.isoformat(), "planets": planets, "periods": periods}


# --------------------------------------------------------------------------- today


def _moon_ingress_after(when_utc: datetime, tz: str) -> dict[str, Any] | None:
    """First Moon sign change at or after ``when_utc`` (the Moon changes sign every ~2.5 days)."""
    start = (when_utc - timedelta(days=1)).date().isoformat()
    end = (when_utc + timedelta(days=4)).date().isoformat()
    found = SignIngressFactory.from_iso_range(start, end, planets=["Moon"])
    for ing in found.ingresses:
        utc = _parse_utc(ing.iso_utc)
        if utc >= when_utc:
            entry: dict[str, Any] = {"sign": SIGN_NAMES[int(ing.sign_num)], "sign_num": int(ing.sign_num), "from_sign": SIGN_NAMES[int(ing.from_sign_num)]}
            entry.update(_local_fields(utc, tz))
            return entry
    return None


def _daily_aspects(day_start: datetime, day_end: datetime, tz: str) -> list[dict[str, Any]]:
    """Aspects between the ten planets that are exact during the day (bisection) or within
    DAILY_ASPECT_ORB at one of the day boundaries (then ``exact`` is false and ``orb`` is the
    smallest distance seen)."""
    with ephemeris_session():
        pos_start = {p: _longitude(p, day_start)[0] for p in TEN_PLANETS}
        pos_end = {p: _longitude(p, day_end)[0] for p in TEN_PLANETS}
        found: list[dict[str, Any]] = []
        for i, p1 in enumerate(TEN_PLANETS):
            for p2 in TEN_PLANETS[i + 1:]:
                for aspect, degrees in ASPECTS.items():
                    # Sextile, square and trine happen with p1 ahead of p2 or behind it:
                    # check both signed separations (0 and 180 are their own mirror).
                    for signed in ((degrees,) if degrees in (0, 180) else (degrees, -degrees)):
                        a = _signed_diff(pos_start[p1] - pos_start[p2], signed)
                        b = _signed_diff(pos_end[p1] - pos_end[p2], signed)
                        if abs(a) > 20 and abs(b) > 20:
                            continue
                        exact = (a <= 0 < b) or (b <= 0 < a)
                        if not exact and min(abs(a), abs(b)) > DAILY_ASPECT_ORB:
                            continue
                        entry: dict[str, Any] = {"p1": p1, "p2": p2, "type": aspect, "degrees": degrees}
                        if exact:
                            lo, hi, f_lo = day_start, day_end, a
                            for _ in range(16):
                                mid = lo + (hi - lo) / 2
                                f_mid = _signed_diff(_longitude(p1, mid)[0] - _longitude(p2, mid)[0], signed)
                                if (f_mid < 0) == (f_lo < 0):
                                    lo, f_lo = mid, f_mid
                                else:
                                    hi = mid
                            at = (lo + (hi - lo) / 2).astimezone(ZoneInfo(tz))
                            entry.update({"exact": True, "datetime_local": at.isoformat(timespec="minutes"), "orb": 0.0})
                        else:
                            entry.update({"exact": False, "datetime_local": None, "orb": round(min(abs(a), abs(b)), 2)})
                        entry["applying"] = abs(b) < abs(a)
                        found.append(entry)
    found.sort(key=lambda e: (not e["exact"], e["datetime_local"] or "", e["orb"]))
    return found


def _active_retrogrades(day: date_type, noon_subject: Any) -> list[dict[str, Any]]:
    stations = RetrogradeStationFactory.from_iso_range(
        (day - timedelta(days=_STATION_MARGIN_DAYS)).isoformat(),
        (day + timedelta(days=_STATION_MARGIN_DAYS)).isoformat(),
        planets=RETRO_CAPABLE,
    )
    by_planet: dict[str, list[Any]] = {}
    for s in stations.stations:
        by_planet.setdefault(s.planet, []).append(s)
    active: list[dict[str, Any]] = []
    for planet in RETRO_CAPABLE:
        point = getattr(noon_subject, planet.lower())
        if not point.retrograde:
            continue
        entry: dict[str, Any] = {"planet": planet}
        entry.update(_sign_fields(float(point.abs_pos)))
        seq = sorted(by_planet.get(planet, []), key=lambda s: s.julian_day)
        entry["since"] = next((_station_entry(s)["date"] for s in reversed(seq) if s.station_type == "SR" and _parse_utc(s.iso_utc).date() <= day), None)
        entry["until"] = next((_station_entry(s)["date"] for s in seq if s.station_type == "SD" and _parse_utc(s.iso_utc).date() >= day), None)
        active.append(entry)
    return active


def today(day: date_type, tz: str) -> dict[str, Any]:
    """The sky of one civil day in ``tz``: Moon, exact aspects, active retrogrades, next lunation."""
    day_start = _local_midnight(day, tz)
    day_end = _local_midnight(day + timedelta(days=1), tz)
    noon = day_start + (day_end - day_start) / 2
    noon_subject = subject_from_utc(noon.astimezone(UTC).isoformat(), 0.0, 0.0, tz, TEN_PLANETS)
    start_subject = subject_from_utc(day_start.astimezone(UTC).isoformat(), 0.0, 0.0, tz, ["Moon"])
    end_subject = subject_from_utc((day_end - timedelta(minutes=1)).astimezone(UTC).isoformat(), 0.0, 0.0, tz, ["Moon"])

    moon: dict[str, Any] = _sign_fields(float(noon_subject.moon.abs_pos))
    moon["at_00_00"] = _sign_fields(float(start_subject.moon.abs_pos))
    moon["at_23_59"] = _sign_fields(float(end_subject.moon.abs_pos))
    next_change = _moon_ingress_after(day_start.astimezone(UTC), tz)
    moon["next_sign_change"] = next_change
    moon["changes_sign_today"] = bool(next_change and next_change["date_local"] == day.isoformat())
    moon["phase"] = moon_phase_of(noon_subject)
    moon["void_of_course"] = None  # reserved; not computed in v1

    next_lun = LunationFinderFactory.from_iso_range(day.isoformat(), (day + timedelta(days=32)).isoformat(), phases=["new", "full"])
    upcoming = None
    for lun in next_lun.lunations:
        utc = _parse_utc(lun.iso_utc)
        if utc >= day_start.astimezone(UTC):
            upcoming = {"phase": lun.phase}
            upcoming.update(_local_fields(utc, tz))
            upcoming.update(_sign_fields(float(lun.moon.abs_pos)))
            break

    planets = []
    for name in TEN_PLANETS:
        point = getattr(noon_subject, name.lower())
        entry: dict[str, Any] = {"name": name}
        entry.update(_sign_fields(float(point.abs_pos)))
        entry["retrograde"] = bool(point.retrograde)
        planets.append(entry)

    return {
        "date": day.isoformat(),
        "tz": tz,
        "computed_at_local": noon.isoformat(timespec="minutes"),
        "sun": _sign_fields(float(noon_subject.sun.abs_pos)),
        "moon": moon,
        "planets": planets,
        "aspects": _daily_aspects(day_start, day_end, tz),
        "aspect_orb": DAILY_ASPECT_ORB,
        "retrogrades": _active_retrogrades(day, noon_subject),
        "next_lunation": upcoming,
    }


# --------------------------------------------------------------------------- sign year


def sign_year(sign_num: int, year: int, tz: str = "UTC") -> dict[str, Any]:
    """Transits of a calendar year that matter for one solar sign: sign periods and
    ingresses of Jupiter..Pluto with their whole-sign aspect to ``sign_num``, the Sun's
    season, the eclipses and the Mercury retrogrades (with the aspect of each)."""
    start, end = date_type(year, 1, 1), date_type(year, 12, 31)
    end_iso = (end + timedelta(days=1)).isoformat()

    sun_periods = SignIngressFactory.sign_periods_from_iso_range(start.isoformat(), end_iso, planets=["Sun"])
    season = None
    for p in sun_periods.periods:
        if int(p.sign_num) == sign_num and not p.start_clipped:
            season = {"from": _local_fields(_parse_utc(p.start), tz), "to": _local_fields(_parse_utc(p.end), tz)}
            break

    planets_out: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    periods = SignIngressFactory.sign_periods_from_iso_range(start.isoformat(), end_iso, planets=OUTER_PLANETS)
    ingresses = SignIngressFactory.from_iso_range(start.isoformat(), end_iso, planets=OUTER_PLANETS)
    for planet in OUTER_PLANETS:
        pl_periods = []
        for p in periods.periods:
            if p.planet != planet:
                continue
            aspect = _whole_sign_aspect(int(p.sign_num), sign_num)
            pl_periods.append({
                "sign": SIGN_NAMES[int(p.sign_num)],
                "sign_num": int(p.sign_num),
                "from": _parse_utc(p.start).date().isoformat() if not p.start_clipped else start.isoformat(),
                "to": _parse_utc(p.end).date().isoformat() if not p.end_clipped else end.isoformat(),
                "from_clipped": bool(p.start_clipped),
                "to_clipped": bool(p.end_clipped),
                "aspect_to_sign": aspect,
            })
        pl_ingresses = []
        for ing in ingresses.ingresses:
            if ing.planet != planet:
                continue
            utc = _parse_utc(ing.iso_utc)
            if not (start <= utc.date() <= end):
                continue
            entry: dict[str, Any] = {
                "sign": SIGN_NAMES[int(ing.sign_num)],
                "sign_num": int(ing.sign_num),
                "from_sign": SIGN_NAMES[int(ing.from_sign_num)],
                "retrograde": bool(ing.retrograde),
                "aspect_to_sign": _whole_sign_aspect(int(ing.sign_num), sign_num),
            }
            entry.update(_local_fields(utc, tz))
            pl_ingresses.append(entry)
            events.append({"kind": "ingress", "planet": planet, **entry})
        planets_out.append({"planet": planet, "periods": pl_periods, "ingresses": pl_ingresses})
        for p in pl_periods:
            if p["aspect_to_sign"]:
                events.append({"kind": "aspect", "planet": planet, "aspect": p["aspect_to_sign"], "sign": p["sign"], "from": p["from"], "to": p["to"]})

    eclipses = []
    for e in _eclipses_between(start, end):
        entry = dict(e)
        entry.update({k: v for k, v in _local_fields(_parse_utc(e["datetime_utc"]), tz).items() if k != "datetime_utc"})
        entry["aspect_to_sign"] = _whole_sign_aspect(e["sign_num"], sign_num)
        eclipses.append(entry)

    mercury = []
    for p in retrogrades(start, end, planets=["Mercury"], shadow=False)["periods"]:
        mercury.append({
            "from": p["from"],
            "to": p["to"],
            "signs": p["signs"],
            "aspects_to_sign": sorted({a for a in (_whole_sign_aspect(SIGN_NAMES.index(s), sign_num) for s in p["signs"]) if a}),
        })

    events.sort(key=lambda e: e.get("date_local") or e.get("from") or "")
    return {
        "sign": SIGN_NAMES[sign_num],
        "sign_num": sign_num,
        "year": year,
        "tz": tz,
        "sun_season": season,
        "planets": planets_out,
        "events": events,
        "eclipses": eclipses,
        "mercury_retrogrades": mercury,
    }


# --------------------------------------------------------------------------- solar return


def solar_return_next(natal: BirthData, after: date_type | None, tz: str | None) -> dict[str, Any]:
    """Next (and previous) solar return after ``after`` (default: today in the natal zone),
    expressed in ``tz`` (default: the natal zone). Only the instant is computed; the full
    return chart is ``/v1/solar-return``."""
    tz = tz or natal.tz
    if after is None:
        after = datetime.now(ZoneInfo(natal.tz)).date()
    subject, has_time = build_subject(natal)
    factory = PlanetaryReturnFactory(subject, lng=natal.lon, lat=natal.lat, tz_str=tz, online=False)
    nxt = factory.next_return_from_date(after.year, after.month, after.day, return_type="Solar")
    prev = factory.next_return_from_date(after.year, after.month, after.day, return_type="Solar", backwards=True)
    next_utc = _parse_utc(nxt.iso_formatted_utc_datetime)
    prev_utc = _parse_utc(prev.iso_formatted_utc_datetime)
    if prev_utc > next_utc:
        prev_utc, next_utc = next_utc, prev_utc
    next_local = next_utc.astimezone(ZoneInfo(tz))
    prev_local = prev_utc.astimezone(ZoneInfo(tz))
    warnings: list[str] = []
    if not has_time:
        warnings.append("return_time_uncertain_without_birth_time")
    return {
        "after": after.isoformat(),
        "tz": tz,
        "has_time": has_time,
        "next": {
            "year": next_local.year,
            "age": next_local.year - natal.date.year,
            "return_datetime_local": next_local.isoformat(timespec="minutes"),
            "return_datetime_utc": next_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "days_until": (next_local.date() - after).days,
        },
        "previous": {
            "year": prev_local.year,
            "return_datetime_local": prev_local.isoformat(timespec="minutes"),
            "return_datetime_utc": prev_utc.isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "natal_sun": _sign_fields(float(subject.sun.abs_pos)),
        "warnings": warnings,
    }
