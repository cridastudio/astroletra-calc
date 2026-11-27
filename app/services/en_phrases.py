"""Short English data sentences for the sign endpoints (``highlights`` and event ``label``).

Same public functions as ``es_phrases``. Facts only (positions, houses, times, dates),
second person, and every time carries its city: "at 23:39 (Madrid time)",
"at 9:00 (UTC)". Dates are written day first ("3 October"), 24-hour clock.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

from app.services.es_phrases import degree  # 15°02': the same notation in both languages

SIGN_EN: dict[str, str] = {
    name: name
    for name in (
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    )
}

PLANET_EN: dict[str, str] = {
    name: name
    for name in ("Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto")
}

# Aspect name with its indefinite article.
ASPECT_EN: dict[str, str] = {
    "conjunction": "a conjunction",
    "sextile": "a sextile",
    "square": "a square",
    "trine": "a trine",
    "opposition": "an opposition",
}

MONTHS_EN = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

# City named after each time. Zones not listed fall back to the last part of the IANA name.
ZONE_CITY_EN: dict[str, str] = {
    "UTC": "UTC",
    "Etc/UTC": "UTC",
    "Europe/Madrid": "Madrid",
    "Atlantic/Canary": "Canary Islands",
    "America/Mexico_City": "Mexico City",
    "America/Monterrey": "Monterrey",
    "America/Cancun": "Cancún",
    "America/Tijuana": "Tijuana",
    "America/Argentina/Buenos_Aires": "Buenos Aires",
    "America/Buenos_Aires": "Buenos Aires",
    "America/Bogota": "Bogotá",
    "America/Santiago": "Santiago",
    "America/Lima": "Lima",
    "America/Caracas": "Caracas",
    "America/Montevideo": "Montevideo",
    "America/Asuncion": "Asunción",
    "America/La_Paz": "La Paz",
    "America/Guayaquil": "Guayaquil",
    "America/Panama": "Panama City",
    "America/Costa_Rica": "San José",
    "America/Guatemala": "Guatemala City",
    "America/El_Salvador": "San Salvador",
    "America/Tegucigalpa": "Tegucigalpa",
    "America/Managua": "Managua",
    "America/Santo_Domingo": "Santo Domingo",
    "America/Havana": "Havana",
    "America/Puerto_Rico": "San Juan",
    "America/New_York": "New York",
    "America/Los_Angeles": "Los Angeles",
    "America/Chicago": "Chicago",
    "Europe/London": "London",
}

# Moon phase names as Kerykeion gives them -> English wording.
_PHASE_EN: dict[str, str] = {
    "New Moon": "New Moon",
    "Waxing Crescent": "Waxing crescent Moon",
    "First Quarter": "First quarter Moon",
    "Waxing Gibbous": "Waxing gibbous Moon",
    "Full Moon": "Full Moon",
    "Waning Gibbous": "Waning gibbous Moon",
    "Last Quarter": "Last quarter Moon",
    "Third Quarter": "Last quarter Moon",
    "Waning Crescent": "Waning crescent Moon",
}

_ECLIPSE_KIND = {"total": "Total", "annular": "Annular", "partial": "Partial", "penumbral": "Penumbral", "hybrid": "Hybrid"}


def city_of(tz: str) -> str:
    if tz in ZONE_CITY_EN:
        return ZONE_CITY_EN[tz]
    return tz.rsplit("/", 1)[-1].replace("_", " ")


def planet(name: str, *, capital: bool = True) -> str:
    """Planet name, with the article the Sun and the Moon take."""
    base = PLANET_EN[name]
    if name in ("Sun", "Moon"):
        return f"{'The' if capital else 'the'} {base}"
    return base


def sign(name: str) -> str:
    return SIGN_EN[name]


def ordinal(n: int) -> str:
    """1 -> 1st, 2 -> 2nd, 11 -> 11th, 12 -> 12th."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def house(n: int) -> str:
    return f"your {ordinal(n)} house"


def point(key: str) -> str:
    """Sensitive point of the sign: '0', '15' or '30'."""
    return {"0": "the 0° point of your sign", "15": "the 15° point of your sign", "30": "the 30° point of your sign"}[key]


def ruler(name: str) -> str:
    """'Mars, your ruler', 'the Moon, your ruler'."""
    return f"{planet(name, capital=False)}, your ruler"


def date_text(when: date | datetime) -> str:
    """'3 October'."""
    return f"{when.day} {MONTHS_EN[when.month - 1]}"


def time_text(when: datetime, tz: str) -> str:
    """'at 23:39 (Madrid time)', 'at 1:05 (Bogotá time)', 'at 9:00 (UTC)'."""
    city = city_of(tz)
    suffix = "(UTC)" if city == "UTC" else f"({city} time)"
    return f"at {when.hour}:{when.minute:02d} {suffix}"


def when_text(when: datetime, tz: str, *, with_date: bool) -> str:
    return f"on {date_text(when)} {time_text(when, tz)}" if with_date else time_text(when, tz)


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# --------------------------------------------------------------------------- sentences


def moon_ingress(sign_name: str, house_num: int, when: datetime, tz: str, *, with_date: bool) -> str:
    return f"The Moon enters {sign(sign_name)}, {house(house_num)}, {when_text(when, tz, with_date=with_date)}."


