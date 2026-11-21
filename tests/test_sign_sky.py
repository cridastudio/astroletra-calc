"""Sky of a day, a week and a month for one solar sign (/v1/sign-day, /v1/sign-week, /v1/sign-month).

Reference instants were cross-checked on 7-11-2026 with Skyfield 1.55 on JPL DE421
(an implementation independent from libephemeris/DE440), apparent geocentric ecliptic
longitude of date; all agree to the second:
- Moon enters Scorpio 2026-11-07 22:39:57 UTC = 23:39 Madrid (the time printed in the
  design mock-up), 16:39 Mexico City, 17:39 Bogota, 19:39 Buenos Aires.
- Sun on 15° Scorpio 2026-11-07 09:52:04 UTC; Sun enters Sagittarius 2026-11-22 07:23:20 UTC.
- Moon sextile Mars (Mars at 21°49' Leo) 2026-11-07 07:01:34 UTC.
- Moon conjunct Mercury (17°32' Scorpio) 2026-11-08 13:01:51 UTC = 14:01 Madrid.
Mercury and Venus stations, lunations and eclipses are the ones already verified in test_sky.py.
"""

from __future__ import annotations

import re

import pytest

from app.services import es_phrases as es
from app.services import sign_sky


def _post(client, headers, path, body):
    r = client.post(path, json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


TIME_RE = re.compile(r"a las? \d{1,2}:\d{2}(?P<after>[^.;]*)")


def _times_have_city(sentences, city):
    for s in sentences:
        for m in TIME_RE.finditer(s):
            assert m.group("after").startswith(f" (hora de {city})"), s


# ----------------------------------------------------------------------------- sign-day


@pytest.fixture(scope="module")
def scorpio_day(client, headers):
    return _post(client, headers, "/v1/sign-day", {"sign": "Scorpio", "date": "2026-11-07", "tz": "Europe/Madrid"})


def test_sign_day_moon_enters_scorpio_at_23_39_madrid(scorpio_day):
    body = scorpio_day
    assert body["sign"] == "Scorpio" and body["sign_num"] == 7 and body["city"] == "Madrid"
    moon = body["moon"]
    assert moon["at_00_00"]["sign"] == "Libra" and moon["at_00_00"]["house"] == 12
    assert moon["at_23_59"]["sign"] == "Scorpio" and moon["at_23_59"]["house"] == 1
    assert moon["changes_house_today"] is True
    change = moon["next_sign_change"]
    assert (change["from_sign"], change["from_house"], change["sign"], change["house"]) == ("Libra", 12, "Scorpio", 1)
    assert change["datetime_local"] == "2026-11-07T23:39+01:00" and change["time_local"] == "23:39"
    assert change["datetime_utc"].startswith("2026-11-07T22:39")
    assert change["local_times"] == {
        "madrid": "2026-11-07T23:39+01:00",
        "mexico_city": "2026-11-07T16:39-06:00",
        "bogota": "2026-11-07T17:39-05:00",
        "buenos_aires": "2026-11-07T19:39-03:00",
    }
    assert [(s["sign"], s["house"], s["to"]["time_local"]) for s in moon["houses_today"]] == [("Libra", 12, "23:39"), ("Scorpio", 1, "09:35")]
    assert moon["phase"]["stage"] == "waning" and moon["phase"]["illumination"] < 0.05


def test_sign_day_featured_and_highlights(scorpio_day):
    featured = scorpio_day["featured"]
    assert featured["kind"] == "moon_ingress" and featured["in_period"] is True
    assert featured["time_local"] == "23:39" and featured["house"] == 1
    assert featured["label"] == "La Luna entra en Escorpio, tu casa 1, a las 23:39 (hora de Madrid)."
    highlights = scorpio_day["highlights"]
    assert 3 <= len(highlights) <= 5 and len(set(highlights)) == len(highlights)
    assert highlights[0] == "La Luna pasa de Libra (tu casa 12) a Escorpio (tu casa 1) a las 23:39 (hora de Madrid)."
    assert "El Sol forma una conjunción exacta con el grado 15 de tu signo a las 10:52 (hora de Madrid)." in highlights
    _times_have_city(highlights, "Madrid")
    for h in highlights:
        assert h.endswith(".") and "vosotros" not in h.lower()


def test_sign_day_aspects_to_points_and_ruler(scorpio_day):
    body = scorpio_day
    assert body["orb"] == 1.0
    assert [p["abs_degree"] for p in body["sign_points"]] == [210.0, 225.0, 240.0]
    assert body["ruler"]["classical"] == "Mars" and body["ruler"]["modern"] == "Pluto"
    assert body["ruler"]["position"]["sign"] == "Leo" and body["ruler"]["position"]["house"] == 10
    sun15 = next(a for a in body["aspects_to_sign"] if a["planet"] == "Sun" and a["point"] == "15")
    assert sun15["type"] == "conjunction" and sun15["exact"] is True
    assert sun15["datetime_local"] == "2026-11-07T10:52+01:00"
    # Moon on degree 0 of the sign = its ingress: listed, but not repeated as an event.
    moon0 = next(a for a in body["aspects_to_sign"] if a["planet"] == "Moon" and a["point"] == "0")
    assert moon0["type"] == "conjunction" and moon0["covered_by"] == "ingress" and moon0["time_local"] == "23:39"
    assert not any(e["kind"] == "aspect_to_sign" and e["planet"] == "Moon" for e in body["events"])
    sextile = next(a for a in body["aspects_to_ruler"] if a["planet"] == "Moon")
    assert (sextile["ruler"], sextile["type"], sextile["datetime_local"]) == ("Mars", "sextile", "2026-11-07T08:01+01:00")
    assert sextile["label"] == "La Luna forma un sextil exacto con Marte, tu regente, a las 8:01 (hora de Madrid)."
    for a in body["aspects_to_sign"] + body["aspects_to_ruler"]:
        assert a["exact"] or (a["planet"] != "Moon" and a["orb"] <= 1.0)
    assert body["aspect_balance"] == {"harmonious": 1, "challenging": 0, "conjunction": 2}
    assert [e["datetime_utc"] for e in body["events"]] == sorted(e["datetime_utc"] for e in body["events"])


def test_sign_day_planets_houses_and_retrogrades(scorpio_day):
    planets = {p["name"]: p for p in scorpio_day["planets"]}
    assert list(planets) == ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    assert planets["Sun"]["sign"] == "Scorpio" and planets["Sun"]["house"] == 1
    assert planets["Moon"]["house"] == 12 and planets["Mars"]["house"] == 10
    for p in planets.values():
        assert p["house"] == (p["sign_num"] - 7) % 12 + 1
    assert planets["Mercury"]["retrograde"] is True and planets["Mars"]["retrograde"] is False
    retro = {r["planet"]: r for r in scorpio_day["retrogrades"]}
    assert {"Mercury", "Venus", "Saturn", "Neptune", "Uranus"} <= set(retro)
    assert scorpio_day["retrogrades_affecting"] == ["Venus", "Mercury"]
    assert retro["Mercury"]["since"] == "2026-10-24" and retro["Mercury"]["until"] == "2026-11-13"
    assert retro["Mercury"]["reasons"] == ["in_sign"] and retro["Mercury"]["houses"] == [1]
    assert retro["Venus"]["signs"] == ["Scorpio", "Libra"] and retro["Venus"]["houses"] == [1, 12]
    assert retro["Saturn"]["affects"] is False
    assert scorpio_day["next_lunation"]["phase"] == "new" and scorpio_day["next_lunation"]["house"] == 1


def test_sign_day_other_zone(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "escorpio", "date": "2026-11-07", "tz": "America/Mexico_City"})
    assert body["sign"] == "Scorpio" and body["city"] == "Ciudad de México"
    assert body["moon"]["next_sign_change"]["datetime_local"] == "2026-11-07T16:39-06:00"
    assert body["featured"]["label"] == "La Luna entra en Escorpio, tu casa 1, a las 16:39 (hora de Ciudad de México)."
    _times_have_city(body["highlights"], "Ciudad de México")


