"""Mundane sky endpoints (lunations, retrogrades, today, sign-year, solar-return-next).

Reference values were checked on 6-11-2026 against public sources:
- New Moon 2026-11-09 07:02 UTC at 16°53' Scorpio; Full Moon 2026-11-24 14:53 UTC at 2°20' Gemini
  (cafeastrology.com, timeanddate.com, theskylive.com).
- Full Moon 2025-11-05 13:19 UTC at 13°22' Taurus, the largest supermoon of 2025 (earthsky.org).
- Mercury retrograde 2026-10-24 (20°59' Scorpio) to 2026-11-13 15:53 UTC (5°02' Scorpio) (chani.com, cafeastrology.com).
- Venus retrograde 2026-10-03 (8°29' Scorpio) to 2026-11-14 (22°52' Libra); Mars retrograde 2027-01-10
  (10°26' Virgo) to 2027-04-01 (20°56' Leo) (cafeastrology.com/retrogrades).
- Eclipses: total solar 2026-08-12 (Leo), partial lunar 2026-08-28 (Pisces), total lunar 2026-03-03 (Virgo)
  (eclipsewise.com, NASA).
"""

from __future__ import annotations

import pytest


def _post(client, headers, path, body):
    r = client.post(path, json=body, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ----------------------------------------------------------------------------- lunations


def test_lunations_november_2026_madrid(client, headers):
    body = _post(client, headers, "/v1/lunations", {"from": "2026-11-01", "to": "2026-11-30", "tz": "Europe/Madrid"})
    assert body["tz"] == "Europe/Madrid"
    assert [l["phase"] for l in body["lunations"]] == ["new", "full"]
    new, full = body["lunations"]
    assert new["datetime_utc"].startswith("2026-11-09T07:02")
    assert new["datetime_local"] == "2026-11-09T08:02+01:00"
    assert new["sign"] == "Scorpio" and abs(new["degree"] - 16.89) < 0.05
    assert new["eclipse"] is None
    assert full["datetime_utc"].startswith("2026-11-24T14:53")
    assert full["datetime_local"] == "2026-11-24T15:53+01:00"
    assert full["sign"] == "Gemini" and abs(full["degree"] - 2.34) < 0.05
    assert full["sun"]["sign"] == "Sagittarius" and full["moon"]["sign"] == "Gemini"
    assert full["eclipse"] is None


def test_lunations_full_moon_2025_11_05_taurus_supermoon(client, headers):
    body = _post(client, headers, "/v1/lunations", {"from": "2025-11-05", "to": "2025-11-05", "tz": "UTC"})
    assert len(body["lunations"]) == 1
    full = body["lunations"][0]
    assert full["phase"] == "full"
    assert full["datetime_utc"].startswith("2025-11-05T13:19")
    assert full["sign"] == "Taurus" and abs(full["degree"] - 13.37) < 0.05


def test_lunations_mark_eclipses(client, headers):
    body = _post(client, headers, "/v1/lunations", {"from": "2026-01-01", "to": "2026-12-31", "tz": "America/Mexico_City"})
    lunations = body["lunations"]
    assert len(lunations) == 25  # 12 new + 13 full Moons in 2026 (two full Moons in December: a blue Moon year)
    assert [l["phase"] for l in lunations].count("new") == 12
    eclipsed = [l for l in lunations if l["eclipse"]]
    assert [(l["phase"], l["eclipse"]["type"], l["eclipse"]["kind"], l["date_local"]) for l in eclipsed] == [
        ("new", "solar", "annular", "2026-02-17"),
        ("full", "lunar", "total", "2026-03-03"),
        ("new", "solar", "total", "2026-08-12"),
        ("full", "lunar", "partial", "2026-08-27"),  # 04:12 UTC on the 28th = evening of the 27th in Mexico City
    ]
    solar = next(l for l in eclipsed if l["date_local"] == "2026-08-12")
    assert solar["sign"] == "Leo" and solar["eclipse"]["sign"] == "Leo"
    assert solar["eclipse"]["datetime_local"].startswith("2026-08-12T11:45-06:00")
    assert solar["eclipse"]["saros"] == 126


def test_lunations_local_date_filter_and_limits(client, headers):
    # The 2026-08-28 04:12 UTC lunation is still the 27th in Mexico City: filter by local date.
    body = _post(client, headers, "/v1/lunations", {"from": "2026-08-27", "to": "2026-08-27", "tz": "America/Mexico_City"})
    assert [l["date_local"] for l in body["lunations"]] == ["2026-08-27"]
    body = _post(client, headers, "/v1/lunations", {"from": "2026-08-27", "to": "2026-08-27", "tz": "UTC"})
    assert body["lunations"] == []
    r = client.post("/v1/lunations", json={"from": "2026-01-01", "to": "2029-12-31"}, headers=headers)
    assert r.status_code == 422
    r = client.post("/v1/lunations", json={"from": "2026-01-01", "to": "2026-02-01", "tz": "Mars/Olympus"}, headers=headers)
    assert r.status_code == 422


# ----------------------------------------------------------------------------- retrogrades


def test_retrogrades_2026(client, headers):
    body = _post(client, headers, "/v1/retrogrades", {"from": "2026-01-01", "to": "2026-12-31"})
    assert body["planets"] == ["Mercury", "Venus", "Mars", "Jupiter", "Saturn"]
    periods = body["periods"]
    assert periods == sorted(periods, key=lambda p: (p["from"], p["planet"]))
    mercury = [p for p in periods if p["planet"] == "Mercury"]
    assert [(p["from"], p["to"]) for p in mercury] == [
        ("2026-02-26", "2026-03-20"),
        ("2026-06-29", "2026-07-23"),
        ("2026-10-24", "2026-11-13"),
    ]
    autumn = mercury[2]
    sr, sd = autumn["station_retrograde"], autumn["station_direct"]
    assert sr["sign"] == "Scorpio" and abs(sr["degree"] - 20.98) < 0.05
    assert sd["sign"] == "Scorpio" and abs(sd["degree"] - 5.03) < 0.05
    assert sd["datetime_utc"].startswith("2026-11-13T15:53")
    assert autumn["signs"] == ["Scorpio"] and autumn["days"] == 20
    assert autumn["shadow_from"] == "2026-10-04" and autumn["shadow_to"] in ("2026-11-29", "2026-11-30")

    venus = [p for p in periods if p["planet"] == "Venus"]
    assert len(venus) == 1 and (venus[0]["from"], venus[0]["to"]) == ("2026-10-03", "2026-11-14")
    assert venus[0]["station_retrograde"]["sign"] == "Scorpio" and abs(venus[0]["station_retrograde"]["degree"] - 8.49) < 0.05
    assert venus[0]["station_direct"]["sign"] == "Libra" and abs(venus[0]["station_direct"]["degree"] - 22.86) < 0.05
    assert venus[0]["signs"] == ["Scorpio", "Libra"]  # travel order: stations retrograde in Scorpio, direct in Libra

    assert not any(p["planet"] == "Mars" for p in periods), "Mars is not retrograde in 2026"
    saturn = [p for p in periods if p["planet"] == "Saturn"]
    assert len(saturn) == 1 and (saturn[0]["from"], saturn[0]["to"]) == ("2026-07-26", "2026-12-10")
    # Periods that overlap the range keep their real stations (not clipped).
    jupiter = [p for p in periods if p["planet"] == "Jupiter"]
    assert [(p["from"], p["to"]) for p in jupiter] == [("2025-11-11", "2026-03-11"), ("2026-12-13", "2027-04-13")]


def test_retrogrades_mars_2027_and_options(client, headers):
    body = _post(client, headers, "/v1/retrogrades", {"from": "2027-01-01", "to": "2027-12-31", "planets": ["Mars"], "shadow": False})
    assert body["planets"] == ["Mars"]
    assert len(body["periods"]) == 1
    mars = body["periods"][0]
    assert (mars["from"], mars["to"]) == ("2027-01-10", "2027-04-01")
    assert mars["station_retrograde"]["sign"] == "Virgo" and abs(mars["station_retrograde"]["degree"] - 10.43) < 0.1
    assert mars["station_direct"]["sign"] == "Leo" and abs(mars["station_direct"]["degree"] - 20.93) < 0.1
    assert mars["shadow_from"] is None and mars["shadow_to"] is None
    r = client.post("/v1/retrogrades", json={"from": "2027-01-01", "to": "2027-12-31", "planets": ["Pluto"]}, headers=headers)
    assert r.status_code == 422


# ----------------------------------------------------------------------------- today


def test_today_madrid_2026_11_06(client, headers):
    body = _post(client, headers, "/v1/today", {"date": "2026-11-06", "tz": "Europe/Madrid"})
    assert body["sun"]["sign"] == "Scorpio"
    moon = body["moon"]
    assert moon["sign"] == "Libra" and moon["at_00_00"]["sign"] == "Libra" and moon["at_23_59"]["sign"] == "Libra"
    assert moon["changes_sign_today"] is False
    assert moon["next_sign_change"]["sign"] == "Scorpio"
    assert moon["next_sign_change"]["datetime_local"] == "2026-11-07T23:39+01:00"
    assert moon["phase"]["stage"] == "waning" and moon["phase"]["illumination"] < 0.15
    active = {r["planet"]: r for r in body["retrogrades"]}
    assert {"Mercury", "Venus", "Saturn"} <= set(active)
    assert active["Mercury"]["since"] == "2026-10-24" and active["Mercury"]["until"] == "2026-11-13"
    assert active["Mercury"]["sign"] == "Scorpio"
    assert body["next_lunation"]["phase"] == "new" and body["next_lunation"]["date_local"] == "2026-11-09"
    assert body["aspect_orb"] == 1.0
    for a in body["aspects"]:
        assert a["exact"] or a["orb"] <= 1.0
    assert len(body["planets"]) == 10 and body["planets"][0]["name"] == "Sun"
    # Both directions of the asymmetric aspects are reported (p1 ahead of or behind p2).
    seen = {(a["p1"], a["p2"], a["type"]) for a in body["aspects"]}
    assert len(seen) == len(body["aspects"])


def test_today_moon_sign_change_and_exact_opposition(client, headers):
    body = _post(client, headers, "/v1/today", {"date": "2026-11-07", "tz": "Europe/Madrid"})
    assert body["moon"]["changes_sign_today"] is True
    assert body["moon"]["at_00_00"]["sign"] == "Libra" and body["moon"]["at_23_59"]["sign"] == "Scorpio"
    # Full Moon day: the Sun-Moon opposition is exact at 15:53 local time.
    body = _post(client, headers, "/v1/today", {"date": "2026-11-24", "tz": "Europe/Madrid"})
    opp = next(a for a in body["aspects"] if a["p1"] == "Sun" and a["p2"] == "Moon" and a["type"] == "opposition")
    assert opp["exact"] is True and opp["datetime_local"] == "2026-11-24T15:53+01:00" and opp["orb"] == 0.0
    assert body["aspects"][0] == opp or body["aspects"][0]["exact"]
    # The same instant in Buenos Aires is 11:53 (local time of the visitor).
    body = _post(client, headers, "/v1/today", {"date": "2026-11-24", "tz": "America/Argentina/Buenos_Aires"})
    opp = next(a for a in body["aspects"] if a["p1"] == "Sun" and a["p2"] == "Moon" and a["type"] == "opposition")
    assert opp["datetime_local"] == "2026-11-24T11:53-03:00"


def test_today_cazimi(client, headers):
    # Mercury cazimi (inferior conjunction with the Sun) on 2026-11-04.
    body = _post(client, headers, "/v1/today", {"date": "2026-11-04", "tz": "UTC"})
    conj = [a for a in body["aspects"] if {a["p1"], a["p2"]} == {"Sun", "Mercury"} and a["type"] == "conjunction"]
    assert conj and conj[0]["exact"] is True and conj[0]["datetime_local"].startswith("2026-11-04")


# ----------------------------------------------------------------------------- sign-year


def test_sign_year_taurus_2027(client, headers):
    body = _post(client, headers, "/v1/sign-year", {"sign": "taurus", "year": 2027, "tz": "Europe/Madrid"})
    assert body["sign"] == "Taurus" and body["sign_num"] == 1
    assert body["sun_season"]["from"]["date_local"] == "2027-04-20"
    assert body["sun_season"]["to"]["date_local"] == "2027-05-21"
    planets = {p["planet"]: p for p in body["planets"]}
    assert list(planets) == ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]
    jupiter = planets["Jupiter"]
    assert [(p["sign"], p["aspect_to_sign"]) for p in jupiter["periods"]] == [("Leo", "square"), ("Virgo", "trine")]
    assert jupiter["ingresses"][0]["sign"] == "Virgo" and jupiter["ingresses"][0]["date_local"] == "2027-07-26"
    assert planets["Pluto"]["periods"][0]["aspect_to_sign"] == "square"  # Aquarius squares Taurus
    assert planets["Uranus"]["periods"][0]["aspect_to_sign"] is None  # Gemini: semi-sextile, not reported
    assert planets["Uranus"]["ingresses"] == []
    kinds = {e["kind"] for e in body["events"]}
    assert kinds == {"ingress", "aspect"}
    assert len(body["eclipses"]) == 5  # 2027: 2 solar + 3 lunar
    assert body["eclipses"][0]["kind"] == "annular" and body["eclipses"][0]["aspect_to_sign"] == "square"
    assert len(body["mercury_retrogrades"]) == 3
    assert body["mercury_retrogrades"][2]["aspects_to_sign"] == ["opposition"]  # Oct 2027 in Libra/Scorpio


