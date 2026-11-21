#!/usr/bin/env python3
"""Elementos besselianos de los eclipses de Sol y fases de los de Luna, con las efemérides JPL DE440.

Escribe un único JSON (por defecto ``calc/export/besselianos.json``) con el esquema del
``eclipses.json`` de la app de iPhone (claves ``fuente``, ``solares`` y ``lunares``), para que la web
y la app lean el mismo fichero. La web lo publica en ``/datos/eclipses-besselianos.json``.

Método (Explanatory Supplement to the Astronomical Almanac, 3.ª ed., cap. 11; J. Meeus, «Elements
of Solar Eclipses 1951-2200», 1989):

1. Posiciones aparentes geocéntricas del Sol y de la Luna (tiempo de luz y aberración, ecuador y
   equinoccio verdaderos de la fecha; sin deflexión de la luz) con DE440 a través de Skyfield.
2. Eje de la sombra: la recta que une la Luna con el Sol. Su dirección da ``d`` (declinación) y ``a``
   (ascensión recta); ``x``, ``y`` y ``z`` son las coordenadas de la Luna en el plano fundamental, en
   radios ecuatoriales terrestres (WGS84, 6378,137 km).
3. ``mu`` es el ángulo horario de efemérides del eje en Greenwich: tiempo sidéreo aparente de Greenwich
   (IAU 2006/2000A) calculado con UT1 = TT, menos ``a``. Igual que en las tablas de la NASA, el lector
   resta 1,002738 × 15 × ΔT / 3600 = 0,00417807 × ΔT grados a la longitud.
4. Conos de penumbra y umbra con el radio solar de 959,63" a 1 ua y los radios lunares k1 = 0,272488
   (contactos exteriores) y k2 = 0,272281 (contactos interiores), los de la NASA:
   sen f1 = (R☉ + k1) / G, sen f2 = (R☉ − k2) / G; l1 = z·tan f1 + k1 / cos f1; l2 = z·tan f2 − k2 / cos f2.
5. Ajuste por mínimos cuadrados (un punto cada 5 min) a polinomios en t = horas TT desde ``t0`` (la hora
   entera TT más próxima al máximo): x e y de grado 3, d, l1 y l2 de grado 2, mu de grado 1, y tan f1 y
   tan f2 constantes (valor en t0). Los mismos grados que la NASA, comprobando el residuo.

ΔT (TT − UT1): uno por eclipse, ``deltaT = 32,184 + (TAI − UTC) − (UT1 − UTC)`` con UT1 − UTC del
IERS: valores observados para los eclipses pasados, la predicción del IERS Bulletin A para el año
siguiente (finals2000A, que la incluye) y, más allá, la fórmula de extrapolación del mismo boletín.
Las horas del fichero son UT = TT − ΔT redondeadas al segundo, como las de la NASA; UT1 y UTC difieren
menos de 0,9 s y aquí, en 2027, unos 0,2 s.

Eclipses de Luna: instantes de cada fase con la sombra de la Tierra aumentada por la regla de Danjon
(1/85 del radio terrestre, achatamiento incluido) y radio lunar 0,2725076, como el catálogo de la app.

Uso:
    cd calc && .venv/bin/python -I tools/eclipses_bessel.py --bsp RUTA/de440s.bsp \\
        [--finals RUTA/finals2000A.all] [--desde 2026-01-01 --hasta 2031-01-01] [--salida export/besselianos.json]

El fichero de efemérides es el de NAIF (https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp,
MD5 3917ee56769db332790c751e2168843d). Sin ``--finals`` se usan los UT1 − UTC guardados abajo (IERS, 5-11-2026).
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import erfa
import numpy as np
from skyfield import almanac
from skyfield.api import load, load_file

ESQUEMA = 1
UA_KM = 149_597_870.700
A_KM = 6378.137  # radio ecuatorial WGS84
F = 1 / 298.257223563  # achatamiento WGS84
E2 = F * (2 - F)
SD_SOL = 959.63  # semidiámetro del Sol a 1 ua (Auwers), segundos de arco
R_SOL_KM = UA_KM * math.sin(math.radians(SD_SOL / 3600))
R_SOL = R_SOL_KM / A_KM  # radios terrestres
K1, K2 = 0.272488, 0.272281
K_LUNA = 0.2725076  # radio lunar para los eclipses de Luna
R_SOL_KM_LUNARES = 696_000.0
APLANAMIENTO_DANJON = 0.998340
TT_MENOS_TAI = 32.184
TAI_MENOS_UTC = 37.0  # desde el 1-1-2017; el IERS no anuncia más saltos (Bulletin C 72, julio de 2026)
GIRO = 1.002737909350795 * 15 / 3600  # grados de giro de la Tierra por segundo de UT1
PASO_AJUSTE_MIN = 5
GRADOS = {"x": 3, "y": 3, "d": 2, "l1": 2, "l2": 2, "mu": 1}
DECIMALES = {"x": 8, "y": 8, "d": 7, "l1": 8, "l2": 8, "mu": 7}

# UT1 − UTC (s) a las 0 h UTC de cada día, del IERS (fichero finals2000A.all, servicio rápido, descargado de
# datacenter.iers.org el 11-11-2026; valores «I» observados y «P» predicción del Bulletin A vol. XXXIX
# n.º 045 del 5-11-2026). Solo los días que rodean a cada eclipse de 2026 a 2027; para los siguientes se usa
# la fórmula de extrapolación del boletín (ver ``ut1_menos_utc``).
UT1_UTC_IERS: dict[int, tuple[str, float]] = {
    61088: ("I", 0.0699024), 61089: ("I", 0.0695699),  # 2026-02-17/18
    61102: ("I", 0.0663804), 61103: ("I", 0.0656668),  # 2026-03-03/04
    61264: ("I", 0.0116154), 61265: ("I", 0.0111494),  # 2026-08-12/13
    61280: ("I", 0.0058987), 61281: ("I", 0.0050784),  # 2026-08-28/29
    61442: ("P", -0.1466091), 61443: ("P", -0.1475377),  # 2027-02-06/07
    61456: ("P", -0.1609834), 61457: ("P", -0.1625444),  # 2027-02-20/21
    61604: ("P", -0.2418103), 61605: ("P", -0.2405219),  # 2027-07-18/19
    61619: ("P", -0.2266626), 61620: ("P", -0.2260067),  # 2027-08-02/03
    61634: ("P", -0.2138844), 61635: ("P", -0.2133543),  # 2027-08-17/18
}
BOLETIN = "IERS Bulletin A vol. XXXIX n.º 045 (5-11-2026)"
# Fórmula del boletín para extender la predicción: UT1−UTC = −0,1139 − 0,00044 (MJD − 61356) − (UT2 − UT1).
FORMULA_MJD0, FORMULA_A, FORMULA_B = 61356, -0.1139, -0.00044


def mjd_de(jd_utc: float) -> float:
    return jd_utc - 2400000.5


def ut2_menos_ut1(mjd: float) -> float:
    """Variación estacional del IERS (Bulletin A), con T en años besselianos."""
    t = 2000.0 + (mjd - 51544.03) / 365.2422
    p = 2 * math.pi * t
    return 0.022 * math.sin(p) - 0.012 * math.cos(p) - 0.006 * math.sin(2 * p) + 0.007 * math.cos(2 * p)


class FuenteDeltaT:
    """UT1 − UTC del IERS: tabla diaria (observado o predicho) o fórmula de extrapolación del boletín."""

    def __init__(self, finals: Path | None):
        self.tabla: dict[int, tuple[str, float]] = dict(UT1_UTC_IERS)
        if finals:
            for linea in finals.read_text().splitlines():
                if len(linea) < 68:
                    continue
                try:
                    mjd, bandera, valor = int(float(linea[7:15])), linea[57], float(linea[58:68])
                except ValueError:
                    continue
                if bandera in "IP":
                    self.tabla[mjd] = (bandera, valor)

    def ut1_menos_utc(self, mjd: float) -> tuple[float, str]:
        a, b = int(math.floor(mjd)), int(math.floor(mjd)) + 1
        if a in self.tabla and b in self.tabla:
            fa, va = self.tabla[a]
            fb, vb = self.tabla[b]
            origen = "observado" if fa == fb == "I" else "prediccion"
            return va + (vb - va) * (mjd - a), origen
        v = FORMULA_A + FORMULA_B * (mjd - FORMULA_MJD0) - ut2_menos_ut1(mjd)
        return v, "extrapolado"

    def delta_t(self, jd_tt: float) -> tuple[float, float, str]:
        """(ΔT, UT1 − UTC, origen) en el instante ``jd_tt``."""
        mjd = jd_tt - 2400000.5 - (TT_MENOS_TAI + TAI_MENOS_UTC) / 86400
        dut, origen = self.ut1_menos_utc(mjd)
        return TT_MENOS_TAI + TAI_MENOS_UTC - dut, dut, origen


# --------------------------------------------------------------------------------------------------
# Posiciones y elementos instantáneos


class Efemeride:
    def __init__(self, bsp: Path):
        self.ts = load.timescale(builtin=True)
        self.eph = load_file(str(bsp))
        self.tierra, self.sol, self.luna = self.eph["earth"], self.eph["sun"], self.eph["moon"]

    def sol_luna(self, jd_tt):
        """Ascensión recta, declinación (rad) y distancia (km) aparentes geocéntricas del Sol y la Luna."""
        t = self.ts.tt_jd(jd_tt)
        e = self.tierra.at(t)
        s = e.observe(self.sol).apparent(deflectors=())
        m = e.observe(self.luna).apparent(deflectors=())
        ra_s, de_s, di_s = s.radec(epoch="date")
        ra_m, de_m, di_m = m.radec(epoch="date")
        return ra_s.radians, de_s.radians, di_s.km, ra_m.radians, de_m.radians, di_m.km


def gast_efemerides(jd_tt) -> np.ndarray:
    """Tiempo sidéreo aparente de Greenwich (rad) con UT1 = TT: el que define el ángulo horario de efemérides."""
    jd = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    j1 = np.floor(jd - 0.5) + 0.5
    j2 = jd - j1
    return erfa.gst06a(j1, j2, j1, j2)


def unitario(ra, de):
    return np.array([np.cos(de) * np.cos(ra), np.cos(de) * np.sin(ra), np.sin(de)])


def elementos_instantaneos(ef: Efemeride, jd_tt) -> dict[str, np.ndarray]:
    jd_tt = np.atleast_1d(np.asarray(jd_tt, dtype=float))
    ra_s, de_s, di_s, ra_m, de_m, di_m = ef.sol_luna(jd_tt)
    S = unitario(ra_s, de_s) * (di_s / A_KM)
    M = unitario(ra_m, de_m) * (di_m / A_KM)
    G = S - M
    g = np.linalg.norm(G, axis=0)
    a = np.arctan2(G[1], G[0])
    d = np.arcsin(G[2] / g)
    i = np.array([-np.sin(a), np.cos(a), np.zeros_like(a)])
    j = np.array([-np.sin(d) * np.cos(a), -np.sin(d) * np.sin(a), np.cos(d)])
    k = np.array([np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d)])
    x = np.sum(M * i, axis=0)
    y = np.sum(M * j, axis=0)
    z = np.sum(M * k, axis=0)
    sf1 = (R_SOL + K1) / g
    sf2 = (R_SOL - K2) / g
    cf1, cf2 = np.sqrt(1 - sf1**2), np.sqrt(1 - sf2**2)
    tf1, tf2 = sf1 / cf1, sf2 / cf2
    l1 = z * tf1 + K1 / cf1
    l2 = z * tf2 - K2 / cf2
    mu = np.degrees(gast_efemerides(jd_tt) - a) % 360.0
    return {"x": x, "y": y, "z": z, "d": np.degrees(d), "mu": mu, "l1": l1, "l2": l2, "tanF1": tf1, "tanF2": tf2}


# --------------------------------------------------------------------------------------------------
# Ajuste polinómico


def ajustar(ef: Efemeride, jd_t0: float, desde_h: float, hasta_h: float) -> tuple[dict, dict]:
    n = int(round((hasta_h - desde_h) * 60 / PASO_AJUSTE_MIN)) + 1
    t = np.linspace(desde_h, hasta_h, n)
    el = elementos_instantaneos(ef, jd_t0 + t / 24)
    el["mu"] = np.degrees(np.unwrap(np.radians(el["mu"])))
    coef, residuo = {}, {}
    for clave, grado in GRADOS.items():
        c = np.polynomial.polynomial.polyfit(t, el[clave], grado)
        r = el[clave] - np.polynomial.polynomial.polyval(t, c)
        if clave == "mu":
            c[0] %= 360.0
        coef[clave] = [round(float(v), DECIMALES[clave]) for v in c]
        residuo[clave] = float(np.max(np.abs(r)))
    i0 = int(np.argmin(np.abs(t)))
    coef["tanF1"] = round(float(el["tanF1"][i0]), 8)
    coef["tanF2"] = round(float(el["tanF2"][i0]), 8)
    residuo["tanF1"] = float(np.max(np.abs(el["tanF1"] - coef["tanF1"])))
    residuo["tanF2"] = float(np.max(np.abs(el["tanF2"] - coef["tanF2"])))
    return coef, residuo


def pol(c, t):
    return np.polynomial.polynomial.polyval(t, c)


def der(c, t):
    return np.polynomial.polynomial.polyval(t, np.polynomial.polynomial.polyder(c))


# --------------------------------------------------------------------------------------------------
# Circunstancias locales


class Lugar:
    def __init__(self, el: dict, latitud: float, longitud: float, altitud: float, delta_t: float):
        self.el = el
        fi = math.radians(latitud)
        u = math.atan((1 - F) * math.tan(fi))
        h = altitud / (A_KM * 1000)
        self.rs = (1 - F) * math.sin(u) + h * math.sin(fi)
        self.rc = math.cos(u) + h * math.cos(fi)
        self.fi = fi
        self.lam = longitud - GIRO * delta_t
        self.delta_t = delta_t

    def estado(self, t: float) -> dict:
        e = self.el
        x, y = pol(e["x"], t), pol(e["y"], t)
        dx, dy = der(e["x"], t), der(e["y"], t)
        d = math.radians(pol(e["d"], t))
        dd = math.radians(der(e["d"], t))
        dmu = math.radians(der(e["mu"], t))
        h = math.radians(pol(e["mu"], t) + self.lam)
        xi = self.rc * math.sin(h)
        eta = self.rs * math.cos(d) - self.rc * math.cos(h) * math.sin(d)
        zeta = self.rs * math.sin(d) + self.rc * math.cos(h) * math.cos(d)
        dxi = dmu * self.rc * math.cos(h)
        deta = dmu * xi * math.sin(d) - zeta * dd
        return {
            "u": x - xi, "v": y - eta, "a": dx - dxi, "b": dy - deta,
            "L1": pol(e["l1"], t) - zeta * e["tanF1"], "L2": pol(e["l2"], t) - zeta * e["tanF2"],
            "h": h, "d": d, "zeta": zeta,
        }

    def maximo(self) -> float | None:
        t = 0.0
        for _ in range(20):
            s = self.estado(t)
            tau = -(s["u"] * s["a"] + s["v"] * s["b"]) / (s["a"] ** 2 + s["b"] ** 2)
            t += tau
            if abs(tau) < 1e-7:
                break
        e = self.el
        return t if math.isfinite(t) and e["validoDesde"] - 1 < t < e["validoHasta"] + 1 else None

    def contacto(self, exterior: bool, signo: float, t_max: float) -> float | None:
        t = t_max
        for _ in range(30):
            s = self.estado(t)
            l = s["L1"] if exterior else abs(s["L2"])
            n = math.hypot(s["a"], s["b"])
            seno = (s["a"] * s["v"] - s["u"] * s["b"]) / (n * l)
            if abs(seno) > 1:
                return None
            tau = -(s["u"] * s["a"] + s["v"] * s["b"]) / n**2 + signo * l / n * math.sqrt(1 - seno * seno)
            t += tau
            if abs(tau) < 1e-8:
                return t
        return t

    def sol(self, s: dict) -> tuple[float, float]:
        fi, d, h = self.fi, s["d"], s["h"]
        alt = math.asin(math.sin(fi) * math.sin(d) + math.cos(fi) * math.cos(d) * math.cos(h))
        az = math.atan2(math.sin(h), math.cos(h) * math.sin(fi) - math.tan(d) * math.cos(fi))
        return math.degrees(alt), (math.degrees(az) + 180) % 360


def tapado(c: float, k: float) -> float:
    if c >= 1 + k:
        return 0.0
    if c <= abs(1 - k):
        return min(1.0, k * k)
    a1 = k * k * math.acos((c * c + k * k - 1) / (2 * c * k))
    a2 = math.acos((c * c + 1 - k * k) / (2 * c))
    a3 = 0.5 * math.sqrt((-c + k + 1) * (c + k - 1) * (c - k + 1) * (c + k + 1))
    return (a1 + a2 - a3) / math.pi


def circunstancias(el: dict, latitud: float, longitud: float, altitud: float = 0.0, delta_t: float | None = None) -> dict | None:
    """Contactos en horas TT desde t0 (sin redondear), tipo, magnitud y oscurecimiento. Nada si no hay eclipse."""
    dt = el["deltaT"] if delta_t is None else delta_t
    lugar = Lugar(el, latitud, longitud, altitud, dt)
    t_max = lugar.maximo()
    if t_max is None:
        return None
    s = lugar.estado(t_max)
    m = math.hypot(s["u"], s["v"])
    if m >= s["L1"]:
        return None
    t1 = lugar.contacto(True, -1, t_max)
    t4 = lugar.contacto(True, 1, t_max)
    if t1 is None or t4 is None:
        return None
    tipo, t2, t3 = "parcial", None, None
    if m < abs(s["L2"]):
        tipo = "total" if s["L2"] < 0 else "anular"
        t2 = lugar.contacto(False, -1, t_max)
        t3 = lugar.contacto(False, 1, t_max)
    r_sol = (s["L1"] + s["L2"]) / 2
    k = (s["L1"] - s["L2"]) / 2 / r_sol
    contactos = {"c1": t1, "c2": t2, "maximo": t_max, "c3": t3, "c4": t4}
    soles = {c: (lugar.sol(lugar.estado(t)) if t is not None else None) for c, t in contactos.items()}
    return {
        "tipo": tipo, "contactos": contactos, "sol": soles, "deltaT": dt,
        "magnitud": (s["L1"] - m) / (s["L1"] + s["L2"]),
        "oscurecimiento": tapado(m / r_sol, k),
        "duracion": (t3 - t2) * 3600 if t2 is not None and t3 is not None else None,
    }


# --------------------------------------------------------------------------------------------------
# Circunstancias globales a partir de los polinomios


def eje_en_tierra(el: dict, t: float, delta_t: float) -> tuple[float, float, float] | None:
    """Punto donde el eje corta el elipsoide en t: latitud y longitud geodésicas (grados) y ζ. Nada si no lo corta."""
    x, y, d = pol(el["x"], t), pol(el["y"], t), math.radians(pol(el["d"], t))
    c = E2 / (1 - E2)
    qa = 1 + c * math.sin(d) ** 2
    qb = 2 * c * y * math.cos(d) * math.sin(d)
    qc = c * (y * math.cos(d)) ** 2 - (1 - x * x - y * y)
    disc = qb * qb - 4 * qa * qc
    if disc < 0:
        return None
    zeta = (-qb + math.sqrt(disc)) / (2 * qa)
    return punto_geodesico(el, t, x, y, zeta, delta_t) + (zeta,)


def punto_geodesico(el: dict, t: float, xi: float, eta: float, zeta: float, delta_t: float) -> tuple[float, float]:
    d = math.radians(pol(el["d"], t))
    z_ecu = eta * math.cos(d) + zeta * math.sin(d)
    p_cos = zeta * math.cos(d) - eta * math.sin(d)
    h = math.degrees(math.atan2(xi, p_cos))
    p = math.hypot(xi, p_cos)
    lat = math.degrees(math.atan2(z_ecu, (1 - E2) * p))
    lon = (h - pol(el["mu"], t) + GIRO * delta_t + 180) % 360 - 180
    return lat, lon


def minimo_m(el: dict) -> float:
    """Instante (h desde t0) en que el eje pasa más cerca del centro de la Tierra."""
    t = 0.0
    for _ in range(30):
        x, y = pol(el["x"], t), pol(el["y"], t)
        dx, dy = der(el["x"], t), der(el["y"], t)
        tau = -(x * dx + y * dy) / (dx * dx + dy * dy)
        t += tau
        if abs(tau) < 1e-9:
            break
    return t


def distancia_al_contorno(el: dict, t: float) -> float:
    """Distancia del eje al contorno de la Tierra en el plano fundamental (negativa si lo corta), con el achatamiento."""
    x, y, d = pol(el["x"], t), pol(el["y"], t), math.radians(pol(el["d"], t))
    rho1 = math.sqrt(1 - E2 * math.cos(d) ** 2)
    # Elipse de semiejes 1 (ξ) y rho1 (η): punto más cercano por iteración en el ángulo excéntrico.
    th = math.atan2(y / rho1, x)
    for _ in range(50):
        cx, cy = math.cos(th), rho1 * math.sin(th)
        tx, ty = -math.sin(th), rho1 * math.cos(th)
        f = (x - cx) * tx + (y - cy) * ty
        df = -(tx * tx + ty * ty) + (x - cx) * (-math.cos(th)) + (y - cy) * (-rho1 * math.sin(th))
        paso = f / df
        th -= paso
        if abs(paso) < 1e-12:
            break
    dist = math.hypot(x - math.cos(th), y - rho1 * math.sin(th))
    dentro = (x * x + (y / rho1) ** 2) < 1
    return -dist if dentro else dist


def raiz(f, a: float, b: float, tol: float = 1e-9) -> float:
    fa, fb = f(a), f(b)
    if fa * fb > 0:
        raise ValueError("sin cambio de signo")
    for _ in range(200):
        c = (a + b) / 2
        fc = f(c)
        if fa * fc <= 0:
            b, fb = c, fc
        else:
            a, fa = c, fc
        if b - a < tol:
            break
    return (a + b) / 2


def globales(el: dict, delta_t: float) -> dict:
    """Máximo, gamma, magnitud, clase y contactos globales P1, U1, U4 y P4 (horas TT desde t0)."""
    t_ge = minimo_m(el)
    x, y = pol(el["x"], t_ge), pol(el["y"], t_ge)
    m = math.hypot(x, y)
    gamma = math.copysign(m, y)
    lo, hi = el["validoDesde"] - 2, el["validoHasta"] + 2

    def penumbra(t):
        return distancia_al_contorno(el, t) - pol(el["l1"], t)

    p1 = raiz(penumbra, lo, t_ge)
    p4 = raiz(penumbra, t_ge, hi)
    central = distancia_al_contorno(el, t_ge) < 0
    res = {"t_ge": t_ge, "gamma": gamma, "p1": p1, "p4": p4, "u1": None, "u4": None, "central": central}
    if central:
        def eje(t):
            return distancia_al_contorno(el, t)
        res["u1"] = raiz(eje, lo, t_ge)
        res["u4"] = raiz(eje, t_ge, hi)
        lat, lon, zeta = eje_en_tierra(el, t_ge, delta_t)
        L1 = pol(el["l1"], t_ge) - zeta * el["tanF1"]
        L2 = pol(el["l2"], t_ge) - zeta * el["tanF2"]
        res["magnitud"] = (L1 - L2) / (L1 + L2)
        # Clase por el signo de L2 a lo largo de la línea central.
        signos = set()
        for t in np.linspace(res["u1"] + 1e-4, res["u4"] - 1e-4, 400):
            p = eje_en_tierra(el, float(t), delta_t)
            if p is None:
                continue
            signos.add(pol(el["l2"], float(t)) - p[2] * el["tanF2"] < 0)
        res["clase"] = "hibrido" if len(signos) == 2 else ("total" if True in signos else "anular")
        res["punto"] = (lat, lon)
    else:
        # Máximo de un parcial: en el borde de la Tierra (ζ = 0), con el punto del contorno más cercano al eje.
        dist = distancia_al_contorno(el, t_ge)
        L1, L2 = pol(el["l1"], t_ge), pol(el["l2"], t_ge)
        res["magnitud"] = (L1 - dist) / (L1 + L2)
        res["clase"] = "parcial"
    return res


# --------------------------------------------------------------------------------------------------
# Búsqueda de eclipses


def iso(dtm: datetime, decimas: bool = False) -> str:
    if decimas:
        s = (dtm + timedelta(microseconds=50_000)).replace(tzinfo=None).isoformat(timespec="milliseconds")
        return s[:-2] + "Z"
    return (dtm + timedelta(microseconds=500_000)).replace(microsecond=0, tzinfo=None).isoformat() + "Z"


def jd_a_datetime(jd: float) -> datetime:
    return datetime(2000, 1, 1, 12, tzinfo=timezone.utc) + timedelta(days=jd - 2451545.0)


def eclipses_de_sol(ef: Efemeride, fdt: FuenteDeltaT, desde: date, hasta: date) -> tuple[list, list]:
    t0, t1 = ef.ts.utc(desde.year, desde.month, desde.day), ef.ts.utc(hasta.year, hasta.month, hasta.day)
    tiempos, fases = almanac.find_discrete(t0, t1, almanac.moon_phases(ef.eph))
    salida, informe = [], []
    for t, fase in zip(tiempos, fases):
        if fase != 0:
            continue
        jd = float(t.tt)
        horas = np.linspace(-6, 6, 145)
        el = elementos_instantaneos(ef, jd + horas / 24)
        m = np.hypot(el["x"], el["y"])
        i = int(np.argmin(m))
        if m[i] > 1.0 + el["l1"][i] + 0.02:
            continue
        jd_ge = jd + horas[i] / 24
        # t0: hora entera TT más próxima al máximo; día del identificador: el de t0 en TT.
        hora = (jd_ge - 0.5) % 1 * 24
        jd_t0 = jd_ge + (round(hora) - hora) / 24
        delta_t, dut, origen = fdt.delta_t(jd_ge)
        delta_t = round(delta_t, 1)
        desde_h, hasta_h = -3.0, 3.0
        coef, _ = ajustar(ef, jd_t0, desde_h, hasta_h)
        t_ge0 = minimo_m(coef)
        if distancia_al_contorno(coef, t_ge0) - pol(coef["l1"], t_ge0) >= 0:
            continue  # la penumbra no llega a tocar la Tierra
        for _ in range(3):
            coef, residuo = ajustar(ef, jd_t0, desde_h, hasta_h)
            el_pol = dict(coef, validoDesde=desde_h, validoHasta=hasta_h, deltaT=delta_t)
            g = globales(el_pol, delta_t)
            nuevo_desde = min(-3.0, math.floor((g["p1"] - 0.25) * 2) / 2)
            nuevo_hasta = max(3.0, math.ceil((g["p4"] + 0.25) * 2) / 2)
            if (nuevo_desde, nuevo_hasta) == (desde_h, hasta_h):
                break
            desde_h, hasta_h = nuevo_desde, nuevo_hasta
        dia_t0 = jd_a_datetime(jd_t0).date()
        t0_horas = round(((jd_t0 - 0.5) % 1) * 24)
        base_tt = datetime(dia_t0.year, dia_t0.month, dia_t0.day, tzinfo=timezone.utc) + timedelta(hours=t0_horas)

        def ut(h):
            return base_tt + timedelta(seconds=h * 3600 - delta_t)

        ident = f"{dia_t0.isoformat()}-eclipse-solar"
        entrada = {
            "identificador": ident,
            "maximo": iso(ut(g["t_ge"])),
            "clase": {"total": "total", "anular": "anular", "parcial": "parcial", "hibrido": "hibrido"}[g["clase"]],
            "gamma": round(g["gamma"], 4),
            "magnitud": round(g["magnitud"], 4),
            "t0": float(t0_horas),
            "validoDesde": desde_h,
            "validoHasta": hasta_h,
            "deltaT": delta_t,
            "x": coef["x"], "y": coef["y"], "d": coef["d"], "l1": coef["l1"], "l2": coef["l2"], "mu": coef["mu"],
            "tanF1": coef["tanF1"], "tanF2": coef["tanF2"],
            # Campos añadidos (la app no los necesita): origen del ΔT y contactos globales.
            "deltaTOrigen": origen,
            "maximoTT": iso(base_tt + timedelta(seconds=g["t_ge"] * 3600), decimas=True),
            "globales": {
                "p1": iso(ut(g["p1"])), "u1": iso(ut(g["u1"])) if g["u1"] is not None else None,
                "u4": iso(ut(g["u4"])) if g["u4"] is not None else None, "p4": iso(ut(g["p4"])),
            },
        }
        if g["central"]:
            lat, lon = g["punto"]
            c = circunstancias(dict(el_pol), lat, lon, 0.0, delta_t)
            entrada["puntoMaximo"] = {
                "latitud": round(lat, 4), "longitud": round(lon, 4),
                "alturaSol": round(c["sol"]["maximo"][0], 1), "acimutSol": round(c["sol"]["maximo"][1], 1),
                "duracion": round(c["duracion"], 1) if c["duracion"] is not None else None,
            }
        salida.append(entrada)
        informe.append({"identificador": ident, "residuo": residuo, "ut1MenosUtc": round(dut, 4), "deltaTExacto": fdt.delta_t(jd_ge)[0]})
    return salida, informe


# --------------------------------------------------------------------------------------------------
# Eclipses de Luna (regla de Danjon)


def eclipses_de_luna(ef: Efemeride, fdt: FuenteDeltaT, desde: date, hasta: date) -> list:
    t0, t1 = ef.ts.utc(desde.year, desde.month, desde.day), ef.ts.utc(hasta.year, hasta.month, hasta.day)
    tiempos, fases = almanac.find_discrete(t0, t1, almanac.moon_phases(ef.eph))

    def geometria(jd):
        ra_s, de_s, di_s, ra_m, de_m, di_m = ef.sol_luna(np.atleast_1d(jd))
        s, m = unitario(ra_s, de_s), unitario(ra_m, de_m)
        sep = np.pi - np.arccos(np.clip(np.sum(s * m, axis=0), -1, 1))
        pi_l = np.arcsin(A_KM / di_m)
        pi_s = np.arcsin(A_KM / di_s)
        s_s = np.arcsin(R_SOL_KM_LUNARES / di_s)
        s_l = np.arcsin(K_LUNA * A_KM / di_m)
        base = APLANAMIENTO_DANJON * pi_l + pi_s
        return sep, base - s_s + pi_l / 85, base + s_s + pi_l / 85, s_l

    salida = []
    for t, fase in zip(tiempos, fases):
        if fase != 2:
            continue
        jd = float(t.tt)
        horas = np.linspace(-6, 6, 721)
        sep, umbra, penumbra, s_l = geometria(jd + horas / 24)
        i = int(np.argmin(sep))
        if sep[i] >= penumbra[i] + s_l[i]:
            continue
        # Máximo: mínimo de la distancia al eje de la sombra, por sección áurea.
        a, b = jd + horas[max(i - 1, 0)] / 24, jd + horas[min(i + 1, len(horas) - 1)] / 24
        r = (math.sqrt(5) - 1) / 2
        for _ in range(80):
            c, d = b - r * (b - a), a + r * (b - a)
            if geometria(c)[0][0] < geometria(d)[0][0]:
                b = d
            else:
                a = c
        jd_max = (a + b) / 2
        sep0, umbra0, penumbra0, s_l0 = (float(v[0]) for v in geometria(jd_max))
        mag_p = (penumbra0 + s_l0 - sep0) / (2 * s_l0)
        mag_u = (umbra0 + s_l0 - sep0) / (2 * s_l0)
        delta_t, _, origen = fdt.delta_t(jd_max)
        delta_t = round(delta_t, 1)

        def instante(jd_tt):
            return iso(jd_a_datetime(jd_tt) - timedelta(seconds=delta_t))

        def contacto(objetivo, signo):
            def f(x):
                g = geometria(x)
                return float(g[0][0] - objetivo(g))
            extremo = jd_max + signo * 0.3
            return raiz(f, extremo, jd_max, 1e-9) if signo < 0 else raiz(f, jd_max, extremo, 1e-9)

        def par(objetivo, hay):
            return (contacto(objetivo, -1), contacto(objetivo, 1)) if hay else (None, None)

        p1, p4 = par(lambda g: g[2][0] + g[3][0], True)
        u1, u4 = par(lambda g: g[1][0] + g[3][0], mag_u > 0)
        u2, u3 = par(lambda g: g[1][0] - g[3][0], mag_u >= 1)
        clase = "total" if mag_u >= 1 else "parcial" if mag_u > 0 else "penumbral"
        maximo = instante(jd_max)
        salida.append({
            "identificador": f"{maximo[:10]}-eclipse-lunar",
            "maximo": maximo, "clase": clase,
            "magnitudUmbral": round(mag_u, 4), "magnitudPenumbral": round(mag_p, 4),
            "p1": instante(p1), "u1": instante(u1) if u1 else None, "u2": instante(u2) if u2 else None,
            "u3": instante(u3) if u3 else None, "u4": instante(u4) if u4 else None, "p4": instante(p4),
            "deltaT": delta_t, "deltaTOrigen": origen,
        })
    return salida


# --------------------------------------------------------------------------------------------------


def main(argv=None) -> int:
    raiz_calc = Path(__file__).resolve().parents[1]
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bsp", type=Path, required=True, help="de440s.bsp o de440.bsp de NAIF")
    p.add_argument("--finals", type=Path, help="finals2000A.all del IERS (si no, los valores guardados)")
    p.add_argument("--desde", default="2026-01-01")
    p.add_argument("--hasta", default="2031-01-01")
    p.add_argument("--salida", type=Path, default=raiz_calc / "export" / "besselianos.json")
    p.add_argument("--informe", type=Path, help="JSON con residuos del ajuste y ΔT sin redondear")
    a = p.parse_args(argv)
    ef = Efemeride(a.bsp)
    fdt = FuenteDeltaT(a.finals)
    desde, hasta = date.fromisoformat(a.desde), date.fromisoformat(a.hasta)
    solares, informe = eclipses_de_sol(ef, fdt, desde, hasta)
    lunares = eclipses_de_luna(ef, fdt, desde, hasta)
    datos = {
        "esquema": ESQUEMA,
        "fuente": {
            "solares": "Elementos de Bessel calculados por Astroletra con las efemérides JPL DE440 (NASA JPL), "
                       "posiciones aparentes geocéntricas, k1 = 0,272488, k2 = 0,272281, Sol de 959,63\". "
                       "Tiempo dinámico (TT); mu es ángulo horario de efemérides.",
            "lunares": "Calculados por Astroletra con JPL DE440, sombra con el aumento de Danjon, radio lunar 0,2725076.",
            "deltaT": f"ΔT = 32,184 s + 37 s − (UT1 − UTC), con UT1 − UTC del IERS: observado para los eclipses pasados, "
                      f"predicción del {BOLETIN} hasta noviembre de 2027 y la fórmula de extrapolación del mismo "
                      f"boletín después. Las horas son UT = TT − ΔT.",
            "licencia": "CC BY 4.0, Astroletra (astroletra.com)",
        },
        "constantes": {
            "efemerides": "JPL DE440", "elipsoide": "WGS84", "radioEcuatorialKm": A_KM,
            "achatamiento": round(F, 12), "semidiametroSol": SD_SOL, "k1": K1, "k2": K2,
            "kLunares": K_LUNA, "sombraLunares": "Danjon",
            "grados": GRADOS,
        },
        "solares": solares,
        "lunares": lunares,
    }
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    a.salida.write_text(json.dumps(datos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"escrito {a.salida}: {len(solares)} eclipses de Sol y {len(lunares)} de Luna")
    if a.informe:
        a.informe.write_text(json.dumps(informe, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for r in informe:
        peor = max(r["residuo"][k] for k in ("x", "y"))
        print(f"  {r['identificador']}: residuo x/y {peor:.2e}, d {r['residuo']['d']:.1e}°, mu {r['residuo']['mu']:.1e}°, "
              f"l1 {r['residuo']['l1']:.1e}, l2 {r['residuo']['l2']:.1e}, ΔT {r['deltaTExacto']:.3f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
