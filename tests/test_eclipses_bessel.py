"""Elementos de Bessel de tools/eclipses_bessel.py (export/besselianos.json, JPL DE440) frente a fuentes publicadas.

Referencias consultadas el 11-11-2026:
- NASA, F. Espenak, elementos de Bessel (https://eclipse.gsfc.nasa.gov/SEbeselm/SEbeselm2001/SE2027Aug02Tbeselm.html y
  SE2026Aug12Tbeselm.html), VSOP87/ELP2000-85, ΔT 71,7 y 71,4 s.
- Skyfield 1.55 con DE421 y búsqueda topocéntrica de los contactos (tools/datos/referencias-eclipses.py de la app de
  iPhone, rama frente/c-eclipses), instantes en UTC verdadero (TT − 69,184 s) con su ΔT para la rotación.
- F. Espenak, EclipseWise, fases de los eclipses de Luna (citadas en la Wikipedia en inglés).
El resumen está en docs/ECLIPSE-MOTOR-VALIDACION.md.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

CALC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CALC / "tools"))

import eclipses_bessel as eb  # noqa: E402

EXPORT = json.loads((CALC / "export" / "besselianos.json").read_text(encoding="utf-8"))
SOL = {e["identificador"]: e for e in EXPORT["solares"]}
LUNA = {e["identificador"]: e for e in EXPORT["lunares"]}

CAMPOS_SOL = ["identificador", "maximo", "clase", "gamma", "magnitud", "t0", "validoDesde", "validoHasta", "deltaT",
              "x", "y", "d", "l1", "l2", "mu", "tanF1", "tanF2"]
CAMPOS_LUNA = ["identificador", "maximo", "clase", "magnitudUmbral", "magnitudPenumbral", "p1", "u1", "u2", "u3", "u4", "p4"]

NASA = {
    "2027-08-02-eclipse-solar": {
        "td_maximo": "10:07:49.4", "gamma": 0.1421, "magnitud": 1.0790, "clase": "total",
        "x": [-0.019645, 0.5447105, -0.0000444, -0.0000091], "y": [0.160063, -0.2111569, -0.0001217, 0.0000037],
        "d": [17.76247, -0.010181, -0.000004], "l1": [0.530596, 0.0000138, -0.0000128],
        "l2": [-0.015464, 0.0000137, -0.0000128], "mu": [328.42249, 15.002093], "tanF1": 0.0046064, "tanF2": 0.0045834,
        "duracion": 382.6,
    },
    "2026-08-12-eclipse-solar": {
        "td_maximo": "17:47:05.2", "gamma": 0.8978, "magnitud": 1.0386, "clase": "total",
        "x": [0.475593, 0.5189288, -0.0000773, -0.0000088], "y": [0.771161, -0.2301664, -0.0001245, 0.0000037],
        "d": [14.79667, -0.012065, -0.000003], "l1": [0.537954, 0.000094, -0.0000121],
        "l2": [-0.008142, 0.0000935, -0.0000121], "mu": [88.74776, 15.003093], "tanF1": 0.0046141, "tanF2": 0.0045911,
        "duracion": 138.2,
    },
}
# Diferencias admitidas, NASA − DE440. La NASA usa VSOP87/ELP2000-85: su Luna va unos 0,8 km (≈ 0,8 s) por delante de
# la de DE440 en 2026-2027, lo que mueve sobre todo x0 (1,3e-4 radios terrestres como mucho en los 12 eclipses).
TOLERANCIA = {"x": [2e-4, 2e-5, 3e-6, 2e-6], "y": [1e-4, 5e-6, 1e-6, 1e-6], "d": [3e-5, 2e-6, 1e-6],
              "l1": [3e-6, 1e-6, 1e-7], "l2": [3e-6, 1e-6, 1e-7], "mu": [1e-4, 1e-5]}

# [eclipse, lugar, lat, lon, ΔT, (C1, C2, máximo, C3, C4) en s desde 1970 UTC, magnitud]
SKYFIELD = [
    ("2027-08-02-eclipse-solar", "Cádiz", 36.5267, -6.2891, 69.08,
     (1817192445.9, 1817196325.8, 1817196412.5, 1817196499.9, 1817200776.7), 1.00766),
    ("2027-08-02-eclipse-solar", "Ceuta", 35.8892, -5.3204, 69.08,
     (1817192460.9, 1817196322.0, 1817196465.7, 1817196610.3, 1817200874.9), 1.03031),
    ("2027-08-02-eclipse-solar", "Madrid", 40.4165, -3.7026, 69.08,
     (1817192729.9, None, 1817196676.2, None, 1817200965.9), 0.87955),
    ("2027-08-02-eclipse-solar", "Luxor", 25.6989, 32.6421, 69.08,
     (1817196017.2, 1817200927.0, 1817201117.7, 1817201307.9, 1817205993.7), 1.03580),
    ("2026-08-12-eclipse-solar", "Palma", 39.5694, 2.6502, 69.10,
     (1786556285.2, 1786559466.1, 1786559514.3, 1786559562.2, 1786562553.3), 1.01522),
    ("2027-02-06-eclipse-solar", "Mar del Plata", -38.0004, -57.5562, 69.09,
     (1801921521.2, 1801927463.6, 1801927692.9, 1801927921.9, 1801933810.0), 0.95572),
    ("2028-01-26-eclipse-solar", "Sevilla", 37.3828, -5.9732, 69.07,
     (1832513672.9, 1832518342.2, 1832518560.0, 1832518777.4, 1832522872.0), 0.95490),
]


def segundos_ut(el: dict, horas: float, delta_t: float) -> float:
    base = datetime.fromisoformat(el["identificador"][:10]).replace(tzinfo=timezone.utc) + timedelta(hours=el["t0"])
    return (base + timedelta(seconds=horas * 3600 - delta_t)).timestamp()


def test_esquema_del_fichero_de_la_app():
    assert [e["identificador"][:10] for e in EXPORT["solares"]] == [
        "2026-02-17", "2026-08-12", "2027-02-06", "2027-08-02", "2028-01-26", "2028-07-22",
        "2029-01-14", "2029-06-12", "2029-07-11", "2029-12-05", "2030-06-01", "2030-11-25"]
    assert len(EXPORT["lunares"]) == 12
    for e in EXPORT["solares"]:
        for k in CAMPOS_SOL:
            assert k in e, (e["identificador"], k)
        assert len(e["x"]) == 4 and len(e["d"]) == 3 and len(e["mu"]) == 2
        assert e["maximo"].endswith("Z") and len(e["maximo"]) == 20
        assert e["validoDesde"] <= -3 and e["validoHasta"] >= 3
    for e in EXPORT["lunares"]:
        for k in CAMPOS_LUNA:
            assert k in e, (e["identificador"], k)
    clases = {e["identificador"][:10]: e["clase"] for e in EXPORT["solares"]}
    assert clases["2027-08-02"] == "total" and clases["2027-02-06"] == "anular" and clases["2029-01-14"] == "parcial"


@pytest.mark.parametrize("ident", sorted(NASA))
def test_elementos_frente_a_la_nasa(ident):
    n, m = NASA[ident], SOL[ident]
    for clave, tol in TOLERANCIA.items():
        for i, (a, b) in enumerate(zip(n[clave], m[clave])):
            assert abs(a - b) <= tol[i], f"{ident} {clave}{i}: NASA {a} DE440 {b}"
    assert abs(n["tanF1"] - m["tanF1"]) < 1e-7 and abs(n["tanF2"] - m["tanF2"]) < 1e-7
    assert abs(n["gamma"] - m["gamma"]) < 2e-4 and abs(n["magnitud"] - m["magnitud"]) < 1e-4
    assert n["clase"] == m["clase"]
    h, mi, s = n["td_maximo"].split(":")
    td_nasa = int(h) * 3600 + int(mi) * 60 + float(s)
    hh, mm, ss = m["maximoTT"][11:-1].split(":")
    td_mio = int(hh) * 3600 + int(mm) * 60 + float(ss)
    assert 0 < td_mio - td_nasa < 1.0  # la Luna de DE440 llega 0,3 a 0,8 s después
    assert abs(m["puntoMaximo"]["duracion"] - n["duracion"]) < 0.5


@pytest.mark.parametrize("fila", SKYFIELD, ids=[f"{f[0][:10]}-{f[1]}" for f in SKYFIELD])
def test_circunstancias_frente_a_skyfield(fila):
    ident, lugar, lat, lon, dt, ref, mag = fila
    el = SOL[ident]
    c = eb.circunstancias(el, lat, lon, 0.0, dt)
    assert c is not None
    for k, r in zip(("c1", "c2", "maximo", "c3", "c4"), ref):
        t = c["contactos"][k]
        assert (t is None) == (r is None), (lugar, k)
        if r is None or k == "maximo":
            continue
        # La referencia es UTC (TT − 69,184 s); el motor da UT = TT − ΔT.
        d = segundos_ut(el, t, dt) - (r + 69.184 - dt)
        assert abs(d) < 0.4, f"{lugar} {k}: {d:+.2f} s"
    assert abs(c["magnitud"] - mag) < 1e-3


def test_delta_t_del_iers():
    assert SOL["2026-08-12-eclipse-solar"]["deltaT"] == 69.2 and SOL["2026-08-12-eclipse-solar"]["deltaTOrigen"] == "observado"
    assert SOL["2027-08-02-eclipse-solar"]["deltaT"] == 69.4 and SOL["2027-08-02-eclipse-solar"]["deltaTOrigen"] == "prediccion"
    assert SOL["2028-01-26-eclipse-solar"]["deltaTOrigen"] == "extrapolado"
    fdt = eb.FuenteDeltaT(None)
    # Bulletin A del 5-11-2026: UT1 − UTC = −0,22666 s el 2-8-2027 a las 0 h.
    dt, dut, origen = fdt.delta_t(2461619.5 + 69.184 / 86400)
    assert origen == "prediccion" and abs(dut + 0.22666) < 1e-5 and abs(dt - 69.41066) < 1e-4


def test_maximo_global_en_ut_con_nuestro_delta_t():
    e = SOL["2027-08-02-eclipse-solar"]
    td = datetime.fromisoformat(e["maximoTT"].replace("Z", "+00:00"))
    ut = datetime.fromisoformat(e["maximo"].replace("Z", "+00:00"))
    assert abs((td - ut).total_seconds() - e["deltaT"]) < 0.6
    assert e["maximo"] == "2027-08-02T10:06:41Z"


# EclipseWise (Espenak), UT: P1, U1, U2, máximo, U3, U4, P4.
ECLIPSEWISE = {
    "2026-03-03-eclipse-lunar": ["08:44:22", "09:50:00", "11:04:26", "11:33:37", "12:02:45", "13:17:10", "14:22:59"],
    "2028-12-31-eclipse-lunar": ["14:03:49", "15:07:35", "16:16:19", "16:51:58", "17:27:40", "18:36:24", "19:40:02"],
    "2029-06-26-eclipse-lunar": ["00:34:34", "01:32:18", "02:31:18", "03:22:05", "04:13:01", "05:11:50", "06:09:42"],
}


@pytest.mark.parametrize("ident", sorted(ECLIPSEWISE))
def test_eclipses_de_luna_frente_a_eclipsewise(ident):
    e = LUNA[ident]
    for k, h in zip(("p1", "u1", "u2", "maximo", "u3", "u4", "p4"), ECLIPSEWISE[ident]):
        mio = datetime.fromisoformat(e[k].replace("Z", "+00:00"))
        ref = datetime.fromisoformat(f"{e[k][:10]}T{h}+00:00")
        # Misma sombra de Danjon; Espenak usa otro ΔT y otras efemérides (hasta unos 10 s en estas fases).
        assert abs((mio - ref).total_seconds()) < 15, (ident, k)


BSP = Path(os.environ.get("ASTROLETRA_DE440", Path.home() / "Library/Caches/astroletra-efemerides/de440s.bsp"))


@pytest.mark.skipif(not BSP.exists(), reason="sin el fichero DE440 de NAIF (ASTROLETRA_DE440)")
def test_el_fichero_se_regenera_igual(tmp_path):
    salida = tmp_path / "besselianos.json"
    assert eb.main(["--bsp", str(BSP), "--salida", str(salida)]) == 0
    assert json.loads(salida.read_text(encoding="utf-8")) == EXPORT