def test_sign_year_accepts_sign_num_and_rejects_unknown(client, headers):
    body = _post(client, headers, "/v1/sign-year", {"sign": "7", "year": 2026})
    assert body["sign"] == "Scorpio" and body["tz"] == "UTC"
    assert body["sun_season"]["from"]["date_local"] == "2026-10-23"
    r = client.post("/v1/sign-year", json={"sign": "Ophiuchus", "year": 2026}, headers=headers)
    assert r.status_code == 422


# ----------------------------------------------------------------------------- solar-return-next


def test_solar_return_next(client, headers, reference):
    body = _post(client, headers, "/v1/solar-return-next", {"natal": reference, "after": "2026-11-06"})
    assert body["tz"] == "Europe/Madrid" and body["has_time"] is True and body["warnings"] == []
    nxt, prev = body["next"], body["previous"]
    assert nxt["return_datetime_local"] == "2027-05-14T07:09+02:00"
    assert nxt["return_datetime_utc"].startswith("2027-05-14T05:09")
    assert nxt["year"] == 2027 and nxt["age"] == 37 and nxt["days_until"] == 189
    assert prev["return_datetime_local"].startswith("2026-05-14T01:35")
    assert body["natal_sun"]["sign"] == "Taurus" and abs(body["natal_sun"]["abs_degree"] - 53.211) < 0.01
    # The Sun is back on its natal degree at the return instant.
    chart = _post(client, headers, "/v1/natal", {**reference, "date": "2027-05-14", "time": "07:09"})
    sun = next(p for p in chart["planets"] if p["name"] == "Sun")
    assert abs(sun["abs_degree"] - 53.211) < 0.01


def test_solar_return_next_other_zone_and_no_time(client, headers, reference):
    body = _post(client, headers, "/v1/solar-return-next", {"natal": reference, "after": "2026-11-06", "tz": "America/Mexico_City"})
    assert body["next"]["return_datetime_local"] == "2027-05-13T23:09-06:00"
    body = _post(client, headers, "/v1/solar-return-next", {"natal": {**reference, "time": None}, "after": "2026-11-06"})
    assert body["has_time"] is False and body["warnings"] == ["return_time_uncertain_without_birth_time"]
    assert body["next"]["return_datetime_local"].startswith("2027-05-14")


# ----------------------------------------------------------------------------- auth


@pytest.mark.parametrize("path,body", [
    ("/v1/lunations", {"from": "2026-01-01", "to": "2026-01-31"}),
    ("/v1/retrogrades", {"from": "2026-01-01", "to": "2026-01-31"}),
    ("/v1/today", {"date": "2026-01-01"}),
    ("/v1/sign-year", {"sign": "Aries", "year": 2026}),
])
def test_sky_requires_key(client, path, body):
    assert client.post(path, json=body).status_code == 401
