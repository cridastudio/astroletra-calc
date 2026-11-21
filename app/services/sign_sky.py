"""The sky of a day, a week or a month seen from one solar sign (portal horoscopes,
).

Model ("solar sign" astrology, as printed horoscopes do it):

- The sign's stretch of the zodiac is 0°-30° of the sign. Its sensitive points are the
  degrees 0, 15 and 30 of the sign (30 is the cusp with the next sign).
- The sign's classical ruler (Mars for Aries and Scorpio, Venus for Taurus and Libra,
  Mercury for Gemini and Virgo, the Moon for Cancer, the Sun for Leo, Jupiter for
  Sagittarius and Pisces, Saturn for Capricorn and Aquarius) is followed in the sky:
  aspects made to the transiting ruler count for the sign.
- Solar houses: house 1 is the sign itself, house 2 the next sign, and so on
  (whole-sign houses from the solar sign).
- Aspects: the five major ones (conjunction, sextile, square, trine, opposition) with
  a 1° orb. ``exact: true`` means the aspect perfects inside the period (time found by
  bisection); for the day endpoint a planet other than the Moon that stays within 1°
  without perfecting is reported with ``exact: false`` and its smallest orb.

Every instant is computed in UTC and returned in the requested IANA zone.
"""

from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Callable
from zoneinfo import ZoneInfo

from kerykeion import LunationFinderFactory, RetrogradeStationFactory, SignIngressFactory
from kerykeion.ephemeris_backend.backend import ephemeris_session

from app.services import es_phrases as es
from app.services.astro import SIGN_NAMES, TEN_PLANETS, moon_phase_of, subject_from_utc
from app.services.sky import (
    _STATION_MARGIN_DAYS,
    ASPECTS,
    RETRO_CAPABLE,
    UTC,
    _daily_aspects,
    _eclipses_between,
    _local_midnight,
    _longitude,
    _parse_utc,
    _sign_fields,
    _signed_diff,
    _whole_sign_aspect,
)

CLASSICAL_RULER: list[str] = [
    "Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
    "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter",
]
MODERN_RULER: dict[int, str] = {7: "Pluto", 10: "Uranus", 11: "Neptune"}

# Sensitive points of the sign: offset in degrees from 0° of the sign.
SIGN_POINTS: dict[str, float] = {"0": 0.0, "15": 15.0, "30": 30.0}
ORB = 1.0

# Cities whose local time is attached to the key instants (the portal shows Madrid,
# Mexico City, Bogota and Buenos Aires side by side).
REPORT_CITIES: dict[str, str] = {
    "madrid": "Europe/Madrid",
    "mexico_city": "America/Mexico_City",
    "bogota": "America/Bogota",
    "buenos_aires": "America/Argentina/Buenos_Aires",
}

# ---- relevance score of an event (fixed formula, also usable for the daily ranking) ----
# Planet weight: luminaries and social planets weigh more; the Moon is frequent, so less.
PLANET_WEIGHT: dict[str, float] = {
    "Sun": 3, "Moon": 1, "Mercury": 2, "Venus": 2, "Mars": 2,
    "Jupiter": 3, "Saturn": 3, "Uranus": 2, "Neptune": 2, "Pluto": 2,
}
ASPECT_WEIGHT: dict[str, float] = {"conjunction": 3, "opposition": 3, "square": 2.5, "trine": 2, "sextile": 1.5}
HARMONIOUS = {"trine", "sextile"}
CHALLENGING = {"square", "opposition"}

_SAMPLE_STEP_DAY = timedelta(hours=1)  # the Moon moves ~0.5° per hour
_SAMPLE_STEP_PERIOD = timedelta(hours=6)  # planets other than the Moon move < 2.3° per day
_BISECT_STEPS = 20


def score_event(event: dict[str, Any]) -> float:
    """Relevance of a dated event for the sign. Formula:

    - eclipse 12, lunation 8; +2 when it falls in house 1 or 7;
    - station 5 + planet weight; +2 when the retrograde period affects the sign;
    - ingress 3 + planet weight; +4 when the planet enters the sign (house 1);
    - Moon ingress 2; +4 when the Moon enters the sign;
    - aspect to a sign point: aspect weight x planet weight / 2; +0.5 on the degree 15;
    - aspect to the ruler: 0.8 x aspect weight x planet weight / 2;
    - sky aspect (between two planets, not involving the ruler): aspect weight x
      (weight 1 + weight 2) / 8. Only used when the day has no event of the sign.
    """
    kind = event["kind"]
    planet = event.get("planet")
    house = event.get("house")
    if kind == "eclipse":
        score = 12 + (2 if house in (1, 7) else 0)
    elif kind == "lunation":
        score = 8 + (2 if house in (1, 7) else 0)
    elif kind == "station":
        score = 5 + PLANET_WEIGHT[planet] + (2 if event.get("affects") else 0)
    elif kind == "ingress":
        score = 3 + PLANET_WEIGHT[planet] + (4 if house == 1 else 0)
    elif kind == "moon_ingress":
        score = 2 + (4 if house == 1 else 0)
    elif kind == "aspect_to_sign":
        score = ASPECT_WEIGHT[event["type"]] * PLANET_WEIGHT[planet] / 2 + (0.5 if event["point"] == "15" else 0)
    elif kind == "aspect_to_ruler":
        score = 0.8 * ASPECT_WEIGHT[event["type"]] * PLANET_WEIGHT[planet] / 2
    elif kind == "sky_aspect":
        score = ASPECT_WEIGHT[event["type"]] * (PLANET_WEIGHT[event["p1"]] + PLANET_WEIGHT[event["p2"]]) / 8
    else:  # pragma: no cover - every kind is listed above
        score = 0
    return round(float(score), 2)