def test_sign_day_stations_rank_first(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "Leo", "date": "2026-11-13", "tz": "America/Argentina/Buenos_Aires"})
    stations = [e for e in body["events"] if e["kind"] == "station"]
    assert [(e["planet"], e["station"], e["time_local"], e["house"]) for e in stations] == [
        ("Mercury", "direct", "12:53", 4),  # 15:53 UTC, verified in test_sky.py
        ("Venus", "direct", "21:27", 3),
    ]
    assert body["featured"]["planet"] == "Mercury" and body["featured"]["kind"] == "station"
    assert body["moon"]["changes_house_today"] is False
    assert body["highlights"][0].startswith("La Luna está en Capricornio (tu casa 6) todo el día y entra en Acuario (tu casa 7) el 15 de noviembre")
    _times_have_city(body["highlights"], "Buenos Aires")


def test_sign_day_full_moon_for_cancer_is_not_repeated_as_ruler_aspect(client, headers):
    body = _post(client, headers, "/v1/sign-day", {"sign": "Cancer", "date": "2026-11-24", "tz": "Europe/Madrid"})
    assert body["ruler"]["classical"] == "Moon" and body["ruler"]["modern"] is None
    lunation = next(e for e in body["events"] if e["kind"] == "lunation")
    assert lunation["phase"] == "full" and lunation["time_local"] == "15:53" and lunation["sign"] == "Gemini" and lunation["house"] == 12
    assert body["featured"]["kind"] == "lunation"
    opp = next(a for a in body["aspects_to_ruler"] if a["planet"] == "Sun")
    assert opp["type"] == "opposition" and opp["covered_by"] == "lunation"
    assert opp not in body["events"]


