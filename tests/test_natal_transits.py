"""POST /v1/natal-transits: transits over a natal chart per local day .

Reference chart: 1990-05-14 08:30 Girona (conftest REFERENCE). The New Moon of 2026-11-09 07:02 UTC at 16°53'
Scorpio (test_sky.py) is used as an external anchor: it must show at 08:02 in Madrid and 01:02 in Mexico City.
Every exact event is checked against the ephemeris: at its instant the transiting planet sits on the exact aspect.
"""

from __future__ import annotations

from datetime import datetime

from kerykeion.ephemeris_backend.backend import ephemeris_session

from app.services.sky import _longitude, _signed_diff

PATH = "/v1/natal-transits"


def _post(client, headers, body, status=200):
    r = client.post(PATH, json=body, headers=headers)
    assert r.status_code == status, r.text
    return r.json()


def test_exact_events_of_one_madrid_day_hit_the_aspect(client, headers, reference):
    d = _post(client, headers, {"natal": reference, "from": "2026-11-09", "to": "2026-11-09", "tz": "Europe/Madrid"})
    assert d["house_system"] == "placidus" and d["has_time"] is True
    assert {"Ascendant", "MC"} <= set(d["natal"])
    exact = [e for e in d["events"] if e["exact"]]
    assert exact, "the Moon makes several exact aspects every day"
    assert any(e["transiting"] == "Moon" for e in exact)
    natal_lon = {k: v["sign_num"] * 30 + v["degree"] for k, v in d["natal"].items()}
    with ephemeris_session():
        for e in exact:
            assert e["date_local"] == "2026-11-09"
            assert e["datetime_local"].startswith("2026-11-09T") and e["datetime_local"][11:16] == e["time_local"]
            at = datetime.fromisoformat(e["datetime_utc"].replace("Z", "+00:00"))
            lon = _longitude(e["transiting"], at)[0]
            off = min(abs(_signed_diff(lon - natal_lon[e["natal_point"]], s)) for s in (e["degrees"], -e["degrees"]))
            assert off < 0.05, e
            assert 1 <= e["transit_house"] <= 12 and 1 <= e["natal_point_house"] <= 12
    ids = [e["id"] for e in d["events"]]
    assert len(ids) == len(set(ids))
    # Slow planets within 1 degree without perfecting today come without a time.
    for e in d["events"]:
        if not e["exact"]:
            assert e["slow"] and e["time_local"] is None and e["orb"] <= 1.0


def test_new_moon_of_9_november_with_its_natal_house(client, headers, reference):
    mad = _post(client, headers, {"natal": reference, "from": "2026-11-09", "to": "2026-11-09", "tz": "Europe/Madrid"})
    assert [(x["phase"], x["time_local"], x["sign"]) for x in mad["lunations"]] == [("new", "08:02", "Scorpio")]
    assert 1 <= mad["lunations"][0]["house"] <= 12
    mex = _post(client, headers, {"natal": reference, "from": "2026-11-09", "to": "2026-11-09", "tz": "America/Mexico_City"})
    assert [(x["phase"], x["time_local"]) for x in mex["lunations"]] == [("new", "01:02")]


def test_daylight_saving_day_has_25_hours_of_events(client, headers, reference):
    # 25 October 2026: Madrid goes from CEST to CET at 03:00; local times after the change carry +01:00.
    d = _post(client, headers, {"natal": reference, "from": "2026-10-25", "to": "2026-10-25", "tz": "Europe/Madrid"})
    exact = [e for e in d["events"] if e["exact"]]
    assert exact and all(e["date_local"] == "2026-10-25" for e in exact)
    for e in exact:
        hour = int(e["time_local"][:2])
        assert e["datetime_local"].endswith("+02:00" if hour < 2 else "+01:00") or 2 <= hour < 3


def test_without_birth_time_uses_solar_houses_and_no_angles(client, headers, reference):
    natal = {**reference, "time": None}
    d = _post(client, headers, {"natal": natal, "from": "2026-12-01", "to": "2026-12-31", "tz": "America/Mexico_City",
                                "planets": ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"],
                                "include_in_orb": False})
    assert d["house_system"] == "solar" and d["has_time"] is False
    assert "Ascendant" not in d["natal"] and "MC" not in d["natal"]
    sun_sign = d["natal"]["Sun"]["sign_num"]
    assert d["cusps"][0] == sun_sign * 30 and all(c % 30 == 0 for c in d["cusps"])
    assert d["natal"]["Sun"]["house"] == 1
    assert all(e["transiting"] != "Moon" and e["exact"] for e in d["events"])
    assert {x["phase"] for x in d["lunations"]} == {"new", "full"}
    assert all(x["date_local"].startswith("2026-12") for x in d["lunations"])


def test_validation(client, headers, reference):
    base = {"natal": reference, "from": "2026-11-09", "to": "2026-11-09", "tz": "Europe/Madrid"}
    assert client.post(PATH, json=base).status_code == 401
    assert client.post(PATH, json={**base, "tz": "Mars/Olympus"}, headers=headers).status_code == 422
    assert client.post(PATH, json={**base, "to": "2026-11-08"}, headers=headers).status_code == 422
    assert client.post(PATH, json={**base, "to": "2027-01-31"}, headers=headers).status_code == 422
    assert client.post(PATH, json={**base, "planets": ["Chiron"]}, headers=headers).status_code == 422
