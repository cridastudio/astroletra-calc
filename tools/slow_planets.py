"""Retrógrados que faltan en ``retrogrades.json`` e ingresos de los planetas lentos, para las páginas de
Marte retrógrado, planetas retrógrados del año y los tránsitos lentos (docs/ENCARGO-SECCIONES-2-2026-11-10.md §1).

Mismo motor de efemérides que ``export_static.py`` (libephemeris, JPL DE440, geocéntrico y tropical) y las
mismas funciones de ``app.services.sky``. Escribe ``portal/data/calc/slow_planets.json`` con:

- ``retrogrades``: periodos de Urano, Neptuno y Plutón de 2026 a 2028 y de Marte de 2026 a 2035, con las dos
  estaciones (instante, signo, grado y hora local en las ocho ciudades) y la sombra previa y posterior;
- ``stations``: periodos retrógrados de Júpiter a Plutón de 2020 a 2045 sin sombra, para contar cuántas veces
  retrocede cada planeta lento durante su paso por un signo;
- ``ingresses``: entradas en signo de Júpiter a Plutón de 2020 a 2045, con el signo del que salen, si la entrada
  es en retrógrado y la hora local.

``retrogrades.json`` no cambia: sigue con los cinco planetas de siempre y el CSV de /datos/ también.

Uso: ``.venv/bin/python tools/slow_planets.py [salida.json]``
"""

from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kerykeion import SignIngressFactory  # noqa: E402

from app.services import sky  # noqa: E402
from app.services.astro import SIGN_NAMES  # noqa: E402

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
LENTOS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

# La búsqueda de la sombra de sky.py solo conoce los cinco planetas de siempre: los lentos retroceden unos
# 150-160 días y la sombra entera dura casi un año, así que se busca con paso de 10 días hasta 420.
sky._SHADOW_STEP_DAYS.update({"Uranus": 10, "Neptune": 10, "Pluto": 10})
sky._SHADOW_MAX_DAYS.update({"Uranus": 420, "Neptune": 420, "Pluto": 420})


def _local(iso_utc: str) -> dict[str, str]:
    utc = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    return {c: utc.astimezone(ZoneInfo(z)).isoformat(timespec="minutes") for c, z in CITY_ZONES.items()}


def _con_horas(periods: list[dict]) -> list[dict]:
    for p in periods:
        for k in ("station_retrograde", "station_direct"):
            p[k]["local"] = _local(p[k]["datetime_utc"])
    return periods


def main() -> int:
    salida = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "portal" / "data" / "calc" / "slow_planets.json"
    retro = sky.retrogrades(date(2026, 1, 1), date(2028, 12, 31), planets=["Uranus", "Neptune", "Pluto"])["periods"]
    marte = sky.retrogrades(date(2026, 1, 1), date(2035, 12, 31), planets=["Mars"])["periods"]
    estaciones = sky.retrogrades(date(2020, 1, 1), date(2045, 12, 31), planets=LENTOS, shadow=False)["periods"]
    for p in estaciones:
        for k in ("station_retrograde", "station_direct"):
            p[k] = {x: p[k][x] for x in ("datetime_utc", "date", "sign", "degree")}

    ingresos = []
    for ing in SignIngressFactory.from_iso_range("2020-01-01", "2046-01-01", planets=LENTOS).ingresses:
        utc = datetime.fromisoformat(ing.iso_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
        iso = utc.isoformat(timespec="seconds").replace("+00:00", "Z")
        ingresos.append({
            "planet": ing.planet,
            "datetime_utc": iso,
            "sign": SIGN_NAMES[int(ing.sign_num)],
            "from_sign": SIGN_NAMES[int(ing.from_sign_num)],
            "retrograde": bool(ing.retrograde),
            "local": _local(iso),
        })
    ingresos.sort(key=lambda i: i["datetime_utc"])

    datos = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generator": "astroletra-calc tools/slow_planets.py",
        "ephemeris": "libephemeris (JPL DE440) via Kerykeion 6, geocentric tropical",
        "city_zones": CITY_ZONES,
        "retrogrades": _con_horas(sorted(retro + marte, key=lambda p: (p["from"], p["planet"]))),
        "stations": estaciones,
        "ingresses": ingresos,
    }
    salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {salida} ({len(datos['retrogrades'])} retrógrados, {len(estaciones)} periodos lentos, {len(ingresos)} ingresos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
