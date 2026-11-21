"""Short Spanish data sentences for the sign endpoints (``highlights`` and event ``label``).

They state facts only (positions, houses, times, dates); interpretation is left to
the client. Neutral Spanish for Spain and Latin America, second
person singular. Every time carries its city ("ninguna hora sin su ciudad").

``en_phrases`` has the same public functions in English; ``sign_sky`` picks the module
with the ``lang`` of the request. Sign, planet and aspect names come in as the English
identifiers used in the JSON (``Scorpio``, ``Mars``, ``square``).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Any

SIGN_ES: dict[str, str] = {
    "Aries": "Aries", "Taurus": "Tauro", "Gemini": "Géminis", "Cancer": "Cáncer",
    "Leo": "Leo", "Virgo": "Virgo", "Libra": "Libra", "Scorpio": "Escorpio",
    "Sagittarius": "Sagitario", "Capricorn": "Capricornio", "Aquarius": "Acuario", "Pisces": "Piscis",
}

PLANET_ES: dict[str, str] = {
    "Sun": "Sol", "Moon": "Luna", "Mercury": "Mercurio", "Venus": "Venus", "Mars": "Marte",
    "Jupiter": "Júpiter", "Saturn": "Saturno", "Uranus": "Urano", "Neptune": "Neptuno", "Pluto": "Plutón",
}

# Aspect name with its indefinite article (gender matters in Spanish).
ASPECT_ES: dict[str, str] = {
    "conjunction": "una conjunción",
    "sextile": "un sextil",
    "square": "una cuadratura",
    "trine": "un trígono",
    "opposition": "una oposición",
}

MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

# City named after each time. Zones not listed fall back to the last part of the IANA name.
ZONE_CITY_ES: dict[str, str] = {
    "UTC": "UTC",
    "Etc/UTC": "UTC",
    "Europe/Madrid": "Madrid",
    "Atlantic/Canary": "Canarias",
    "America/Mexico_City": "Ciudad de México",
    "America/Monterrey": "Monterrey",
    "America/Cancun": "Cancún",
    "America/Tijuana": "Tijuana",
    "America/Argentina/Buenos_Aires": "Buenos Aires",
    "America/Buenos_Aires": "Buenos Aires",
    "America/Bogota": "Bogotá",
    "America/Santiago": "Santiago de Chile",
    "America/Lima": "Lima",
    "America/Caracas": "Caracas",
    "America/Montevideo": "Montevideo",
    "America/Asuncion": "Asunción",
    "America/La_Paz": "La Paz",
    "America/Guayaquil": "Guayaquil",
    "America/Panama": "Panamá",
    "America/Costa_Rica": "San José de Costa Rica",
    "America/Guatemala": "Ciudad de Guatemala",
    "America/El_Salvador": "San Salvador",
    "America/Tegucigalpa": "Tegucigalpa",
    "America/Managua": "Managua",
    "America/Santo_Domingo": "Santo Domingo",
    "America/Havana": "La Habana",
    "America/Puerto_Rico": "San Juan de Puerto Rico",
    "America/New_York": "Nueva York",
    "America/Los_Angeles": "Los Ángeles",
    "America/Chicago": "Chicago",
    "Europe/London": "Londres",
}


def city_of(tz: str) -> str:
    if tz in ZONE_CITY_ES:
        return ZONE_CITY_ES[tz]
    return tz.rsplit("/", 1)[-1].replace("_", " ")


def planet(name: str, *, capital: bool = True) -> str:
    """Planet name with the article the Sun and the Moon take in Spanish."""
    base = PLANET_ES[name]
    if name in ("Sun", "Moon"):
        article = "El" if name == "Sun" else "La"
        return f"{article if capital else article.lower()} {base}"
    return base


def sign(name: str) -> str:
    return SIGN_ES[name]


def degree(in_sign: float) -> str:
    """15.04 -> 15°02'."""
    total = round(in_sign * 60)
    deg, minutes = divmod(total, 60)
    if deg >= 30:
        deg, minutes = 29, 59
    return f"{deg}°{minutes:02d}'"


def date_es(when: date | datetime) -> str:
    return f"{when.day} de {MONTHS_ES[when.month - 1]}"


def time_es(when: datetime, tz: str) -> str:
    """'a las 23:39 (hora de Madrid)', 'a la 1:05 (hora de Bogotá)', 'a las 9:00 (UTC)'."""
    clock = f"{when.hour}:{when.minute:02d}"
    lead = "a la" if when.hour == 1 else "a las"
    city = city_of(tz)
    suffix = "(UTC)" if city == "UTC" else f"(hora de {city})"
    return f"{lead} {clock} {suffix}"


def when_es(when: datetime, tz: str, *, with_date: bool) -> str:
    return f"el {date_es(when)} {time_es(when, tz)}" if with_date else time_es(when, tz)


def house(n: int) -> str:
    return f"tu casa {n}"


def point(key: str) -> str:
    return {"0": "el grado 0 de tu signo", "15": "el grado 15 de tu signo", "30": "el grado 30 de tu signo"}[key]


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


# Language-neutral names of the helpers above (``en_phrases`` defines the same ones).
date_text = date_es
time_text = time_es
when_text = when_es


def ruler(name: str) -> str:
    """'Marte, tu regente', 'la Luna, tu regente'."""
    return f"{planet(name, capital=False)}, tu regente"


# --------------------------------------------------------------------------- sentences

