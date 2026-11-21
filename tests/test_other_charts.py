import datetime


def test_solar_return(client, headers, reference):
    body = {"natal": reference, "year": 2027, "location": {"lat": 41.98, "lon": 2.82, "tz": "Europe/Madrid"}}
    r = client.post("/v1/solar-return", json=body, headers=headers)
    assert r.status_code == 200, r.text
    sr = r.json()
    assert sr["return_datetime"].startswith("2027-05-1")
    chart = sr["return_chart"]
    sun = next(p for p in chart["planets"] if p["name"] == "Sun")
    assert abs(sun["abs_degree"] - 53.211) < 0.01
    assert chart["angles"] is not None and sr["wheel_svg"].startswith("<svg")
    assert sr["year"] == 2027 and "planets" not in sr
    cross = sr["return_to_natal_aspects"]
    assert cross and cross[0] == {"return_point": "Sun", "natal_point": "Sun", "type": "conjunction", "degrees": 0, "orb": 0.0, "applying": cross[0]["applying"]}
    assert cross == sorted(cross, key=lambda x: x["orb"])


def test_synastry(client, headers, reference):
    b = {"date": "1988-11-02", "time": "15:10", "lat": 40.42, "lon": -3.70, "tz": "Europe/Madrid"}
    r = client.post("/v1/synastry", json={"a": reference, "b": b}, headers=headers)
    assert r.status_code == 200, r.text
    syn = r.json()
    assert syn["chart_a"]["planets"][0]["sign"] == "Taurus"
    assert syn["chart_b"]["planets"][0]["sign"] == "Scorpio"
    assert len(syn["inter_aspects"]) > 10
    assert all({"a", "b", "type", "orb", "applying"} <= set(a) for a in syn["inter_aspects"])
    assert syn["inter_aspects"] == sorted(syn["inter_aspects"], key=lambda x: x["orb"])
    assert syn["composite"]["planets"][0]["name"] == "Sun"
    assert syn["composite"]["asc"]["sign"] and syn["composite"]["method"] == "midpoint"
    assert syn["double_wheel_svg"].startswith("<svg")


def test_synastry_without_time_on_one_side(client, headers, reference):
    b = {"date": "1988-11-02", "time": None, "lat": 40.42, "lon": -3.70, "tz": "Europe/Madrid"}
    r = client.post("/v1/synastry", json={"a": reference, "b": b}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["composite"]["asc"] is None
    assert body["chart_b"]["moon_range"]["at_00_00"]["sign"]
    assert not any("Ascendant" in (a["a"], a["b"]) for a in body["inter_aspects"])


def test_transits(client, headers, reference):
    body = {"natal": reference, "from": "2027-01-01", "to": "2027-12-31"}
    r = client.post("/v1/transits", json=body, headers=headers)
    assert r.status_code == 200, r.text
    t = r.json()
    assert [m["month"] for m in t["months"]] == [f"2027-{i:02d}" for i in range(1, 13)]
    events = [e for m in t["months"] for e in m["events"]]
    assert events, "a full year must contain slow-planet transits"
    for e in events:
        assert e["transiting"] in t["transiting"]
        assert e["aspect"] in ("conjunction", "sextile", "square", "trine", "opposition")
        assert datetime.date.fromisoformat(e["date"]).year == 2027
        assert e["exact"] is True or e["orb"] <= 1.0
    # Saturn square natal Uranus (279.2) from Aries is exact mid January 2027.
    assert any(e["transiting"] == "Saturn" and e["natal_point"] == "Uranus" and e["date"].startswith("2027-01") for e in events)
    assert len(t["retrogrades"]) == 3 and all(p["planet"] == "Mercury" for p in t["retrogrades"])
    assert any(i["planet"] == "Jupiter" and i["sign"] == "Virgo" for i in t["ingresses"])