# --------------------------------------------------------------------------- helpers


def house_of(planet_sign_num: int, sign_num: int) -> int:
    return (planet_sign_num - sign_num) % 12 + 1


def _instant(utc: datetime, tz: str) -> dict[str, str]:
    local = utc.astimezone(ZoneInfo(tz))
    return {
        "datetime_utc": utc.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "datetime_local": local.isoformat(timespec="minutes"),
        "date_local": local.date().isoformat(),
        "time_local": local.strftime("%H:%M"),
    }


def _city_times(utc: datetime) -> dict[str, str]:
    return {city: utc.astimezone(ZoneInfo(zone)).isoformat(timespec="minutes") for city, zone in REPORT_CITIES.items()}


def _position(planet: str, when: datetime, sign_num: int) -> dict[str, Any]:
    """Position, solar house and motion of ``planet``; inside ``ephemeris_session()``."""
    lon, speed = _longitude(planet, when)
    entry: dict[str, Any] = _sign_fields(lon)
    entry["house"] = house_of(entry["sign_num"], sign_num)
    entry["retrograde"] = planet not in ("Sun", "Moon") and speed < 0
    entry["speed"] = round(speed, 4)
    return entry


def _sample(planets: list[str], start: datetime, end: datetime, step: timedelta) -> tuple[list[datetime], dict[str, list[float]]]:
    times: list[datetime] = []
    t = start
    while t < end:
        times.append(t)
        t += step
    times.append(end)
    return times, {p: [_longitude(p, t)[0] for t in times] for p in planets}


def _bisect(f: Callable[[datetime], float], lo: datetime, hi: datetime, f_lo: float) -> datetime:
    for _ in range(_BISECT_STEPS):
        mid = lo + (hi - lo) / 2
        f_mid = f(mid)
        if (f_mid < 0) == (f_lo < 0):
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return lo + (hi - lo) / 2


def _scan(
    mover: str,
    times: list[datetime],
    mover_lons: list[float],
    target_lons: list[float],
    target_at: Callable[[datetime], float],
    *,
    near: bool,
) -> list[dict[str, Any]]:
    """Major aspects between ``mover`` and a target (fixed degree or moving planet) over the
    sampled interval. Each hit: ``{type, degrees, exact, at, orb, applying}``."""
    hits: list[dict[str, Any]] = []
    for aspect, degrees in ASPECTS.items():
        exact_found = False
        best: float | None = None
        best_variant: tuple[float, float] | None = None
        # Sextile, square and trine happen with the mover ahead of the target or behind it.
        for signed in ((degrees,) if degrees in (0, 180) else (degrees, -degrees)):
            f = [_signed_diff(m - t, signed) for m, t in zip(mover_lons, target_lons)]
            if min(abs(x) for x in f) > 20:
                continue
            for i in range(len(times) - 1):
                a, b = f[i], f[i + 1]
                if abs(a) < 90 and abs(b) < 90 and ((a <= 0 < b) or (b <= 0 < a)):
                    at = _bisect(lambda t, s=signed: _signed_diff(_longitude(mover, t)[0] - target_at(t), s), times[i], times[i + 1], a)
                    hits.append({"type": aspect, "degrees": degrees, "exact": True, "at": at, "orb": 0.0, "applying": None})
                    exact_found = True
            low = min(abs(x) for x in f)
            if best is None or low < best:
                best, best_variant = low, (f[0], f[-1])
        if near and not exact_found and best is not None and best <= ORB and best_variant is not None:
            hits.append({
                "type": aspect, "degrees": degrees, "exact": False, "at": None,
                "orb": round(best, 2), "applying": abs(best_variant[1]) < abs(best_variant[0]),
            })
    return hits


@lru_cache(maxsize=16)
def _eclipses_of_year(year: int) -> tuple[dict[str, Any], ...]:
    return tuple(_eclipses_between(date_type(year, 1, 1), date_type(year, 12, 31)))


def _eclipse_near(utc: datetime, phase: str) -> dict[str, Any] | None:
    wanted = "solar" if phase == "new" else "lunar"
    for year in {utc.year, (utc - timedelta(days=2)).year, (utc + timedelta(days=2)).year}:
        for e in _eclipses_of_year(year):
            if e["type"] == wanted and abs((_parse_utc(e["datetime_utc"]) - utc).total_seconds()) <= 36 * 3600:
                return e
    return None