def test_sign_day_quiet_day_features_the_sky_aspect(client, headers):
    # 8-11-2026: nothing happens on the points or the ruler of Aries; the dato del día is the
    # exact Moon-Mercury conjunction of the day's sky, placed in the Aries houses.
    body = _post(client, headers, "/v1/sign-day", {"sign": "Aries", "date": "2026-11-08", "tz": "Europe/Madrid"})
    assert body["events"] == []
    featured = body["featured"]
    assert (featured["kind"], featured["p1"], featured["p2"], featured["type"]) == ("sky_aspect", "Moon", "Mercury", "conjunction")
    assert featured["time_local"] == "14:01" and featured["houses"] == [8, 8] and featured["in_period"] is True
    assert featured["label"] == "La Luna (tu casa 8) forma una conjunción exacta con Mercurio (tu casa 8) a las 14:01 (hora de Madrid)."
    assert featured["local_times"]["buenos_aires"] == "2026-11-08T10:01-03:00"
    assert body["sky_aspects"] and all("Mars" not in (a["p1"], a["p2"]) for a in body["sky_aspects"])  # Mars rules Aries
    assert featured["label"] in body["highlights"]
    # Gemini is ruled by Mercury: the same conjunction is an aspect to its ruler instead.
    body = _post(client, headers, "/v1/sign-day", {"sign": "Gemini", "date": "2026-11-08", "tz": "Europe/Madrid"})
    assert body["featured"]["kind"] == "aspect_to_ruler" and body["featured"]["ruler"] == "Mercury"
    assert not any("Mercury" in (a["p1"], a["p2"]) for a in body["sky_aspects"])


def test_sign_day_validation(client, headers):
    for sign in ("7", "SCORPIO", "Escorpión"):
        body = _post(client, headers, "/v1/sign-day", {"sign": sign, "date": "2026-11-07"})
        assert body["sign"] == "Scorpio" and body["tz"] == "UTC" and body["city"] == "UTC"
    assert "(UTC)" in body["featured"]["label"]
    for bad in (
        {"sign": "Ophiuchus", "date": "2026-11-07"},
        {"sign": "Leo", "date": "2026-11-07", "tz": "Mars/Olympus"},
        {"sign": "Leo", "date": "2200-01-01"},
        {"sign": "Leo"},
    ):
        assert client.post("/v1/sign-day", json=bad, headers=headers).status_code == 422


# ----------------------------------------------------------------------------- sign-week


