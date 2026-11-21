#!/usr/bin/env python3
"""Export the static sky data the website reads at build time.

Writes to ``calc/export/`` (or ``--out``):

- ``lunations.json``  new and full Moons with eclipses, UTC plus local times in the reference cities
- ``retrogrades.json`` retrograde periods of Mercury, Venus, Mars, Jupiter and Saturn with stations and shadows
- ``eclipses.json``   every solar and lunar eclipse of the range
- ``index.json``      range, generation time and the city zones used

Data only (no translated text): the site renders names and copy from its own i18n files.

    cd calc && .venv/bin/python tools/export_static.py            # 2026-01-01 .. 2028-12-31
    cd calc && .venv/bin/python tools/export_static.py --from 2027-01-01 --to 2027-12-31 --out /tmp/x
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import __version__  # noqa: E402
from app.services import sky  # noqa: E402

# Reference cities shown on the lunation pages (Madrid, Mexico City, Buenos Aires).
CITY_ZONES: dict[str, str] = {
    "madrid": "Europe/Madrid",
    "mexico_city": "America/Mexico_City",
    "buenos_aires": "America/Argentina/Buenos_Aires",
    "bogota": "America/Bogota",
    "santiago": "America/Santiago",
    "new_york": "America/New_York",
    "los_angeles": "America/Los_Angeles",
    "london": "Europe/London",
}


def _local_times(iso_utc: str) -> dict[str, str]:
    utc = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return {city: utc.astimezone(ZoneInfo(zone)).isoformat(timespec="minutes") for city, zone in CITY_ZONES.items()}


def _with_local(entry: dict) -> dict:
    out = {k: v for k, v in entry.items() if k not in ("datetime_local", "date_local", "tz")}
    # UTC calendar date: one stable route slug shared by every language (/es/luna/2026-11-24).
    out["date_utc"] = entry["datetime_utc"][:10]
    out["local"] = _local_times(entry["datetime_utc"])
    return out


def _dump(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size // 1024} KB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument("--to", dest="end", type=date.fromisoformat, default=date(2028, 12, 31))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "export")
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--to must not be before --from")
    args.out.mkdir(parents=True, exist_ok=True)

    generated = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    meta = {
        "generated_at": generated,
        "generator": f"astroletra-calc {__version__} tools/export_static.py",
        "ephemeris": "libephemeris (JPL DE440) via Kerykeion 6, geocentric tropical",
        "from": args.start.isoformat(),
        "to": args.end.isoformat(),
        "city_zones": CITY_ZONES,
    }

    lunations = sky.lunations(args.start, args.end, "UTC")["lunations"]
    lun_items = []
    for entry in lunations:
        item = _with_local(entry)
        if entry["eclipse"]:
            item["eclipse"] = _with_local(entry["eclipse"])
        lun_items.append(item)
    _dump(args.out / "lunations.json", {**meta, "count": len(lun_items), "lunations": lun_items})

    retro = sky.retrogrades(args.start, args.end)
    for period in retro["periods"]:
        for key in ("station_retrograde", "station_direct"):
            period[key]["local"] = _local_times(period[key]["datetime_utc"])
    _dump(args.out / "retrogrades.json", {**meta, "planets": retro["planets"], "count": len(retro["periods"]), "periods": retro["periods"]})

    eclipses = [_with_local(e) for e in sky._eclipses_between(args.start, args.end)]
    _dump(args.out / "eclipses.json", {**meta, "count": len(eclipses), "eclipses": eclipses})

    _dump(args.out / "index.json", {**meta, "files": ["lunations.json", "retrogrades.json", "eclipses.json"]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
