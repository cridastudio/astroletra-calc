"""Short Spanish data sentences for the sign endpoints (``highlights`` and event ``label``).

They state facts only (positions, houses, times, dates); interpretation is left to
the client. Neutral Spanish for Spain and Latin America, second
person singular. Every time carries its city ("ninguna hora sin su ciudad").
"""

from __future__ import annotations

from datetime import datetime

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


def date_es(when: datetime) -> str:
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
