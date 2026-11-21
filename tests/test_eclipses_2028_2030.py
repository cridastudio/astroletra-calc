"""Reference eclipses 2028-2030 in /v1/lunations, against NASA's eclipse catalogues (F. Espenak, NASA GSFC).

Sources, read on 2026-11-21:
- Solar eclipses 2021-2030: https://eclipse.gsfc.nasa.gov/SEdecade/SEdecade2021.html
- Lunar eclipses 2021-2030: https://eclipse.gsfc.nasa.gov/LEdecade/LEdecade2021.html

NASA gives the instant of greatest eclipse in Terrestrial Dynamical Time (TD). The service returns UTC, so the
comparison adds a Delta T of 69 s (TD - UT, IERS value for the mid-2020s; NASA's 2013 tables do not state the
value they assumed). The one-minute tolerance absorbs the uncertainty of Delta T for these years.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

DELTA_T = timedelta(seconds=69)
TOLERANCE = timedelta(seconds=60)

# date (UTC), type, kind, Saros, greatest eclipse in TD, umbral magnitude (lunar eclipses that reach the umbra)
NASA = [
    ("2028-01-12", "lunar", "partial", 115, "04:14:13", 0.066),
    ("2028-01-26", "solar", "annular", 141, "15:08:58", None),
    ("2028-07-06", "lunar", "partial", 120, "18:20:57", 0.389),
    ("2028-07-22", "solar", "total", 146, "02:56:39", None),
    ("2028-12-31", "lunar", "total", 125, "16:53:15", 1.246),
    ("2029-01-14", "solar", "partial", 151, "17:13:47", None),
    ("2029-06-12", "solar", "partial", 118, "04:06:13", None),
    ("2029-06-26", "lunar", "total", 130, "03:23:22", 1.844),
    ("2029-07-11", "solar", "partial", 156, "15:37:18", None),
    ("2029-12-05", "solar", "partial", 123, "15:03:57", None),
    ("2029-12-20", "lunar", "total", 135, "22:43:12", 1.117),
    ("2030-06-01", "solar", "annular", 128, "06:29:13", None),
    ("2030-06-15", "lunar", "partial", 140, "18:34:34", 0.502),
    ("2030-11-25", "solar", "total", 133, "06:51:37", None),
    ("2030-12-09", "lunar", "penumbral", 145, "22:28:51", None),
]


@pytest.fixture(scope="module")
def eclipses(client, headers):
    r = client.post("/v1/lunations", json={"from": "2028-01-01", "to": "2030-12-31", "tz": "UTC"}, headers=headers)
    assert r.status_code == 200, r.text
    return [l["eclipse"] for l in r.json()["lunations"] if l["eclipse"]]


def test_same_eclipses_as_nasa(eclipses):
    got = [(e["datetime_utc"][:10], e["type"], e["kind"], e["saros"]) for e in eclipses]
    assert got == [(d, t, k, s) for d, t, k, s, _, _ in NASA]


@pytest.mark.parametrize("ref", NASA, ids=[f"{r[0]}-{r[1]}" for r in NASA])
def test_greatest_eclipse_within_a_minute(eclipses, ref):
    day, kind, _, _, td, _ = ref
    e = next(x for x in eclipses if x["datetime_utc"].startswith(day) and x["type"] == kind)
    utc = datetime.fromisoformat(e["datetime_utc"].replace("Z", "+00:00")).replace(tzinfo=None)
    nasa_utc = datetime.fromisoformat(f"{day}T{td}") - DELTA_T
    assert abs(utc - nasa_utc) <= TOLERANCE, f"{day}: {utc} vs NASA {nasa_utc} (UT)"


@pytest.mark.parametrize("ref", [r for r in NASA if r[5] is not None], ids=lambda r: r[0])
def test_umbral_magnitude(eclipses, ref):
    day, _, _, _, _, magnitude = ref
    e = next(x for x in eclipses if x["datetime_utc"].startswith(day) and x["type"] == "lunar")
    assert abs(e["magnitude_umbral"] - magnitude) <= 0.01
