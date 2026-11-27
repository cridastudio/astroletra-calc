"""English sentences of /v1/sign-day, /v1/sign-week and /v1/sign-month (``lang: "en"``).

Same cases and reference instants as test_sign_sky.py (see its docstring for the
independent cross-checks); only the language of ``label``, ``highlights`` and ``city``
changes, the data is identical.
"""

from __future__ import annotations

import inspect
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services import en_phrases as en
from app.services import es_phrases as es


def _post(client, headers, path, body):
    r = client.post(path, json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


TIME_RE = re.compile(r"at \d{1,2}:\d{2}(?P<after>[^.;]*)")


def _times_have_city(sentences, city):
    for s in sentences:
        assert TIME_RE.search(s) or not re.search(r"\d:\d\d", s), s
        for m in TIME_RE.finditer(s):
            assert m.group("after").startswith(f" ({city} time)"), s


def _sentences(body):
    """Every sentence of a response: highlights and the labels of all its events."""
    out = list(body["highlights"])
    featured = body["featured"]
    for e in [*(featured if isinstance(featured, list) else [featured] if featured else []), *body["events"]]:
        out.append(e["label"])
    for key in ("aspects_to_sign", "aspects_to_ruler", "sky_aspects", "moon_ingresses", "lunations"):
        out.extend(e["label"] for e in body.get(key, []))
    return out


def _without_text(body):
    """The response with the language-dependent fields taken out."""
    if isinstance(body, dict):
        return {k: _without_text(v) for k, v in body.items() if k not in ("label", "highlights", "city")}
    if isinstance(body, list):
        return [_without_text(v) for v in body]
    return body


# Spanish words that never belong in an English sentence (whole words, any case).
_ES_WORDS = {
    "de", "del", "en", "el", "la", "las", "los", "tu", "tus", "y", "con", "al",
    "casa", "casas", "hora", "grado", "signo", "regente", "forma", "entra", "pasa", "está", "recorre",
    "mantiene", "estaciona", "exacto", "exacta", "retrógrado", "retrógrados", "directo", "creciente",
    "menguante", "disco", "iluminado", "nueva", "llena", "semana", "mes", "todo", "toda", "día",
    "afecta", "afectan", "anular", "parcial", "híbrido",
    "conjunción", "cuadratura", "oposición", "trígono", "sextil",
}
_ES_WORDS |= {w.lower() for w in es.MONTHS_ES}
_ES_WORDS |= {v.lower() for k, v in {**es.SIGN_ES, **es.PLANET_ES}.items() if k != v}
_ES_WORD_RE = re.compile(r"\b(" + "|".join(sorted(map(re.escape, _ES_WORDS), key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _assert_english(sentences):
    for s in sentences:
        found = _ES_WORD_RE.findall(s)
        assert not found, (found, s)
        assert "tu casa" not in s and "hora de" not in s and " % " not in s, s
        assert s.endswith("."), s


# ----------------------------------------------------------------------------- sign-day


@pytest.fixture(scope="module")
def scorpio_day_en(client, headers):
    return _post(client, headers, "/v1/sign-day", {"sign": "Scorpio", "date": "2026-11-07", "tz": "Europe/Madrid", "lang": "en"})


@pytest.fixture(scope="module")
def scorpio_day_es(client, headers):
    return _post(client, headers, "/v1/sign-day", {"sign": "Scorpio", "date": "2026-11-07", "tz": "Europe/Madrid"})


def test_sign_day_en_moon_enters_scorpio_at_23_39_madrid(scorpio_day_en, scorpio_day_es):
    body = scorpio_day_en
    assert body["sign"] == "Scorpio" and body["sign_num"] == 7 and body["city"] == "Madrid"
    change = body["moon"]["next_sign_change"]
    assert (change["from_sign"], change["sign"], change["datetime_local"]) == ("Libra", "Scorpio", "2026-11-07T23:39+01:00")
    # Only the sentences and the city change with the language.
    assert _without_text(body) == _without_text(scorpio_day_es)


def test_sign_day_en_featured_and_highlights(scorpio_day_en):
    featured = scorpio_day_en["featured"]
    assert featured["kind"] == "moon_ingress" and featured["time_local"] == "23:39"
    assert featured["label"] == "The Moon enters Scorpio, your 1st house, at 23:39 (Madrid time)."
    highlights = scorpio_day_en["highlights"]
    assert 3 <= len(highlights) <= 5 and len(set(highlights)) == len(highlights)
    assert highlights[0] == "The Moon moves from Libra (your 12th house) to Scorpio (your 1st house) at 23:39 (Madrid time)."
    assert "The Sun forms an exact conjunction with the 15° point of your sign at 10:52 (Madrid time)." in highlights
    assert highlights[3] == (
        "Venus is retrograde in Scorpio and Libra (your 1st and 12th houses) from 3 October to 14 November; "
        "Mercury is retrograde in Scorpio (your 1st house) from 24 October to 13 November."
    )
    assert highlights[4] == "The Sun is at 15°03' Scorpio, in your 1st house."
    _times_have_city(highlights, "Madrid")
    _assert_english(_sentences(scorpio_day_en))


def test_sign_day_en_aspects_to_points_and_ruler(scorpio_day_en):
    sextile = next(a for a in scorpio_day_en["aspects_to_ruler"] if a["planet"] == "Moon")
    assert sextile["label"] == "The Moon forms an exact sextile with Mars, your ruler, at 8:01 (Madrid time)."
    moon0 = next(a for a in scorpio_day_en["aspects_to_sign"] if a["planet"] == "Moon" and a["point"] == "0")
    assert moon0["label"] == "The Moon forms an exact conjunction with the 0° point of your sign at 23:39 (Madrid time)."


def test_sign_day_en_other_zone(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "escorpio", "date": "2026-11-07", "tz": "America/Mexico_City", "lang": "en"})
    assert body["sign"] == "Scorpio" and body["city"] == "Mexico City"
    assert body["featured"]["label"] == "The Moon enters Scorpio, your 1st house, at 16:39 (Mexico City time)."
    _times_have_city(body["highlights"], "Mexico City")
    _assert_english(_sentences(body))


def test_sign_day_en_stations(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "Leo", "date": "2026-11-13", "tz": "America/Argentina/Buenos_Aires", "lang": "en"})
    stations = [e for e in body["events"] if e["kind"] == "station"]
    assert [e["label"] for e in stations] == [
        "Mercury stations direct at 5°02' Scorpio, in your 4th house, at 12:53 (Buenos Aires time).",
        "Venus stations direct at 22°52' Libra, in your 3rd house, at 21:27 (Buenos Aires time).",
    ]
    assert body["featured"]["planet"] == "Mercury" and body["featured"]["kind"] == "station"
    assert body["highlights"][0].startswith(
        "The Moon is in Capricorn (your 6th house) all day and enters Aquarius (your 7th house) on 15 November at "
    )
    _times_have_city(body["highlights"], "Buenos Aires")
    _assert_english(_sentences(body))


def test_sign_day_en_full_moon_for_cancer(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "Cancer", "date": "2026-11-24", "tz": "Europe/Madrid", "lang": "en"})
    lunation = next(e for e in body["events"] if e["kind"] == "lunation")
    assert lunation["phase"] == "full" and lunation["time_local"] == "15:53"
    assert lunation["label"] == "Full Moon at 2°20' Gemini, in your 12th house, at 15:53 (Madrid time)."
    ruler = [e["label"] for e in body["events"] if e["kind"] == "aspect_to_ruler"]
    assert ruler[0] == "Jupiter forms an exact square with the Moon, your ruler, at 6:28 (Madrid time)."
    assert body["featured"]["label"] == lunation["label"]
    _assert_english(_sentences(body))


def test_sign_day_en_quiet_day_features_the_sky_aspect(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "Aries", "date": "2026-11-08", "tz": "Europe/Madrid", "lang": "en"})
    assert body["events"] == []
    featured = body["featured"]
    assert featured["label"] == "The Moon (your 8th house) forms an exact conjunction with Mercury (your 8th house) at 14:01 (Madrid time)."
    assert body["highlights"] == [
        "The Moon is in Scorpio (your 8th house) all day and enters Sagittarius (your 9th house) on 10 November at 9:35 (Madrid time).",
        featured["label"],
        "Neptune is retrograde in Aries (your 1st house) from 7 July to 12 December; "
        "Saturn is retrograde in Aries (your 1st house) from 26 July to 11 December.",
        "The Sun is at 16°03' Scorpio, in your 8th house.",
        "Waning crescent Moon, with 1% of the disc illuminated.",
    ]
    _assert_english(_sentences(body))