def test_sign_week_scorpio(client, headers):
    body = _post(client, headers, "/v1/sign-week", {"sign": "Scorpio", "from": "2026-11-09", "tz": "Europe/Madrid"})
    assert (body["period"], body["from"], body["to"]) == ("week", "2026-11-09", "2026-11-15")
    assert [d["date"] for d in body["moon_by_day"]] == [f"2026-11-{d:02d}" for d in range(9, 16)]
    assert body["moon_by_day"][0]["sign"] == "Scorpio" and body["moon_by_day"][0]["house"] == 1
    featured = body["featured"]
    assert featured[0]["kind"] == "lunation" and featured[0]["phase"] == "new"
    assert featured[0]["datetime_local"] == "2026-11-09T08:02+01:00" and featured[0]["house"] == 1
    assert featured[0]["label"] == "Luna nueva a 16°53' de Escorpio, en tu casa 1, el 9 de noviembre a las 8:02 (hora de Madrid)."
    stations = [(e["planet"], e["datetime_local"]) for e in body["events"] if e["kind"] == "station"]
    assert stations == [("Mercury", "2026-11-13T16:53+01:00"), ("Venus", "2026-11-14T01:27+01:00")]
    venus = next(e for e in body["events"] if e["kind"] == "station" and e["planet"] == "Venus")
    assert venus["label"].endswith("el 14 de noviembre a la 1:27 (hora de Madrid).")
    for e in body["events"]:
        assert "2026-11-09" <= e["date_local"] <= "2026-11-15"
    assert [e["datetime_utc"] for e in body["events"]] == sorted(e["datetime_utc"] for e in body["events"])
    assert all(e["kind"] == "moon_ingress" for e in body["moon_ingresses"]) and len(body["moon_ingresses"]) == 3
    assert body["sun"]["at_start"]["house"] == 1 and body["sun"]["at_end"]["house"] == 1
    assert 3 <= len(body["highlights"]) <= 5
    assert "El Sol recorre Escorpio (tu casa 1) toda la semana." in body["highlights"]
    _times_have_city(body["highlights"], "Madrid")


def test_sign_week_validation(client, headers):
    assert client.post("/v1/sign-week", json={"sign": "Leo", "from": "2149-12-28"}, headers=headers).status_code == 422
    assert client.post("/v1/sign-week", json={"sign": "Leo"}, headers=headers).status_code == 422


# ----------------------------------------------------------------------------- sign-month


def test_sign_month_scorpio_november_2026(client, headers):
    body = _post(client, headers, "/v1/sign-month", {"sign": "Scorpio", "year": 2026, "month": 11, "tz": "Europe/Madrid"})
    assert (body["period"], body["from"], body["to"]) == ("month", "2026-11-01", "2026-11-30")
    assert len(body["moon_by_day"]) == 30
    sun_in = next(e for e in body["events"] if e["kind"] == "ingress" and e["planet"] == "Sun")
    assert (sun_in["sign"], sun_in["house"], sun_in["datetime_local"]) == ("Sagittarius", 2, "2026-11-22T08:23+01:00")
    assert [(l["phase"], l["date_local"], l["house"]) for l in body["lunations"]] == [("new", "2026-11-09", 1), ("full", "2026-11-24", 8)]
    moon_in_sign = [e for e in body["moon_ingresses"] if e["house"] == 1]
    assert moon_in_sign[0]["datetime_local"] == "2026-11-07T23:39+01:00"
    assert "La Luna entra en Escorpio, tu casa 1, el 7 de noviembre a las 23:39 (hora de Madrid)." in body["highlights"]
    ruler = [(a["planet"], a["type"], a["date_local"]) for a in body["aspects_to_ruler"]]
    assert ("Jupiter", "conjunction", "2026-11-16") in ruler
    assert body["featured"][0]["kind"] == "lunation"
    assert body["retrogrades_affecting"] == ["Venus", "Mercury"]
    assert all(a["exact"] for a in body["aspects_to_sign"] + body["aspects_to_ruler"])
    assert not any(a["planet"] == "Moon" for a in body["aspects_to_sign"])
    _times_have_city(body["highlights"], "Madrid")