_EXACT = {"sextile": "exacto", "trine": "exacto"}  # the other three aspects are feminine
_ECLIPSE_KIND = {"total": "total", "annular": "anular", "partial": "parcial", "penumbral": "penumbral", "hybrid": "híbrido"}


def moon_ingress(sign_name: str, house_num: int, when: datetime, tz: str, *, with_date: bool) -> str:
    return f"La Luna entra en {sign(sign_name)}, {house(house_num)}, {when_es(when, tz, with_date=with_date)}."


def planet_ingress(name: str, sign_name: str, house_num: int, when: datetime, tz: str, *, retrograde: bool, with_date: bool) -> str:
    retro = " retrógrado" if retrograde else ""
    return f"{planet(name)}{retro} entra en {sign(sign_name)}, {house(house_num)}, {when_es(when, tz, with_date=with_date)}."


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
    where = f"a {degree(in_sign)} de {sign(sign_name)}, en {house(house_num)}"
    if eclipse_type:
        kind = _ECLIPSE_KIND.get(eclipse_kind or "", eclipse_kind)
        name = f"Eclipse {'solar' if eclipse_type == 'solar' else 'lunar'} {kind}"
    else:
        name = "Luna nueva" if phase == "new" else "Luna llena"
    return f"{name} {where}, {when_es(when, tz, with_date=with_date)}."


def station(name: str, direction: str, in_sign: float, sign_name: str, house_num: int, when: datetime, tz: str, *, with_date: bool) -> str:
    """``direction``: ``retrograde`` or ``direct``."""
    word = "retrógrado" if direction == "retrograde" else "directo"
    return (
        f"{planet(name)} se estaciona {word} a {degree(in_sign)} de {sign(sign_name)}, "
        f"en {house(house_num)}, {when_es(when, tz, with_date=with_date)}."
    )


def aspect_exact(name: str, aspect: str, target: str, when: datetime, tz: str, *, with_date: bool, to_ruler: bool) -> str:
    """``target`` comes from :func:`point` or :func:`ruler`."""
    comma = "," if to_ruler else ""
    return f"{planet(name)} forma {ASPECT_ES[aspect]} {_EXACT.get(aspect, 'exacta')} con {target}{comma} {when_es(when, tz, with_date=with_date)}."


def aspect_near(name: str, aspect: str, target: str, minutes: int) -> str:
    """An aspect that stays within orb all day without perfecting."""
    return f"{planet(name)} mantiene {ASPECT_ES[aspect]} con {target}, a {minutes}' del exacto."


def sky_aspect(p1: str, house1: int, aspect: str, p2: str, house2: int, when: datetime, tz: str) -> str:
    return (
        f"{planet(p1)} ({house(house1)}) forma {ASPECT_ES[aspect]} {_EXACT.get(aspect, 'exacta')} "
        f"con {planet(p2, capital=False)} ({house(house2)}) {when_es(when, tz, with_date=False)}."
    )


def moon_changes_sign(from_sign: str, from_house: int, sign_name: str, house_num: int, when: datetime, tz: str) -> str:
    return (
        f"La Luna pasa de {sign(from_sign)} ({house(from_house)}) "
        f"a {sign(sign_name)} ({house(house_num)}) {time_es(when, tz)}."
    )


def moon_all_day(sign_name: str, house_num: int, next_sign: str, next_house: int, when: datetime, tz: str) -> str:
    return (
        f"La Luna está en {sign(sign_name)} ({house(house_num)}) todo el día "
        f"y entra en {sign(next_sign)} ({house(next_house)}) {when_es(when, tz, with_date=True)}."
    )


def moon_in_sign(sign_name: str, house_num: int) -> str:
    return f"La Luna está en {sign(sign_name)} ({house(house_num)})."


def sun_position(in_sign: float, sign_name: str, house_num: int) -> str:
    return f"El Sol está a {degree(in_sign)} de {sign(sign_name)}, en {house(house_num)}."


def sun_through(sign_name: str, house_num: int, period: str) -> str:
    """``period``: ``week`` or ``month``."""
    span = "toda la semana" if period == "week" else "todo el mes"
    return f"El Sol recorre {sign(sign_name)} ({house(house_num)}) {span}."


def moon_phase(stage: str | None, illumination: float, name: str | None = None) -> str:
    """Waxing or waning Moon and its lit fraction (``name`` is not used in Spanish)."""
    word = "creciente" if stage == "waxing" else "menguante"
    return f"Luna {word}, con el {round(illumination * 100)} % del disco iluminado."


def retrogrades(periods: Sequence[dict[str, Any]]) -> str | None:
    """One sentence for the retrograde periods that affect the sign (``planet``, ``signs``,
    ``houses``, ``since`` and ``until`` as ISO dates); ``None`` when there are none."""
    parts = []
    for p in periods:
        sign_txt = " y ".join(sign(s) for s in p["signs"])
        houses = " y ".join(str(h) for h in p["houses"])
        house_txt = f"tu casa {houses}" if len(p["houses"]) == 1 else f"tus casas {houses}"
        since = date_es(date.fromisoformat(p["since"]))
        until = date_es(date.fromisoformat(p["until"]))
        parts.append(f"{planet(p['planet'])} en {sign_txt} ({house_txt}), del {since} al {until}")
    if not parts:
        return None
    plural = len(parts) > 1
    return f"Retrógrado{'s' if plural else ''} que te afecta{'n' if plural else ''}: {'; '.join(parts)}."