def test_sign_day_en_utc_and_validation(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "7", "date": "2026-11-07", "lang": "en"})
    assert body["tz"] == "UTC" and body["city"] == "UTC"
    assert body["featured"]["label"] == "The Moon enters Scorpio, your 1st house, at 22:39 (UTC)."
    for lang in ("fr", "EN", "", None):
        bad = {"sign": "Leo", "date": "2026-11-07", "lang": lang}
        assert client.post("/v1/sign-day", json=bad, headers=headers).status_code == 422


def test_without_lang_everything_stays_in_spanish(client, headers, scorpio_day_es):
    body = {"sign": "Scorpio", "date": "2026-11-07", "tz": "Europe/Madrid"}
    assert _post(client, headers, "/v1/sign-day", {**body, "lang": "es"}) == scorpio_day_es
    assert scorpio_day_es["city"] == "Madrid"
    assert scorpio_day_es["featured"]["label"] == "La Luna entra en Escorpio, tu casa 1, a las 23:39 (hora de Madrid)."
    week = {"sign": "Scorpio", "from": "2026-11-09", "tz": "America/Mexico_City"}
    default = _post(client, headers, "/v1/sign-week", week)
    assert default == _post(client, headers, "/v1/sign-week", {**week, "lang": "es"})
    assert default["city"] == "Ciudad de México"
    assert "El Sol recorre Escorpio (tu casa 1) toda la semana." in default["highlights"]