def test_sign_month_cancer_eclipses_and_no_moon_ruler_scan(client, headers):
    body = _post(client, headers, "/v1/sign-month", {"sign": "Cancer", "year": 2027, "month": 2, "tz": "America/Bogota"})
    assert body["to"] == "2027-02-28" and len(body["moon_by_day"]) == 28
    eclipses = [(e["eclipse"]["type"], e["eclipse"]["kind"], e["date_local"], e["house"]) for e in body["events"] if e["kind"] == "eclipse"]
    assert eclipses == [("solar", "annular", "2027-02-06", 8), ("lunar", "penumbral", "2027-02-20", 3)]
    assert body["featured"][0]["kind"] == "eclipse"
    assert body["aspects_to_ruler"] == []  # the ruler is the Moon: covered by lunations and Moon ingresses
    mercury = next(e for e in body["events"] if e["kind"] == "station" and e["planet"] == "Mercury")
    assert mercury["station"] == "retrograde" and mercury["date_local"] == "2027-02-09"
    _times_have_city(body["highlights"], "Bogotá")


def test_sign_month_validation(client, headers):
    assert client.post("/v1/sign-month", json={"sign": "Leo", "year": 2026, "month": 13}, headers=headers).status_code == 422
    body = _post(client, headers, "/v1/sign-month", {"sign": "11", "year": 2026, "month": 12})
    assert body["sign"] == "Pisces" and body["to"] == "2026-12-31"


@pytest.mark.parametrize("path,body", [
    ("/v1/sign-day", {"sign": "Aries", "date": "2026-11-07"}),
    ("/v1/sign-week", {"sign": "Aries", "from": "2026-11-09"}),
    ("/v1/sign-month", {"sign": "Aries", "year": 2026, "month": 11}),
])
def test_sign_endpoints_require_key(client, path, body):
    assert client.post(path, json=body).status_code == 401


# ----------------------------------------------------------------------------- units


def test_score_formula_and_houses():
    assert sign_sky.house_of(7, 7) == 1 and sign_sky.house_of(6, 7) == 12 and sign_sky.house_of(0, 11) == 2
    assert sign_sky.score_event({"kind": "ingress", "planet": "Sun", "house": 1}) == 10
    assert sign_sky.score_event({"kind": "moon_ingress", "planet": "Moon", "house": 1}) == 6
    assert sign_sky.score_event({"kind": "eclipse", "planet": "Moon", "house": 7}) == 14
    assert sign_sky.score_event({"kind": "station", "planet": "Mercury", "affects": True}) == 9
    assert sign_sky.score_event({"kind": "aspect_to_sign", "planet": "Jupiter", "type": "trine", "point": "15"}) == 3.5
    assert sign_sky.score_event({"kind": "aspect_to_ruler", "planet": "Moon", "type": "sextile"}) == 0.6
    assert sign_sky.score_event({"kind": "sky_aspect", "p1": "Moon", "p2": "Mercury", "type": "conjunction"}) == 1.12
    assert [sign_sky.CLASSICAL_RULER[i] for i in (0, 3, 4, 7, 10, 11)] == ["Mars", "Moon", "Sun", "Mars", "Saturn", "Jupiter"]


def test_spanish_phrases():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    assert es.degree(15.04) == "15°02'" and es.degree(29.9999) == "29°59'" and es.degree(0.0) == "0°00'"
    when = datetime(2026, 11, 14, 1, 27, tzinfo=ZoneInfo("Europe/Madrid"))
    assert es.time_es(when, "Europe/Madrid") == "a la 1:27 (hora de Madrid)"
    assert es.when_es(when, "Europe/Madrid", with_date=True) == "el 14 de noviembre a la 1:27 (hora de Madrid)"
    assert es.time_es(datetime(2026, 1, 1, 0, 5), "UTC") == "a las 0:05 (UTC)"
    assert es.city_of("America/Argentina/Cordoba") == "Cordoba"
    assert es.planet("Sun") == "El Sol" and es.planet("Moon", capital=False) == "la Luna" and es.planet("Mars") == "Marte"
