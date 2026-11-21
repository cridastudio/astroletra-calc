"""Chart construction and serialization on top of Kerykeion 6.

Only the data that the Worker needs is exposed. Point names, sign names and
house numbers are plain English identifiers; the Worker translates them.
"""

from __future__ import annotations

import math
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from kerykeion import AspectsFactory, AstrologicalSubjectFactory
from kerykeion.ephemeris_backend.backend import BACKEND_NAME
from kerykeion.schemas.models import AstrologicalSubjectModel

from app.schemas import BirthData

EPHEMERIS_BACKEND = BACKEND_NAME

# Points reported in every chart. Chiron needs the libephemeris "asteroids" LEB2
# group (installed in the Docker image with ``libephemeris download leb2-base``);
# without it libephemeris falls back to a Keplerian approximation and logs a warning.
PLANET_POINTS: list[str] = [
    "Sun",
    "Moon",
    "Mercury",
    "Venus",
    "Mars",
    "Jupiter",
    "Saturn",
    "Uranus",
    "Neptune",
    "Pluto",
    "True_North_Lunar_Node",
    "Chiron",
]
# Points that count for the element/modality balance and that receive transits.
TEN_PLANETS: list[str] = PLANET_POINTS[:10]
ANGLE_POINTS: list[str] = ["Ascendant", "Medium_Coeli"]

# Public name of each Kerykeion point.
POINT_NAMES: dict[str, str] = {
    "True_North_Lunar_Node": "North Node",
    "Medium_Coeli": "MC",
}

SIGN_NAMES: list[str] = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
SIGN_CODES: list[str] = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
ELEMENT_BY_SIGN: list[str] = ["fire", "earth", "air", "water"] * 3
MODALITY_BY_SIGN: list[str] = ["cardinal", "fixed", "mutable"] * 4

HOUSE_ATTRS: list[str] = [
    "first_house", "second_house", "third_house", "fourth_house", "fifth_house", "sixth_house",
    "seventh_house", "eighth_house", "ninth_house", "tenth_house", "eleventh_house", "twelfth_house",
]
HOUSE_NUMBER: dict[str, int] = {
    "First_House": 1, "Second_House": 2, "Third_House": 3, "Fourth_House": 4,
    "Fifth_House": 5, "Sixth_House": 6, "Seventh_House": 7, "Eighth_House": 8,
    "Ninth_House": 9, "Tenth_House": 10, "Eleventh_House": 11, "Twelfth_House": 12,
}

MAJOR_ASPECTS = [
    {"name": "conjunction", "orb": 8.0},
    {"name": "opposition", "orb": 8.0},
    {"name": "trine", "orb": 7.0},
    {"name": "square", "orb": 7.0},
    {"name": "sextile", "orb": 5.0},
]

NOON = "12:00"


def _round(x: float, nd: int = 2) -> float:
    return round(float(x), nd)


def build_subject(data: BirthData, *, name: str = "Subject", force_time: str | None = None) -> tuple[AstrologicalSubjectModel, bool]:
    """Create a Kerykeion subject. Returns ``(subject, has_time)``.

    Without a birth time the chart is cast at 12:00 local time and the angles are
    not requested as active points (houses are still computed internally but the
    serializer hides them).
    """
    has_time = data.time is not None
    time_str = force_time or data.time or NOON
    hour, minute = (int(part) for part in time_str.split(":"))
    active = PLANET_POINTS + (ANGLE_POINTS if has_time else [])
    subject = AstrologicalSubjectFactory.from_birth_data(
        name,
        data.date.year,
        data.date.month,
        data.date.day,
        hour,
        minute,
        lng=data.lon,
        lat=data.lat,
        tz_str=data.tz,
        online=False,
        houses_system_identifier=data.house_system,
        active_points=active,  # type: ignore[arg-type]
        suppress_geonames_warning=True,
    )
    return subject, has_time


def subject_from_utc(iso_utc: str, lat: float, lon: float, tz: str, points: list[str], house_system: str = "P") -> AstrologicalSubjectModel:
    return AstrologicalSubjectFactory.from_iso_utc_time(
        "Moment",
        iso_utc,
        lng=lon,
        lat=lat,
        tz_str=tz,
        online=False,
        houses_system_identifier=house_system,  # type: ignore[arg-type]
        active_points=points,  # type: ignore[arg-type]
        suppress_geonames_warning=True,
    )


def position_dict(point: Any) -> dict[str, Any]:
    sign_num = int(point.sign_num)
    return {
        "sign": SIGN_NAMES[sign_num],
        "sign_num": sign_num,
        "degree": _round(point.position),
        "abs_degree": _round(point.abs_pos, 3),
    }


def planet_entry(name: str, point: Any, *, with_house: bool) -> dict[str, Any]:
    entry = {"name": POINT_NAMES.get(name, name)}
    entry.update(position_dict(point))
    entry["house"] = HOUSE_NUMBER.get(point.house) if (with_house and point.house) else None
    entry["retrograde"] = bool(point.retrograde) if point.retrograde is not None else False
    entry["element"] = ELEMENT_BY_SIGN[int(point.sign_num)]
    entry["modality"] = MODALITY_BY_SIGN[int(point.sign_num)]
    if point.speed is not None:
        entry["speed"] = _round(point.speed, 4)
    return entry


def planets_of(subject: Any, *, with_house: bool, points: list[str] | None = None) -> list[dict[str, Any]]:
    result = []
    for name in points or PLANET_POINTS:
        point = getattr(subject, name.lower(), None)
        if point is None:
            continue
        result.append(planet_entry(name, point, with_house=with_house))
    return result