def _retro_reasons(planet: str, signs: list[int], sign_num: int, hits_points: set[str]) -> list[str]:
    reasons: list[str] = []
    if CLASSICAL_RULER[sign_num] == planet:
        reasons.append("classical_ruler")
    if MODERN_RULER.get(sign_num) == planet:
        reasons.append("modern_ruler")
    for s in signs:
        aspect = _whole_sign_aspect(s, sign_num)
        reason = {"conjunction": "in_sign", "opposition": "opposite_sign", "square": "square_sign"}.get(aspect or "")
        if reason and reason not in reasons:
            reasons.append(reason)
    if planet in hits_points:
        reasons.append("aspects_sign_degree")
    return reasons


# --------------------------------------------------------------------------- event builders


def _event(kind: str, utc: datetime, tz: str, label: str, **fields: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {"kind": kind}
    entry.update(fields)
    entry.update(_instant(utc, tz))
    entry["label"] = label
    entry["score"] = score_event(entry)
    return entry


def _ingress_events(start: datetime, end: datetime, tz: str, sign_num: int, *, with_date: bool) -> list[dict[str, Any]]:
    """Sign ingresses of the ten planets (the Moon too) between two instants."""
    found = SignIngressFactory.from_iso_range(
        (start.astimezone(UTC) - timedelta(days=1)).date().isoformat(),
        (end.astimezone(UTC) + timedelta(days=2)).date().isoformat(),
        planets=TEN_PLANETS,
    )
    out: list[dict[str, Any]] = []
    for ing in found.ingresses:
        utc = _parse_utc(ing.iso_utc)
        if not (start <= utc < end):
            continue
        new_sign, old_sign = int(ing.sign_num), int(ing.from_sign_num)
        house, from_house = house_of(new_sign, sign_num), house_of(old_sign, sign_num)
        moment = es.when_es(utc.astimezone(ZoneInfo(tz)), tz, with_date=with_date)
        if ing.planet == "Moon":
            label = f"La Luna entra en {es.sign(SIGN_NAMES[new_sign])}, {es.house(house)}, {moment}."
            kind = "moon_ingress"
        else:
            retro = " retrógrado" if ing.retrograde else ""
            label = f"{es.planet(ing.planet)}{retro} entra en {es.sign(SIGN_NAMES[new_sign])}, {es.house(house)}, {moment}."
            kind = "ingress"
        out.append(_event(
            kind, utc, tz, label,
            planet=ing.planet, sign=SIGN_NAMES[new_sign], sign_num=new_sign, house=house,
            from_sign=SIGN_NAMES[old_sign], from_house=from_house, retrograde=bool(ing.retrograde),
            local_times=_city_times(utc) if ing.planet == "Moon" or house == 1 else None,
        ))
    return out


def _lunation_events(start: datetime, end: datetime, tz: str, sign_num: int, *, with_date: bool) -> list[dict[str, Any]]:
    found = LunationFinderFactory.from_iso_range(
        (start.astimezone(UTC) - timedelta(days=1)).date().isoformat(),
        (end.astimezone(UTC) + timedelta(days=2)).date().isoformat(),
        phases=["new", "full"],
    )
    out: list[dict[str, Any]] = []
    for lun in found.lunations:
        utc = _parse_utc(lun.iso_utc)
        if not (start <= utc < end):
            continue
        pos = _sign_fields(float(lun.moon.abs_pos))
        house = house_of(pos["sign_num"], sign_num)
        eclipse = _eclipse_near(utc, lun.phase)
        moment = es.when_es(utc.astimezone(ZoneInfo(tz)), tz, with_date=with_date)
        where = f"a {es.degree(pos['degree'])} de {es.sign(pos['sign'])}, en {es.house(house)}"
        if eclipse:
            kind_es = {"total": "total", "annular": "anular", "partial": "parcial", "penumbral": "penumbral", "hybrid": "híbrido"}.get(eclipse["kind"], eclipse["kind"])
            name = f"Eclipse {'solar' if eclipse['type'] == 'solar' else 'lunar'} {kind_es}"
            ecl = dict(eclipse)
            ecl.update({k: v for k, v in _instant(_parse_utc(eclipse["datetime_utc"]), tz).items() if k != "datetime_utc"})
        else:
            name = "Luna nueva" if lun.phase == "new" else "Luna llena"
            ecl = None
        out.append(_event(
            "eclipse" if eclipse else "lunation", utc, tz, f"{name} {where}, {moment}.",
            planet="Moon", phase=lun.phase, house=house, eclipse=ecl, local_times=_city_times(utc), **pos,
        ))
    return out


def _retro_periods(start: datetime, end: datetime, tz: str, sign_num: int, hits_points: set[str], *, with_date: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Retrograde periods (Mercury..Pluto) that overlap ``start``..``end`` and the station
    events inside it."""
    found = RetrogradeStationFactory.from_iso_range(
        (start.astimezone(UTC) - timedelta(days=_STATION_MARGIN_DAYS)).date().isoformat(),
        (end.astimezone(UTC) + timedelta(days=_STATION_MARGIN_DAYS)).date().isoformat(),
        planets=RETRO_CAPABLE,
    )
    by_planet: dict[str, list[Any]] = {}
    for s in found.stations:
        by_planet.setdefault(s.planet, []).append(s)

    periods: list[dict[str, Any]] = []
    stations: list[dict[str, Any]] = []
    for planet in RETRO_CAPABLE:
        seq = sorted(by_planet.get(planet, []), key=lambda s: s.julian_day)
        for i, sr in enumerate(seq):
            if sr.station_type != "SR" or i + 1 >= len(seq) or seq[i + 1].station_type != "SD":
                continue
            sd = seq[i + 1]
            sr_utc, sd_utc = _parse_utc(sr.iso_utc), _parse_utc(sd.iso_utc)
            if sd_utc < start or sr_utc >= end:
                continue
            sr_pos, sd_pos = _sign_fields(float(sr.ecliptic_longitude)), _sign_fields(float(sd.ecliptic_longitude))
            signs = [sr_pos["sign_num"]] + ([sd_pos["sign_num"]] if sd_pos["sign_num"] != sr_pos["sign_num"] else [])
            reasons = _retro_reasons(planet, signs, sign_num, hits_points)
            entry: dict[str, Any] = {
                "planet": planet,
                "since": _instant(sr_utc, tz)["date_local"],
                "until": _instant(sd_utc, tz)["date_local"],
                "station_retrograde": {**_instant(sr_utc, tz), **sr_pos, "house": house_of(sr_pos["sign_num"], sign_num)},
                "station_direct": {**_instant(sd_utc, tz), **sd_pos, "house": house_of(sd_pos["sign_num"], sign_num)},
                "signs": [SIGN_NAMES[s] for s in signs],
                "houses": [house_of(s, sign_num) for s in signs],
                "reasons": reasons,
                "affects": bool(reasons),
            }
            periods.append(entry)
            for kind_station, utc, pos in (("retrograde", sr_utc, sr_pos), ("direct", sd_utc, sd_pos)):
                if not (start <= utc < end):
                    continue
                house = house_of(pos["sign_num"], sign_num)
                moment = es.when_es(utc.astimezone(ZoneInfo(tz)), tz, with_date=with_date)
                word = "retrógrado" if kind_station == "retrograde" else "directo"
                label = f"{es.planet(planet)} se estaciona {word} a {es.degree(pos['degree'])} de {es.sign(pos['sign'])}, en {es.house(house)}, {moment}."
                stations.append(_event(
                    "station", utc, tz, label,
                    planet=planet, station=kind_station, house=house, affects=bool(reasons), **pos,
                ))
    periods.sort(key=lambda p: (p["since"], p["planet"]))
    return periods, stations


def _aspect_entries(
    sign_num: int,
    movers: list[str],
    times: list[datetime],
    lons: dict[str, list[float]],
    tz: str,
    *,
    near_for: set[str],
    with_date: bool,
    fallback_at: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Aspects of ``movers`` to the sign points and to the classical ruler."""
    ruler = CLASSICAL_RULER[sign_num]
    to_points: list[dict[str, Any]] = []
    for planet in movers:
        planet_hits: list[dict[str, Any]] = []
        for key, offset in SIGN_POINTS.items():
            target = (30.0 * sign_num + offset) % 360.0
            for hit in _scan(planet, times, lons[planet], [target] * len(times), lambda _t, v=target: v, near=planet in near_for):
                planet_hits.append({"point": key, "point_abs_degree": round(target, 3), **hit})
        # A planet can hit the degree 0 and the degree 30 at the same instant (e.g. square to
        # 0° and sextile to 30°): keep the one on the degree 0.
        def same_moment(a: dict[str, Any], b: dict[str, Any]) -> bool:
            if a["exact"] and b["exact"]:
                return abs((a["at"] - b["at"]).total_seconds()) < 120
            return not a["exact"] and not b["exact"] and abs(a["orb"] - b["orb"]) < 0.02

        keep = [
            h for h in planet_hits
            if not (h["point"] == "30" and any(o["point"] == "0" and same_moment(o, h) for o in planet_hits))
        ]
        for h in keep:
            to_points.append(_aspect_entry("aspect_to_sign", planet, h, sign_num, tz, with_date=with_date, fallback_at=fallback_at))

    to_ruler: list[dict[str, Any]] = []
    if ruler in lons:
        for planet in movers:
            if planet == ruler:
                continue
            near = planet in near_for and ruler in near_for
            for h in _scan(planet, times, lons[planet], lons[ruler], lambda t: _longitude(ruler, t)[0], near=near):
                to_ruler.append(_aspect_entry("aspect_to_ruler", planet, h, sign_num, tz, with_date=with_date, fallback_at=fallback_at))

    def order(e: dict[str, Any]) -> tuple[bool, str, float]:
        return (not e["exact"], e["datetime_utc"] or "", e["orb"])

    return sorted(to_points, key=order), sorted(to_ruler, key=order)


def _aspect_entry(kind: str, planet: str, hit: dict[str, Any], sign_num: int, tz: str, *, with_date: bool, fallback_at: datetime) -> dict[str, Any]:
    ruler = CLASSICAL_RULER[sign_num]
    at = hit["at"]
    pos = _position(planet, at or fallback_at, sign_num)
    entry: dict[str, Any] = {"kind": kind, "planet": planet}
    if kind == "aspect_to_sign":
        entry.update({"point": hit["point"], "point_abs_degree": hit["point_abs_degree"]})
        target = es.point(hit["point"])
    else:
        entry["ruler"] = ruler
        target = f"{es.planet(ruler, capital=False)}, tu regente"
    entry["covered_by"] = None
    entry.update({"type": hit["type"], "degrees": hit["degrees"], "exact": hit["exact"], "orb": hit["orb"], "applying": hit["applying"]})
    entry["position"] = pos
    entry["house"] = pos["house"]
    subject = es.planet(planet)
    if at is not None:
        entry.update(_instant(at, tz))
        moment = es.when_es(at.astimezone(ZoneInfo(tz)), tz, with_date=with_date)
        exact_word = "exacto" if hit["type"] in ("sextile", "trine") else "exacta"
        comma = "," if kind == "aspect_to_ruler" else ""
        entry["label"] = f"{subject} forma {es.ASPECT_ES[hit['type']]} {exact_word} con {target}{comma} {moment}."
    else:
        entry.update({"datetime_utc": None, "datetime_local": None, "date_local": None, "time_local": None})
        minutes = round(hit["orb"] * 60)
        entry["label"] = f"{subject} mantiene {es.ASPECT_ES[hit['type']]} con {target}, a {minutes}' del exacto."
    entry["score"] = score_event(entry)
    return entry


def _mark_covered(aspects: list[dict[str, Any]], ingresses: list[dict[str, Any]]) -> None:
    """Flag exact aspects that another event already states, so the event list does not
    repeat them (they stay in ``aspects_to_sign`` / ``aspects_to_ruler``):

    - an aspect to the degree 0 or 30 of the sign is a sign ingress of the same planet
      (it enters the sign, the opposite sign, a square sign...): ``covered_by: "ingress"``;
    - a Sun-Moon conjunction or opposition (ruler of Leo and Cancer) is a lunation:
      ``covered_by: "lunation"``.
    """
    for a in aspects:
        if not a["exact"]:
            continue
        if a["kind"] == "aspect_to_ruler" and {a["planet"], a["ruler"]} == {"Sun", "Moon"} and a["type"] in ("conjunction", "opposition"):
            a["covered_by"] = "lunation"
        elif a.get("point") in ("0", "30"):
            at = _parse_utc(a["datetime_utc"])
            if any(i["planet"] == a["planet"] and abs((_parse_utc(i["datetime_utc"]) - at).total_seconds()) < 120 for i in ingresses):
                a["covered_by"] = "ingress"


def _sky_aspects(start: datetime, end: datetime, tz: str, sign_num: int, noon_planets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Exact aspects between two planets during the day (as in ``/v1/today``), placed in the
    sign's solar houses. Aspects with the ruler are left out (they are ``aspects_to_ruler``),
    and so are Sun-Moon conjunctions and oppositions (lunations)."""
    ruler = CLASSICAL_RULER[sign_num]
    out: list[dict[str, Any]] = []
    for a in _daily_aspects(start.astimezone(ZoneInfo(tz)), end.astimezone(ZoneInfo(tz)), tz):
        if not a["exact"] or ruler in (a["p1"], a["p2"]):
            continue
        if {a["p1"], a["p2"]} == {"Sun", "Moon"} and a["type"] in ("conjunction", "opposition"):
            continue
        utc = datetime.fromisoformat(a["datetime_local"]).astimezone(UTC)
        h1, h2 = noon_planets[a["p1"]]["house"], noon_planets[a["p2"]]["house"]
        exact_word = "exacto" if a["type"] in ("sextile", "trine") else "exacta"
        moment = es.when_es(utc.astimezone(ZoneInfo(tz)), tz, with_date=False)
        label = (
            f"{es.planet(a['p1'])} ({es.house(h1)}) forma {es.ASPECT_ES[a['type']]} {exact_word} "
            f"con {es.planet(a['p2'], capital=False)} ({es.house(h2)}) {moment}."
        )
        out.append(_event("sky_aspect", utc, tz, label, p1=a["p1"], p2=a["p2"], type=a["type"], degrees=a["degrees"], houses=[h1, h2]))
    return out


def _balance(aspects: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "harmonious": sum(1 for a in aspects if a["type"] in HARMONIOUS),
        "challenging": sum(1 for a in aspects if a["type"] in CHALLENGING),
        "conjunction": sum(1 for a in aspects if a["type"] == "conjunction"),
    }


def _pick_featured(events: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Highest score first (earliest on ties), at most one event per (kind, planet)."""
    ranked = sorted(events, key=lambda e: (-e["score"], e["datetime_utc"]))
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str | None]] = set()
    for e in ranked:
        key = (e["kind"], e.get("planet") or e.get("p1"))
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
        if len(out) == count:
            break
    return out


def _retro_sentence(periods: list[dict[str, Any]], *, ongoing_on: date_type | None = None) -> str | None:
    parts = []
    for p in periods:
        if not p["affects"]:
            continue
        if ongoing_on is not None and not (p["since"] <= ongoing_on.isoformat() <= p["until"]):
            continue
        sign_txt = " y ".join(es.sign(s) for s in p["signs"])
        houses = " y ".join(str(h) for h in p["houses"])
        house_txt = f"tu casa {houses}" if len(p["houses"]) == 1 else f"tus casas {houses}"
        until = es.date_es(date_type.fromisoformat(p["until"]))
        since = es.date_es(date_type.fromisoformat(p["since"]))
        parts.append(f"{es.planet(p['planet'])} en {sign_txt} ({house_txt}), del {since} al {until}")
        if len(parts) == 2:
            break
    if not parts:
        return None
    return f"Retrógrado{'s' if len(parts) > 1 else ''} que te afecta{'n' if len(parts) > 1 else ''}: {'; '.join(parts)}."


def _unique(items: list[str | None], limit: int) -> list[str]:
    out: list[str] = []
    for s in items:
        if s and s not in out:
            out.append(s)
        if len(out) == limit:
            break
    return out


def _moon_ingresses_around(start: datetime, end: datetime) -> list[tuple[datetime, int, int]]:
    found = SignIngressFactory.from_iso_range(
        (start.astimezone(UTC) - timedelta(days=4)).date().isoformat(),
        (end.astimezone(UTC) + timedelta(days=5)).date().isoformat(),
        planets=["Moon"],
    )
    return sorted((_parse_utc(i.iso_utc), int(i.from_sign_num), int(i.sign_num)) for i in found.ingresses)


def _next_lunation(start: datetime, tz: str, sign_num: int) -> dict[str, Any] | None:
    found = LunationFinderFactory.from_iso_range(
        start.astimezone(UTC).date().isoformat(), (start.astimezone(UTC) + timedelta(days=32)).date().isoformat(), phases=["new", "full"]
    )
    for lun in found.lunations:
        utc = _parse_utc(lun.iso_utc)
        if utc >= start:
            pos = _sign_fields(float(lun.moon.abs_pos))
            return {"phase": lun.phase, **_instant(utc, tz), **pos, "house": house_of(pos["sign_num"], sign_num)}
    return None


def _ruler_info(sign_num: int, when: datetime) -> dict[str, Any]:
    ruler = CLASSICAL_RULER[sign_num]
    return {"classical": ruler, "modern": MODERN_RULER.get(sign_num), "position": _position(ruler, when, sign_num)}


def _sign_points(sign_num: int) -> list[dict[str, Any]]:
    return [{"point": k, "abs_degree": round((30.0 * sign_num + v) % 360.0, 3)} for k, v in SIGN_POINTS.items()]


# --------------------------------------------------------------------------- day


def sign_day(sign_num: int, day: date_type, tz: str) -> dict[str, Any]:
    """Everything a daily horoscope of ``sign_num`` needs for one civil day in ``tz``."""
    start = _local_midnight(day, tz).astimezone(UTC)
    end = _local_midnight(day + timedelta(days=1), tz).astimezone(UTC)
    noon = start + (end - start) / 2
    sign = SIGN_NAMES[sign_num]

    with ephemeris_session():
        times, lons = _sample(TEN_PLANETS, start, end, _SAMPLE_STEP_DAY)
        # Moon and planets sampled every hour: the Moon moves ~0.5° per hour.
        planets = [{"name": p, **_position(p, noon, sign_num)} for p in TEN_PLANETS]
        aspects_to_sign, aspects_to_ruler = _aspect_entries(
            sign_num, TEN_PLANETS, times, lons, tz,
            near_for={p for p in TEN_PLANETS if p != "Moon"}, with_date=False, fallback_at=noon,
        )
        moon_00 = _position("Moon", start, sign_num)
        moon_2359 = _position("Moon", end - timedelta(minutes=1), sign_num)
        ruler = _ruler_info(sign_num, noon)

    # Moon: houses crossed during the day, change of the day and next change.
    ingresses = _moon_ingresses_around(start, end)
    segments = []
    for i, (utc, _from, to_sign) in enumerate(ingresses):
        seg_end = ingresses[i + 1][0] if i + 1 < len(ingresses) else None
        if utc >= end or (seg_end is not None and seg_end <= start) or seg_end is None:
            continue
        segments.append({
            "sign": SIGN_NAMES[to_sign], "sign_num": to_sign, "house": house_of(to_sign, sign_num),
            "from": _instant(utc, tz), "to": _instant(seg_end, tz),
        })
    nxt = next(((u, f, t) for u, f, t in ingresses if u >= start), None)
    next_change = None
    if nxt is not None:
        utc, from_sign, to_sign = nxt
        next_change = {
            "sign": SIGN_NAMES[to_sign], "sign_num": to_sign, "house": house_of(to_sign, sign_num),
            "from_sign": SIGN_NAMES[from_sign], "from_house": house_of(from_sign, sign_num),
            **_instant(utc, tz), "local_times": _city_times(utc),
        }
    changes_today = bool(next_change and _parse_utc(next_change["datetime_utc"]) < end)
    noon_subject = subject_from_utc(noon.isoformat(), 0.0, 0.0, tz, ["Sun", "Moon"])
    moon_noon = next(p for p in planets if p["name"] == "Moon")
    moon: dict[str, Any] = {
        **{k: v for k, v in moon_noon.items() if k not in ("name", "retrograde")},
        "at_00_00": moon_00,
        "at_23_59": moon_2359,
        "phase": moon_phase_of(noon_subject),
        "houses_today": segments,
        "changes_house_today": changes_today,
        "next_sign_change": next_change,
    }

    ingress_events = _ingress_events(start, end, tz, sign_num, with_date=False)
    _mark_covered(aspects_to_sign + aspects_to_ruler, ingress_events)
    hits_points = {a["planet"] for a in aspects_to_sign if a["covered_by"] is None}
    periods, stations = _retro_periods(start, end, tz, sign_num, hits_points, with_date=False)
    events = (
        ingress_events
        + stations
        + _lunation_events(start, end, tz, sign_num, with_date=False)
        + [a for a in aspects_to_sign + aspects_to_ruler if a["exact"] and a["covered_by"] is None]
    )
    events.sort(key=lambda e: e["datetime_utc"])
    sky_aspects = _sky_aspects(start, end, tz, sign_num, {p["name"]: p for p in planets})
    top = _pick_featured(events, 3)
    if not top:
        # No event of the sign today: the exact aspects of the day's sky, in its houses.
        top = _pick_featured(sky_aspects, 2)
    featured: dict[str, Any] | None = None
    if top:
        featured = {**top[0], "in_period": True}
        featured.setdefault("local_times", None)
        if not featured.get("local_times"):
            featured["local_times"] = _city_times(_parse_utc(featured["datetime_utc"]))
    elif next_change is not None:
        # No dated event today: the next Moon ingress is the closest dated fact.
        utc = _parse_utc(next_change["datetime_utc"])
        moment = es.when_es(utc.astimezone(ZoneInfo(tz)), tz, with_date=True)
        featured = {
            "kind": "moon_ingress", "planet": "Moon", "sign": next_change["sign"], "sign_num": next_change["sign_num"],
            "house": next_change["house"], **_instant(utc, tz), "local_times": next_change["local_times"],
            "label": f"La Luna entra en {es.sign(next_change['sign'])}, {es.house(next_change['house'])}, {moment}.",
            "in_period": False,
        }
        featured["score"] = score_event(featured)

    # Highlights: data sentences, 3 to 5.
    phase = moon["phase"] or {}
    if changes_today and next_change:
        when = _parse_utc(next_change["datetime_utc"]).astimezone(ZoneInfo(tz))
        moon_sentence = (
            f"La Luna pasa de {es.sign(next_change['from_sign'])} ({es.house(next_change['from_house'])}) "
            f"a {es.sign(next_change['sign'])} ({es.house(next_change['house'])}) {es.time_es(when, tz)}."
        )
    elif next_change:
        when = _parse_utc(next_change["datetime_utc"]).astimezone(ZoneInfo(tz))
        moon_sentence = (
            f"La Luna está en {es.sign(moon_00['sign'])} ({es.house(moon_00['house'])}) todo el día "
            f"y entra en {es.sign(next_change['sign'])} ({es.house(next_change['house'])}) {es.when_es(when, tz, with_date=True)}."
        )
    else:  # pragma: no cover - the Moon changes sign every 2.5 days
        moon_sentence = f"La Luna está en {es.sign(moon_noon['sign'])} ({es.house(moon_noon['house'])})."
    sun = planets[0]
    sun_sentence = f"El Sol está a {es.degree(sun['degree'])} de {es.sign(sun['sign'])}, en {es.house(sun['house'])}."
    phase_sentence = None
    if phase.get("illumination") is not None:
        stage = "creciente" if phase.get("stage") == "waxing" else "menguante"
        phase_sentence = f"Luna {stage}, con el {round(phase['illumination'] * 100)} % del disco iluminado."
    others = [e["label"] for e in top if e["kind"] != "moon_ingress"]
    highlights = _unique([moon_sentence, *others[:2], _retro_sentence(periods, ongoing_on=day), sun_sentence, phase_sentence], 5)

    return {
        "sign": sign,
        "sign_num": sign_num,
        "date": day.isoformat(),
        "tz": tz,
        "city": es.city_of(tz),
        "computed_at_local": noon.astimezone(ZoneInfo(tz)).isoformat(timespec="minutes"),
        "orb": ORB,
        "ruler": ruler,
        "sign_points": _sign_points(sign_num),
        "sun": {k: v for k, v in sun.items() if k not in ("name", "retrograde")},
        "moon": moon,
        "planets": planets,
        "aspects_to_sign": aspects_to_sign,
        "aspects_to_ruler": aspects_to_ruler,
        "aspect_balance": _balance(aspects_to_sign + aspects_to_ruler),
        "retrogrades": periods,
        "retrogrades_affecting": [p["planet"] for p in periods if p["affects"]],
        "events": events,
        "sky_aspects": sky_aspects,
        "featured": featured,
        "next_lunation": _next_lunation(start, tz, sign_num),
        "highlights": highlights,
    }


# --------------------------------------------------------------------------- week and month


def sign_period(sign_num: int, first: date_type, last: date_type, tz: str, *, period: str) -> dict[str, Any]:
    """Dated events between the local midnights of ``first`` and ``last + 1`` for one sign.

    The Moon is left out of the aspect scan (it would add some 30 aspects a month); its
    sign changes come as ``moon_ingresses`` and ``moon_by_day``, and the lunations as events.
    When the ruler is the Moon (Cancer) there are no aspects to the ruler for the same reason.
    """
    start = _local_midnight(first, tz).astimezone(UTC)
    end = _local_midnight(last + timedelta(days=1), tz).astimezone(UTC)
    movers = [p for p in TEN_PLANETS if p != "Moon"]
    days = [first + timedelta(days=i) for i in range((last - first).days + 1)]

    def local_noon(d: date_type) -> datetime:
        a = _local_midnight(d, tz).astimezone(UTC)
        b = _local_midnight(d + timedelta(days=1), tz).astimezone(UTC)
        return a + (b - a) / 2

    with ephemeris_session():
        times, lons = _sample(movers, start, end, _SAMPLE_STEP_PERIOD)
        aspects_to_sign, aspects_to_ruler = _aspect_entries(
            sign_num, movers, times, lons, tz, near_for=set(), with_date=True, fallback_at=start,
        )
        planets_start = [{"name": p, **_position(p, local_noon(first), sign_num)} for p in TEN_PLANETS]
        planets_end = [{"name": p, **_position(p, local_noon(last), sign_num)} for p in TEN_PLANETS]
        moon_by_day = []
        for d in days:
            pos = _position("Moon", local_noon(d), sign_num)
            moon_by_day.append({"date": d.isoformat(), "sign": pos["sign"], "sign_num": pos["sign_num"], "degree": pos["degree"], "house": pos["house"]})
        ruler = _ruler_info(sign_num, local_noon(first))

    ingresses = _ingress_events(start, end, tz, sign_num, with_date=True)
    _mark_covered(aspects_to_sign + aspects_to_ruler, ingresses)
    hits_points = {a["planet"] for a in aspects_to_sign if a["covered_by"] is None}
    periods, stations = _retro_periods(start, end, tz, sign_num, hits_points, with_date=True)
    lunations = _lunation_events(start, end, tz, sign_num, with_date=True)
    events = ingresses + stations + lunations + [a for a in aspects_to_sign + aspects_to_ruler if a["covered_by"] is None]
    events.sort(key=lambda e: e["datetime_utc"])
    featured = _pick_featured(events, 3)
    for e in featured:
        if not e.get("local_times"):
            e["local_times"] = _city_times(_parse_utc(e["datetime_utc"]))

    sun_start, sun_end = planets_start[0], planets_end[0]
    span = "toda la semana" if period == "week" else "todo el mes"
    sun_ingress = next((e for e in ingresses if e["planet"] == "Sun"), None)
    if sun_ingress is not None:
        sun_sentence = sun_ingress["label"]
    else:
        sun_sentence = f"El Sol recorre {es.sign(sun_start['sign'])} ({es.house(sun_start['house'])}) {span}."
    moon_in_sign = [e for e in ingresses if e["kind"] == "moon_ingress" and e["house"] == 1]
    moon_sentence = moon_in_sign[0]["label"] if moon_in_sign else None
    highlights = _unique([*(e["label"] for e in featured), moon_sentence, _retro_sentence(periods), sun_sentence], 5)

    return {
        "sign": SIGN_NAMES[sign_num],
        "sign_num": sign_num,
        "period": period,
        "from": first.isoformat(),
        "to": last.isoformat(),
        "tz": tz,
        "city": es.city_of(tz),
        "orb": ORB,
        "ruler": ruler,
        "sign_points": _sign_points(sign_num),
        "sun": {"at_start": {k: v for k, v in sun_start.items() if k != "name"}, "at_end": {k: v for k, v in sun_end.items() if k != "name"}},
        "planets_start": planets_start,
        "planets_end": planets_end,
        "moon_by_day": moon_by_day,
        "moon_ingresses": [e for e in ingresses if e["kind"] == "moon_ingress"],
        "aspects_to_sign": aspects_to_sign,
        "aspects_to_ruler": aspects_to_ruler,
        "aspect_balance": _balance(aspects_to_sign + aspects_to_ruler),
        "retrogrades": periods,
        "retrogrades_affecting": [p["planet"] for p in periods if p["affects"]],
        "lunations": lunations,
        "events": events,
        "featured": featured,
        "highlights": highlights,
    }


def sign_week(sign_num: int, first: date_type, tz: str) -> dict[str, Any]:
    return sign_period(sign_num, first, first + timedelta(days=6), tz, period="week")


def sign_month(sign_num: int, year: int, month: int, tz: str) -> dict[str, Any]:
    first = date_type(year, month, 1)
    last = (date_type(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
    return sign_period(sign_num, first, last, tz, period="month")