# ----------------------------------------------------------------------------- sign-week


def test_sign_week_en_scorpio(client, headers):
    body = _post(client, headers, "/v1/sign-week", {"sign": "Scorpio", "from": "2026-11-09", "tz": "Europe/Madrid", "lang": "en"})
    featured = body["featured"]
    assert featured[0]["kind"] == "lunation" and featured[0]["phase"] == "new"
    assert featured[0]["label"] == "New Moon at 16°53' Scorpio, in your 1st house, on 9 November at 8:02 (Madrid time)."
    venus = next(e for e in body["events"] if e["kind"] == "station" and e["planet"] == "Venus")
    assert venus["label"].endswith("on 14 November at 1:27 (Madrid time).")
    assert all(e["label"].startswith("The Moon enters ") for e in body["moon_ingresses"])
    assert "The Sun moves through Scorpio (your 1st house) all week." in body["highlights"]
    _times_have_city(body["highlights"], "Madrid")
    _assert_english(_sentences(body))


# ----------------------------------------------------------------------------- sign-month


def test_sign_month_en_scorpio_november_2026(client, headers):
    body = _post(client, headers, "/v1/sign-month", {"sign": "Scorpio", "year": 2026, "month": 11, "tz": "Europe/Madrid", "lang": "en"})
    sun_in = next(e for e in body["events"] if e["kind"] == "ingress" and e["planet"] == "Sun")
    assert sun_in["label"] == "The Sun enters Sagittarius, your 2nd house, on 22 November at 8:23 (Madrid time)."
    assert "The Moon enters Scorpio, your 1st house, on 7 November at 23:39 (Madrid time)." in body["highlights"]
    jupiter = next(a for a in body["aspects_to_ruler"] if a["planet"] == "Jupiter" and a["type"] == "conjunction")
    assert jupiter["label"] == "Jupiter forms an exact conjunction with Mars, your ruler, on 16 November at 7:23 (Madrid time)."
    assert body["highlights"][1] == "Mercury stations direct at 5°02' Scorpio, in your 1st house, on 13 November at 16:53 (Madrid time)."
    assert body["highlights"][2] == "Venus stations direct at 22°52' Libra, in your 12th house, on 14 November at 1:27 (Madrid time)."
    retro = next(h for h in body["highlights"] if "retrograde" in h)
    assert retro.startswith("Venus is retrograde in Scorpio and Libra (your 1st and 12th houses) from ")
    assert "; Mercury is retrograde in Scorpio (your 1st house) from 24 October to 13 November." in retro
    _times_have_city(body["highlights"], "Madrid")
    _assert_english(_sentences(body))