def houses_of(subject: Any) -> list[dict[str, Any]]:
    cusps = []
    for i, attr in enumerate(HOUSE_ATTRS, start=1):
        cusp = getattr(subject, attr)
        entry = {"house": i}
        entry.update(position_dict(cusp))
        cusps.append(entry)
    return cusps


def angles_of(subject: Any) -> dict[str, Any]:
    return {
        "asc": position_dict(subject.ascendant),
        "mc": position_dict(subject.medium_coeli),
        "dsc": position_dict(subject.descendant),
        "ic": position_dict(subject.imum_coeli),
    }


def aspects_of(subject: Any, *, points: list[str]) -> list[dict[str, Any]]:
    model = AspectsFactory.single_chart_aspects(
        subject,
        active_points=points,  # type: ignore[arg-type]
        active_aspects=MAJOR_ASPECTS,  # type: ignore[arg-type]
    )
    return sorted((aspect_entry(a) for a in model.aspects), key=lambda x: x["orb"])


def aspect_entry(a: Any) -> dict[str, Any]:
    return {
        "p1": POINT_NAMES.get(a.p1_name, a.p1_name),
        "p2": POINT_NAMES.get(a.p2_name, a.p2_name),
        "type": a.aspect,
        "degrees": int(a.aspect_degrees),
        "orb": _round(a.orbit),
        "applying": a.aspect_movement == "Applying",
    }


def cross_aspect_entry(a: Any, first: str, second: str) -> dict[str, Any]:
    """Aspect between two charts, keyed ``first`` (chart 1 point) and ``second`` (chart 2 point)."""
    return {
        first: POINT_NAMES.get(a.p1_name, a.p1_name),
        second: POINT_NAMES.get(a.p2_name, a.p2_name),
        "type": a.aspect,
        "degrees": int(a.aspect_degrees),
        "orb": _round(a.orbit),
        "applying": a.aspect_movement == "Applying",
    }


def balance_of(planets: list[dict[str, Any]], angles: dict[str, Any] | None) -> dict[str, Any]:
    """Element and modality counts over the ten planets plus the Ascendant when known."""
    elements = {"fire": 0, "earth": 0, "air": 0, "water": 0}
    modalities = {"cardinal": 0, "fixed": 0, "mutable": 0}
    counted: list[int] = [p["sign_num"] for p in planets if p["name"] not in ("North Node", "Chiron")]
    if angles:
        counted.append(angles["asc"]["sign_num"])
    for sign_num in counted:
        elements[ELEMENT_BY_SIGN[sign_num]] += 1
        modalities[MODALITY_BY_SIGN[sign_num]] += 1
    total = max(len(counted), 1)
    return {
        "elements": elements,
        "modalities": modalities,
        "elements_pct": {k: round(100 * v / total) for k, v in elements.items()},
        "modalities_pct": {k: round(100 * v / total) for k, v in modalities.items()},
        "counted_points": total,
        "method": "ten planets" + (" + Ascendant" if angles else ""),
    }


def moon_phase_of(subject: Any) -> dict[str, Any] | None:
    phase = getattr(subject, "lunar_phase", None)
    if phase is None:
        return None
    degrees = float(phase.degrees_between_s_m)
    illumination = (1 - math.cos(math.radians(degrees))) / 2
    return {
        "name": phase.moon_phase_name,
        "sun_moon_angle": _round(degrees, 1),
        "major_phase": phase.major_phase,
        "stage": phase.stage,
        "illumination": round(illumination, 2),
    }


def moon_range_of(data: BirthData) -> dict[str, Any]:
    """Moon position at 00:00 and 23:59 local time for charts without a birth time."""
    start, _ = build_subject(data, force_time="00:00")
    end, _ = build_subject(data, force_time="23:59")
    start_pos = position_dict(start.moon)
    end_pos = position_dict(end.moon)
    return {
        "at_00_00": start_pos,
        "at_23_59": end_pos,
        "sign_changes": start_pos["sign_num"] != end_pos["sign_num"],
    }


def serialize_chart(subject: Any, has_time: bool, *, data: BirthData | None = None) -> dict[str, Any]:
    """Serialize a natal-like subject (natal, solar return, composite) without the SVG."""
    planets = planets_of(subject, with_house=has_time)
    houses = houses_of(subject) if has_time else None
    angles = angles_of(subject) if has_time else None
    points = PLANET_POINTS + (ANGLE_POINTS if has_time else [])
    chart: dict[str, Any] = {
        "has_time": has_time,
        "house_system": getattr(subject, "houses_system_identifier", "P"),
        "datetime_local": getattr(subject, "iso_formatted_local_datetime", None),
        "datetime_utc": getattr(subject, "iso_formatted_utc_datetime", None),
        "planets": planets,
        "houses": houses,
        "angles": angles,
        "aspects": aspects_of(subject, points=points),
        "balance": balance_of(planets, angles),
        "moon_phase": moon_phase_of(subject),
        "moon_range": None,
        "warnings": [],
    }
    if not has_time:
        chart["warnings"].append("no_birth_time")
        if data is not None:
            chart["moon_range"] = moon_range_of(data)
            if chart["moon_range"]["sign_changes"]:
                chart["warnings"].append("moon_changes_sign_that_day")
    return chart


def local_iso_to_tz(iso_utc: str, tz: str) -> datetime:
    """Parse an ISO UTC string (``Z`` or ``+00:00``) and convert to the given zone."""
    text = iso_utc.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz))


def day_range(start: date_type, end: date_type) -> list[date_type]:
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]
