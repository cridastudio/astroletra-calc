"""Reference chart: 1990-05-14 08:30 Girona (41.98N, 2.82E, Europe/Madrid).

Expected values were computed independently with pyswisseph 2.10.3.2 (Moshier
ephemeris, Placidus): Sun 53.211, Moon 282.130, Asc 85.350, MC 329.973.
"""

import pytest

EXPECTED = {
    "Sun": ("Taurus", 53.211),
    "Moon": ("Capricorn", 282.130),
    "Mercury": ("Taurus", 38.217),
    "Venus": ("Aries", 11.418),
    "Mars": ("Pisces", 347.421),
    "Jupiter": ("Cancer", 99.310),
    "Saturn": ("Capricorn", 295.269),
    "Uranus": ("Capricorn", 279.214),
    "Neptune": ("Capricorn", 284.371),
    "Pluto": ("Scorpio", 226.202),
    "North Node": ("Aquarius", 310.309),
    # Chiron from the libephemeris asteroid group (Keplerian fallback agrees to ~0.001 deg here).
    "Chiron": ("Cancer", 103.115),
}
TOLERANCE = 0.1


@pytest.fixture(scope="module")
def natal(client, reference):
    r = client.post("/v1/natal", json=reference, headers={"X-Calc-Key": "test-key"})
    assert r.status_code == 200, r.text
    return r.json()


def test_planets_match_swisseph(natal):
    by_name = {p["name"]: p for p in natal["planets"]}
    for name, (sign, abs_deg) in EXPECTED.items():
        assert by_name[name]["sign"] == sign, name
        assert abs(by_name[name]["abs_degree"] - abs_deg) < TOLERANCE, name
    assert 23.0 < by_name["Sun"]["degree"] < 23.5
    assert by_name["Mercury"]["retrograde"] is True
    assert by_name["Sun"]["house"] == 12


def test_angles_and_houses(natal):
    assert natal["has_time"] is True
    assert abs(natal["angles"]["asc"]["abs_degree"] - 85.350) < TOLERANCE
    assert abs(natal["angles"]["mc"]["abs_degree"] - 329.973) < TOLERANCE
    assert natal["angles"]["asc"]["sign"] == "Gemini"
    assert len(natal["houses"]) == 12
    assert natal["houses"][0]["abs_degree"] == natal["angles"]["asc"]["abs_degree"]
    assert natal["houses"][9]["abs_degree"] == natal["angles"]["mc"]["abs_degree"]


def test_aspects_balance_phase_and_svg(natal):
    assert any(a["p1"] == "Sun" and a["p2"] == "Saturn" and a["type"] == "trine" for a in natal["aspects"])
    assert sum(natal["balance"]["elements"].values()) == 11
    assert natal["moon_phase"]["stage"] == "waning"
    svg = natal["wheel_svg"]
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert 5_000 < len(svg) < 80_000
    assert "AC" in svg and "MC" in svg


def test_without_time(client, headers, reference):
    data = dict(reference, time=None)
    r = client.post("/v1/natal", json=data, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["has_time"] is False
    assert body["houses"] is None and body["angles"] is None
    assert all(p["house"] is None for p in body["planets"])
    assert "no_birth_time" in body["warnings"]
    rng = body["moon_range"]
    assert rng["at_00_00"]["sign"] == "Capricorn" and rng["at_23_59"]["sign"] == "Capricorn"
    assert rng["at_00_00"]["abs_degree"] < rng["at_23_59"]["abs_degree"]
    assert rng["sign_changes"] is False
    assert "AC" not in body["wheel_svg"]