def test_sign_month_en_cancer_eclipses(client, headers):
    body = _post(client, headers, "/v1/sign-month", {"sign": "Cancer", "year": 2027, "month": 2, "tz": "America/Bogota", "lang": "en"})
    assert [e["label"] for e in body["events"] if e["kind"] == "eclipse"] == [
        "Annular solar eclipse at 17°38' Aquarius, in your 8th house, on 6 February at 10:56 (Bogotá time).",
        "Penumbral lunar eclipse at 2°05' Virgo, in your 3rd house, on 20 February at 18:23 (Bogotá time).",
    ]
    mercury = next(e for e in body["events"] if e["kind"] == "station" and e["planet"] == "Mercury")
    assert mercury["label"] == "Mercury stations retrograde at 5°59' Pisces, in your 9th house, on 9 February at 12:36 (Bogotá time)."
    assert body["city"] == "Bogotá"
    _times_have_city(body["highlights"], "Bogotá")
    _assert_english(_sentences(body))


@pytest.mark.parametrize("path,body", [
    ("/v1/sign-day", {"date": "2027-08-02", "tz": "Atlantic/Canary"}),
    ("/v1/sign-day", {"date": "2026-11-22", "tz": "America/Bogota"}),
    ("/v1/sign-week", {"from": "2027-02-01", "tz": "America/New_York"}),
    ("/v1/sign-month", {"year": 2027, "month": 8, "tz": "UTC"}),
])
@pytest.mark.parametrize("sign", ["Aries", "Gemini", "Virgo", "Sagittarius"])
def test_no_spanish_in_english_sentences(client, headers, path, body, sign):
    en_body = _post(client, headers, path, {**body, "sign": sign, "lang": "en"})
    es_body = _post(client, headers, path, {**body, "sign": sign})
    assert _without_text(en_body) == _without_text(es_body)
    _assert_english(_sentences(en_body))
    city = en.city_of(body["tz"])
    for s in en_body["highlights"]:
        for m in TIME_RE.finditer(s):
            assert m.group("after").startswith(" (UTC)" if city == "UTC" else f" ({city} time)"), s


# ----------------------------------------------------------------------------- units


def test_english_phrases():
    assert en.degree(15.04) == "15°02'"
    when = datetime(2026, 11, 14, 1, 27, tzinfo=ZoneInfo("Europe/Madrid"))
    assert en.time_text(when, "Europe/Madrid") == "at 1:27 (Madrid time)"
    assert en.when_text(when, "Europe/Madrid", with_date=True) == "on 14 November at 1:27 (Madrid time)"
    assert en.time_text(datetime(2026, 1, 1, 9, 0), "UTC") == "at 9:00 (UTC)"
    assert en.time_text(datetime(2026, 1, 1, 1, 5), "America/Bogota") == "at 1:05 (Bogotá time)"
    assert en.date_text(date(2026, 10, 3)) == "3 October"
    assert [en.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 21, 22, 23)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "21st", "22nd", "23rd"]
    assert en.house(5) == "your 5th house"
    assert en.city_of("America/New_York") == "New York" and en.city_of("Atlantic/Canary") == "Canary Islands"
    assert en.city_of("America/Argentina/Cordoba") == "Cordoba"
    assert en.planet("Sun") == "The Sun" and en.planet("Moon", capital=False) == "the Moon" and en.planet("Mars") == "Mars"
    assert [en.ASPECT_EN[a] for a in ("conjunction", "square", "opposition", "trine", "sextile")] == [
        "a conjunction", "a square", "an opposition", "a trine", "a sextile",
    ]
    assert en.aspect_near("Saturn", "opposition", en.point("15"), 12) == "Saturn is in an opposition with the 15° point of your sign, 12' from exact."
    assert en.planet_ingress("Mercury", "Libra", 12, when, "Europe/Madrid", retrograde=True, with_date=True) == (
        "Retrograde Mercury enters Libra, your 12th house, on 14 November at 1:27 (Madrid time)."
    )
    assert en.moon_phase("waxing", 0.874, "Waxing Gibbous") == "Waxing gibbous Moon, with 87% of the disc illuminated."
    assert en.moon_phase("waning", 0.5, None) == "Waning Moon, with 50% of the disc illuminated."
    assert en.retrogrades([]) is None
    assert es.time_text is es.time_es and es.ruler("Moon") == "la Luna, tu regente"


def test_phrase_modules_have_the_same_functions():
    def api(module):
        return {
            name: list(inspect.signature(obj).parameters)
            for name, obj in vars(module).items()
            if inspect.isfunction(obj) and not name.startswith("_") and not name.endswith("_es")
        }

    es_api, en_api = api(es), api(en)
    en_api.pop("ordinal")  # English-only helper
    assert es_api == en_api
