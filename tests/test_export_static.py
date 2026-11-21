"""tools/export_static.py: the static JSON the website imports at build time."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

CALC = Path(__file__).resolve().parents[1]
EXPORT = CALC / "export"


def test_export_static_small_range(tmp_path):
    subprocess.run(
        [sys.executable, str(CALC / "tools" / "export_static.py"), "--from", "2026-11-01", "--to", "2026-11-30", "--out", str(tmp_path)],
        check=True,
        capture_output=True,
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == ["eclipses.json", "index.json", "lunations.json", "retrogrades.json"]
    lun = json.loads((tmp_path / "lunations.json").read_text())
    assert lun["count"] == 2 and [l["phase"] for l in lun["lunations"]] == ["new", "full"]
    full = lun["lunations"][1]
    assert full["date_utc"] == "2026-11-24" and full["sign"] == "Gemini"
    assert full["local"]["madrid"] == "2026-11-24T15:53+01:00"
    assert full["local"]["mexico_city"] == "2026-11-24T08:53-06:00"
    assert full["local"]["buenos_aires"] == "2026-11-24T11:53-03:00"
    assert "datetime_local" not in full and "tz" not in full
    retro = json.loads((tmp_path / "retrogrades.json").read_text())
    mercury = [p for p in retro["periods"] if p["planet"] == "Mercury"]
    assert [(p["from"], p["to"]) for p in mercury] == [("2026-10-24", "2026-11-13")]
    assert mercury[0]["station_direct"]["local"]["madrid"] == "2026-11-13T16:53+01:00"
    assert mercury[0]["shadow_from"] == "2026-10-04"
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["from"] == "2026-11-01" and index["to"] == "2026-11-30"
    assert index["city_zones"]["madrid"] == "Europe/Madrid"


@pytest.mark.skipif(not (EXPORT / "index.json").exists(), reason="export/ is repository data, not copied into the Docker image")
def test_committed_export_covers_2026_2028():
    index = json.loads((EXPORT / "index.json").read_text())
    assert (index["from"], index["to"]) == ("2026-01-01", "2028-12-31")
    lun = json.loads((EXPORT / "lunations.json").read_text())
    assert lun["count"] == len(lun["lunations"]) and 72 <= lun["count"] <= 76  # ~24.7 lunations a year
    assert all("date_utc" in l and set(l["local"]) == set(index["city_zones"]) for l in lun["lunations"])
    eclipses = json.loads((EXPORT / "eclipses.json").read_text())
    assert sum(1 for l in lun["lunations"] if l["eclipse"]) == eclipses["count"]
    retro = json.loads((EXPORT / "retrogrades.json").read_text())
    assert {p["planet"] for p in retro["periods"]} == {"Mercury", "Venus", "Mars", "Jupiter", "Saturn"}
    assert sum(1 for p in retro["periods"] if p["planet"] == "Mercury") >= 9