def planet_ingress(name: str, sign_name: str, house_num: int, when: datetime, tz: str, *, retrograde: bool, with_date: bool) -> str:
    # Only Mercury to Pluto go retrograde, so the article of the Sun and the Moon never follows.
    subject = f"Retrograde {planet(name, capital=False)}" if retrograde else planet(name)
    return f"{subject} enters {sign(sign_name)}, {house(house_num)}, {when_text(when, tz, with_date=with_date)}."


def lunation(
    phase: str,
    in_sign: float,
    sign_name: str,
    house_num: int,
    when: datetime,
    tz: str,
    *,
    with_date: bool,
    eclipse_type: str | None = None,
    eclipse_kind: str | None = None,
) -> str:
    """New or full Moon, or the eclipse that comes with it (``eclipse_type`` solar/lunar)."""
    where = f"at {degree(in_sign)} {sign(sign_name)}, in {house(house_num)}"
    if eclipse_type:
        kind = _ECLIPSE_KIND.get(eclipse_kind or "", cap(eclipse_kind or ""))
        name = f"{kind} {'solar' if eclipse_type == 'solar' else 'lunar'} eclipse"
    else:
        name = "New Moon" if phase == "new" else "Full Moon"
    return f"{name} {where}, {when_text(when, tz, with_date=with_date)}."


def station(name: str, direction: str, in_sign: float, sign_name: str, house_num: int, when: datetime, tz: str, *, with_date: bool) -> str:
    """``direction``: ``retrograde`` or ``direct``."""
    word = "retrograde" if direction == "retrograde" else "direct"
    return (
        f"{planet(name)} stations {word} at {degree(in_sign)} {sign(sign_name)}, "
        f"in {house(house_num)}, {when_text(when, tz, with_date=with_date)}."
    )


def aspect_exact(name: str, aspect: str, target: str, when: datetime, tz: str, *, with_date: bool, to_ruler: bool) -> str:
    """``target`` comes from :func:`point` or :func:`ruler`."""
    comma = "," if to_ruler else ""
    return f"{planet(name)} forms an exact {aspect} with {target}{comma} {when_text(when, tz, with_date=with_date)}."


def aspect_near(name: str, aspect: str, target: str, minutes: int) -> str:
    """An aspect that stays within orb all day without perfecting."""
    return f"{planet(name)} is in {ASPECT_EN[aspect]} with {target}, {minutes}' from exact."


def sky_aspect(p1: str, house1: int, aspect: str, p2: str, house2: int, when: datetime, tz: str) -> str:
    return (
        f"{planet(p1)} ({house(house1)}) forms an exact {aspect} "
        f"with {planet(p2, capital=False)} ({house(house2)}) {when_text(when, tz, with_date=False)}."
    )


def moon_changes_sign(from_sign: str, from_house: int, sign_name: str, house_num: int, when: datetime, tz: str) -> str:
    return (
        f"The Moon moves from {sign(from_sign)} ({house(from_house)}) "
        f"to {sign(sign_name)} ({house(house_num)}) {time_text(when, tz)}."
    )


def moon_all_day(sign_name: str, house_num: int, next_sign: str, next_house: int, when: datetime, tz: str) -> str:
    return (
        f"The Moon is in {sign(sign_name)} ({house(house_num)}) all day "
        f"and enters {sign(next_sign)} ({house(next_house)}) {when_text(when, tz, with_date=True)}."
    )


def moon_in_sign(sign_name: str, house_num: int) -> str:
    return f"The Moon is in {sign(sign_name)} ({house(house_num)})."


def sun_position(in_sign: float, sign_name: str, house_num: int) -> str:
    return f"The Sun is at {degree(in_sign)} {sign(sign_name)}, in {house(house_num)}."


def sun_through(sign_name: str, house_num: int, period: str) -> str:
    """``period``: ``week`` or ``month``."""
    span = "all week" if period == "week" else "all month"
    return f"The Sun moves through {sign(sign_name)} ({house(house_num)}) {span}."


def moon_phase(stage: str | None, illumination: float, name: str | None = None) -> str:
    """Phase name (waxing gibbous...) and lit fraction of the disc."""
    label = _PHASE_EN.get(name or "") or ("Waxing Moon" if stage == "waxing" else "Waning Moon")
    return f"{label}, with {round(illumination * 100)}% of the disc illuminated."


def retrogrades(periods: Sequence[dict[str, Any]]) -> str | None:
    """One sentence for the retrograde periods that affect the sign (``planet``, ``signs``,
    ``houses``, ``since`` and ``until`` as ISO dates); ``None`` when there are none."""
    parts = []
    for p in periods:
        sign_txt = " and ".join(sign(s) for s in p["signs"])
        ordinals = " and ".join(ordinal(h) for h in p["houses"])
        house_txt = f"your {ordinals} house" if len(p["houses"]) == 1 else f"your {ordinals} houses"
        since = date_text(date.fromisoformat(p["since"]))
        until = date_text(date.fromisoformat(p["until"]))
        parts.append(f"{planet(p['planet'])} is retrograde in {sign_txt} ({house_txt}) from {since} to {until}")
    if not parts:
        return None
    return f"{'; '.join(parts)}."
