"""Distancia Tierra-Luna en cada lunación de ``lunations.json`` y si la luna llena es superluna.

Lee ``portal/data/calc/lunations.json`` (o el fichero que se pase) y escribe ``moon_distance.json`` al lado,
con el mismo motor de efemérides que generó el volcado (libephemeris, JPL DE440, geocéntrico):

- ``distance_km``: distancia geocéntrica de la Luna en el instante exacto de la lunación;
- ``perigee_km`` y ``apogee_km``: mínimo y máximo de esa misma órbita (±15 días, paso de 10 minutos);
- ``supermoon``: criterio de Fred Espenak, el más usado en prensa y en astronomy.com: la luna llena cae dentro
  del 10 % más cercano del recorrido entre el apogeo y el perigeo de su órbita
  (``distance <= perigee + 0.1 * (apogee - perigee)``). Las lunas nuevas llevan la distancia, pero
  ``supermoon`` siempre es falso: solo se llama así a la llena.

Uso: ``.venv/bin/python tools/moon_distance.py [lunations.json] [salida.json]``
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kerykeion.ephemeris_backend.backend import ephe, ephemeris_session  # noqa: E402

PASO = timedelta(minutes=10)
VENTANA = timedelta(days=15)


def _jd(t: datetime) -> float:
    return ephe.julday(t.year, t.month, t.day, t.hour + t.minute / 60 + t.second / 3600)


def _km(t: datetime) -> float:
    return ephe.calc_ut(_jd(t), ephe.MOON, ephe.FLG_SWIEPH)[0][2] * ephe.AUNIT_TO_KM


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(timezone.utc)


def _extremos(t0: datetime) -> tuple[float, float]:
    """Perigeo y apogeo de la órbita en la que cae ``t0`` (mínimo y máximo de la distancia en ±15 días)."""
    lo, hi = float("inf"), 0.0
    t = t0 - VENTANA
    fin = t0 + VENTANA
    while t <= fin:
        d = _km(t)
        lo, hi = min(lo, d), max(hi, d)
        t += PASO
    return lo, hi


def main() -> int:
    raiz = Path(__file__).resolve().parents[2] / "portal" / "data" / "calc"
    entrada = Path(sys.argv[1]) if len(sys.argv) > 1 else raiz / "lunations.json"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else entrada.with_name("moon_distance.json")
    datos = json.loads(entrada.read_text(encoding="utf-8"))
    filas = []
    with ephemeris_session():
        for lun in datos["lunations"]:
            t = _parse(lun["datetime_utc"])
            d = _km(t)
            perigeo, apogeo = _extremos(t)
            super_ = lun["phase"] == "full" and d <= perigeo + 0.1 * (apogeo - perigeo)
            filas.append({
                "phase": lun["phase"],
                "datetime_utc": lun["datetime_utc"],
                "distance_km": round(d),
                "perigee_km": round(perigeo),
                "apogee_km": round(apogeo),
                "supermoon": super_,
            })
    salida.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generator": "astroletra-calc tools/moon_distance.py",
        "ephemeris": datos.get("ephemeris"),
        "criterion": "supermoon = full moon with distance <= perigee + 0.1 * (apogee - perigee) of its orbit (Espenak)",
        "count": len(filas),
        "lunations": filas,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(1 for f in filas if f["supermoon"])
    print(f"{len(filas)} lunaciones, {n} superlunas -> {salida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
