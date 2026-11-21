"""Request and response models."""

from __future__ import annotations

import re
import unicodedata
from datetime import date as date_type
from typing import ClassVar, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

HouseSystem = Literal["P", "K", "W", "R", "C", "E", "O", "B", "M"]


class BirthData(BaseModel):
    """Birth (or event) data. ``time`` is local wall-clock time in ``tz``; ``None`` means unknown."""

    date: date_type
    time: str | None = Field(default=None, description="HH:MM local time, or null when unknown")
    lat: float = Field(ge=-89.9, le=89.9)
    lon: float = Field(ge=-180.0, le=180.0)
    tz: str = Field(description="IANA time zone, e.g. Europe/Madrid")
    house_system: HouseSystem = "P"

    @field_validator("time")
    @classmethod
    def _check_time(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        if not _TIME_RE.match(v):
            raise ValueError("time must be HH:MM (24 h) or null")
        return v

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown time zone: {v}") from exc
        return v

    @field_validator("date")
    @classmethod
    def _check_date_range(cls, v: date_type) -> date_type:
        # Bundled ephemeris (libephemeris base core) covers 1850-2150.
        if v.year < 1850 or v.year > 2149:
            raise ValueError("date must be between 1850 and 2149")
        return v


class Location(BaseModel):
    lat: float = Field(ge=-89.9, le=89.9)
    lon: float = Field(ge=-180.0, le=180.0)
    tz: str

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown time zone: {v}") from exc
        return v


class SynastryRequest(BaseModel):
    a: BirthData
    b: BirthData


class SolarReturnRequest(BaseModel):
    natal: BirthData
    year: int = Field(ge=1850, le=2149)
    location: Location


class TransitsRequest(BaseModel):
    natal: BirthData
    from_: date_type = Field(alias="from")
    to: date_type

    model_config = {"populate_by_name": True}

    @field_validator("to")
    @classmethod
    def _check_range(cls, v: date_type, info):  # type: ignore[no-untyped-def]
        start = info.data.get("from_")
        if start is not None:
            if v <= start:
                raise ValueError("'to' must be after 'from'")
            if (v - start).days > 400:
                raise ValueError("range must be 400 days or less")
        return v


class ForcedCard(BaseModel):
    card_id: str = Field(max_length=40)
    reversed: bool = False


class TarotDrawRequest(BaseModel):
    spread: Literal["three", "celtic"]
    seed: str | None = Field(default=None, max_length=128)
    lang: Literal["es", "en", "ca"] = "es"
    # Optional: reproduce a known draw (tests, sample PDFs). One entry per position.
    cards: list[ForcedCard] | None = Field(default=None, max_length=10)


class PdfRequest(BaseModel):
    html: str = Field(min_length=1)
    base_url: str | None = None


# ----------------------------------------------------------------------- sky

SIGN_NAME_LIST = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _check_tz_value(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"unknown time zone: {v}") from exc
    return v


def _check_year(v: date_type) -> date_type:
    if v.year < 1850 or v.year > 2149:
        raise ValueError("date must be between 1850 and 2149")
    return v


class DateRangeRequest(BaseModel):
    """Inclusive date range. Subclasses set ``max_days``."""

    MAX_DAYS: ClassVar[int] = 1100

    from_: date_type = Field(alias="from")
    to: date_type

    model_config = {"populate_by_name": True}

    @field_validator("from_")
    @classmethod
    def _check_from(cls, v: date_type) -> date_type:
        return _check_year(v)

    @field_validator("to")
    @classmethod
    def _check_to(cls, v: date_type, info):  # type: ignore[no-untyped-def]
        _check_year(v)
        start = info.data.get("from_")
        if start is not None:
            if v < start:
                raise ValueError("'to' must not be before 'from'")
            if (v - start).days > cls.MAX_DAYS:
                raise ValueError(f"range must be {cls.MAX_DAYS} days or less")
        return v


class LunationsRequest(DateRangeRequest):
    tz: str = Field(default="UTC", description="IANA zone for the local date-times")

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        return _check_tz_value(v)


class RetrogradesRequest(DateRangeRequest):
    planets: list[Literal["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]] | None = None
    shadow: bool = Field(default=True, description="Compute pre/post shadow dates")


class TodayRequest(BaseModel):
    date: date_type
    tz: str = Field(default="UTC", description="IANA zone of the visitor")

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: date_type) -> date_type:
        return _check_year(v)

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        return _check_tz_value(v)


# Spanish names (and their slugs) are accepted too, so the portal can pass its own slugs.
_SIGN_ALIASES: dict[str, str] = {
    "tauro": "Taurus", "geminis": "Gemini", "cancer": "Cancer", "escorpio": "Scorpio", "escorpion": "Scorpio",
    "sagitario": "Sagittarius", "capricornio": "Capricorn", "acuario": "Aquarius", "piscis": "Pisces",
}


def _fold(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.strip().lower()) if unicodedata.category(c) != "Mn")


def parse_sign(v: str) -> str:
    """English sign name (any case), sign_num 0-11 as text, or the Spanish name/slug."""
    text = _fold(v)
    if text.isdigit() and 0 <= int(text) <= 11:
        return SIGN_NAME_LIST[int(text)]
    for name in SIGN_NAME_LIST:
        if name.lower() == text:
            return name
    if text in _SIGN_ALIASES:
        return _SIGN_ALIASES[text]
    raise ValueError(f"unknown sign: {v}")


class SignRequest(BaseModel):
    sign: str = Field(description="English sign name (Taurus), sign_num 0-11 as string or Spanish name (tauro)")
    tz: str = Field(default="UTC", description="IANA zone for the local date-times")

    @field_validator("sign")
    @classmethod
    def _check_sign(cls, v: str) -> str:
        return parse_sign(v)

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str) -> str:
        return _check_tz_value(v)

    @property
    def sign_num(self) -> int:
        return SIGN_NAME_LIST.index(self.sign)


class SignYearRequest(SignRequest):
    year: int = Field(ge=1850, le=2149)


class SignDayRequest(SignRequest):
    date: date_type

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: date_type) -> date_type:
        return _check_year(v)


class SignWeekRequest(SignRequest):
    from_: date_type = Field(alias="from", description="First day of the 7-day period (the portal uses Mondays)")

    model_config = {"populate_by_name": True}

    @field_validator("from_")
    @classmethod
    def _check_from(cls, v: date_type) -> date_type:
        _check_year(v)
        if v.year == 2149 and v.month == 12 and v.day > 25:
            raise ValueError("date must be between 1850 and 2149")
        return v


class SignMonthRequest(SignRequest):
    year: int = Field(ge=1850, le=2149)
    month: int = Field(ge=1, le=12)


class SolarReturnNextRequest(BaseModel):
    natal: BirthData
    after: date_type | None = Field(default=None, description="Search from this date (default: today in the natal zone)")
    tz: str | None = Field(default=None, description="Zone for the local date-time (default: natal zone)")

    @field_validator("after")
    @classmethod
    def _check_after(cls, v: date_type | None) -> date_type | None:
        return _check_year(v) if v is not None else None

    @field_validator("tz")
    @classmethod
    def _check_tz(cls, v: str | None) -> str | None:
        return _check_tz_value(v) if v is not None else None
