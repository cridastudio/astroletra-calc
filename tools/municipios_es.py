#!/usr/bin/env python3
"""Municipios de España con las coordenadas de su capital, su población y su slug, de fuentes abiertas (11-11-2026).

Escribe ``portal/data/municipios-es.csv`` (UTF-8, comas, una fila por municipio):

    slug, ine, nombre, nombre_ine, provincia, cpro, latitud, longitud, poblacion, fuente, metodo, revisar

Fuentes (todas se descargan sin registro ni aceptar condiciones):

- Códigos y nombres: INE, «Relación de municipios y sus códigos por provincias» a 1 de enero de 2026
  (https://www.ine.es/daco/daco42/codmun/diccionario26.xlsx). Reutilización libre citando la fuente («Fuente: INE»).
- Población: INE, cifras oficiales del Padrón a 1 de enero de 2025 (Real Decreto 1117/2025), tabla 29005 del servicio
  JSON abierto https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/29005?nult=1&tip=AM. Misma licencia.
- Coordenadas de la capital del municipio, de dos fuentes abiertas:
  · GeoNames (https://download.geonames.org/export/dump/ES.zip), CC BY 4.0, atribución «GeoNames (geonames.org)». En
    GeoNames el código admin3 de España es el código INE del municipio: se elige el lugar poblado (clase P) con el nombre
    del municipio, prefiriendo las capitales (PPLC, PPLA, PPLA2, PPLA3, PPLA4) y, entre los PPL, el más poblado, siempre
    a menos de 25 km del punto de la unidad administrativa (ADM3); si no hay ninguno, ese punto ADM3.
  · Wikidata (https://query.wikidata.org, propiedades P772 «código INE de municipio» y P625), CC0.
  Si las dos coinciden a menos de 2 km se usa la de GeoNames. Si no, y se pasa ``--ign``, se elige la que mejor reproduce
  las horas de comienzo y fin que publica el IGN para los eclipses de 2026 y 2027 en ese municipio (con el ΔT que
  reproduce sus horas);
  las horas del IGN solo sirven para elegir entre las dos fuentes abiertas, no se copia ninguna coordenada suya. Las que
  siguen lejos de las horas del IGN (más de 4 s) se marcan con ``revisar = 1``.

El Nomenclátor Geográfico de Municipios y Entidades de Población del IGN (CC BY 4.0), que daría la coordenada oficial
de cada capital, solo se distribuye desde el Centro de Descargas del CNIG, con su formulario de descarga; no se usa.

Slug (el de las URL /espana/<municipio>/):
- Del nombre oficial en orden natural («Palmas de Gran Canaria, Las» → «Las Palmas de Gran Canaria»), en minúsculas,
  sin tildes ni diéresis (ñ → n, ç → c), sin el punto volado catalán (l·l → ll) y con guiones en lugar de espacios,
  apóstrofos y barras. Los nombres bilingües llevan las dos formas en el orden del INE: «ayala-aiara». Excepción de la
  sesión SEO (11-11-2026): los de la primera tanda del eclipse usan solo la forma castellana, que es la que se busca
  (alicante, elche, alcoy, castellon-de-la-plana, san-sebastian, pamplona, sagunto y san-vicente-del-raspeig). Se
  escribieron a mano en data/municipios-es.csv y la regla de estabilidad de abajo los conserva.
- Si el mismo slug sale en más de un municipio de España, todos ellos llevan detrás el slug de su provincia
  («villanueva-de-la-sierra-caceres», «villanueva-de-la-sierra-malaga»); las provincias bilingües van con la forma
  castellana («alava», «alicante», «castellon», «valencia»). Nunca «provincia» ni «astrologia».
- Estable: si ya existe el fichero de salida, cada código INE conserva el slug que tenía aunque cambie el nombre; un
  municipio nuevo recibe uno con la misma regla sin tocar los de los demás.

Uso:
    python3 -I calc/tools/municipios_es.py --diccionario diccionario26.xlsx --poblacion t29005.json \\
        --geonames ES.txt --wikidata wd.json [--ign ign-municipios.json] [--salida portal/data/municipios-es.csv]
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROVINCIAS = {
    "01": "Araba/Álava", "02": "Albacete", "03": "Alicante/Alacant", "04": "Almería", "05": "Ávila", "06": "Badajoz",
    "07": "Illes Balears", "08": "Barcelona", "09": "Burgos", "10": "Cáceres", "11": "Cádiz", "12": "Castellón/Castelló",
    "13": "Ciudad Real", "14": "Córdoba", "15": "A Coruña", "16": "Cuenca", "17": "Girona", "18": "Granada",
    "19": "Guadalajara", "20": "Gipuzkoa", "21": "Huelva", "22": "Huesca", "23": "Jaén", "24": "León", "25": "Lleida",
    "26": "La Rioja", "27": "Lugo", "28": "Madrid", "29": "Málaga", "30": "Murcia", "31": "Navarra", "32": "Ourense",
    "33": "Asturias", "34": "Palencia", "35": "Las Palmas", "36": "Pontevedra", "37": "Salamanca",
    "38": "Santa Cruz de Tenerife", "39": "Cantabria", "40": "Segovia", "41": "Sevilla", "42": "Soria", "43": "Tarragona",
    "44": "Teruel", "45": "Toledo", "46": "Valencia/València", "47": "Valladolid", "48": "Bizkaia", "49": "Zamora",
    "50": "Zaragoza", "51": "Ceuta", "52": "Melilla",
}
PROVINCIA_SLUG = {
    "01": "alava", "02": "albacete", "03": "alicante", "04": "almeria", "05": "avila", "06": "badajoz",
    "07": "illes-balears", "08": "barcelona", "09": "burgos", "10": "caceres", "11": "cadiz", "12": "castellon",
    "13": "ciudad-real", "14": "cordoba", "15": "a-coruna", "16": "cuenca", "17": "girona", "18": "granada",
    "19": "guadalajara", "20": "gipuzkoa", "21": "huelva", "22": "huesca", "23": "jaen", "24": "leon", "25": "lleida",
    "26": "la-rioja", "27": "lugo", "28": "madrid", "29": "malaga", "30": "murcia", "31": "navarra", "32": "ourense",
    "33": "asturias", "34": "palencia", "35": "las-palmas", "36": "pontevedra", "37": "salamanca",
    "38": "santa-cruz-de-tenerife", "39": "cantabria", "40": "segovia", "41": "sevilla", "42": "soria",
    "43": "tarragona", "44": "teruel", "45": "toledo", "46": "valencia", "47": "valladolid", "48": "bizkaia",
    "49": "zamora", "50": "zaragoza", "51": "ceuta", "52": "melilla",
}
PROHIBIDOS = {"provincia", "astrologia"}
PRIORIDAD = {"PPLC": 6, "PPLA": 5, "PPLA2": 4, "PPLA3": 3, "PPLA4": 2, "PPL": 1}
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
ARTICULOS = r"(El|La|Los|Las|L'|Els|Les|O|A|Os|As|Lo|Es|Sa|Ses|S')"
RADIO_ADM3_KM = 25.0
COINCIDEN_KM = 2.0
# ΔT con el que las horas publicadas por el IGN se reproducen mejor (ajuste en ~8.000 municipios, 11-11-2026).
DELTA_T_IGN = {"2026": 75.85, "2027": 77.35}
ECLIPSES_IGN = {"2026": "2026-08-12-eclipse-solar", "2027": "2027-08-02-eclipse-solar"}
CAMPOS = ["slug", "ine", "nombre", "nombre_ine", "provincia", "cpro", "latitud", "longitud", "poblacion", "fuente",
          "metodo", "revisar"]


def nombre_natural(n: str) -> str:
    """«Palmas de Gran Canaria, Las» → «Las Palmas de Gran Canaria»; también en cada lado de «Castelló/Castellón»."""
    def una(p: str) -> str:
        m = re.match(rf"^(.*), {ARTICULOS}$", p.strip())
        if not m:
            return p.strip()
        art = m[2]
        return f"{art}{m[1]}" if art.endswith("'") else f"{art} {m[1]}"
    return "/".join(una(p) for p in n.split("/"))


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.replace("·", ""))
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def normal(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def variantes(nombre_ine: str) -> set[str]:
    """Formas del nombre para comparar con GeoNames: cada lado de «/» y de «-», con y sin artículo."""
    v = set()
    for p in nombre_ine.split("/"):
        nat = nombre_natural(p)
        v.add(normal(nat))
        v.add(normal(re.sub(rf"^{ARTICULOS}\s*", "", nat)))
        for q in nat.split("-"):
            if len(q.strip()) > 3:
                v.add(normal(q))
    v.add(normal(nombre_natural(nombre_ine)))
    return {x for x in v if x}


def km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    p1, p2 = math.radians(a_lat), math.radians(b_lat)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b_lon - a_lon) / 2) ** 2
    return 2 * 6371.0 * math.asin(min(1.0, math.sqrt(h)))


# --------------------------------------------------------------------------------------------------------------------
# Lectura de fuentes


def leer_diccionario(ruta: Path) -> list[dict]:
    z = zipfile.ZipFile(ruta)
    ss = []
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
        ss.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    filas = []
    for r in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).findall(".//m:row", NS):
        celdas = {}
        for c in r.findall("m:c", NS):
            v = c.find("m:v", NS)
            val = v.text if v is not None else None
            if c.get("t") == "s" and val is not None:
                val = ss[int(val)]
            celdas[re.sub(r"\d", "", c.get("r"))] = val
        if (celdas.get("B") or "").isdigit() and (celdas.get("C") or "").isdigit():
            filas.append({"cpro": celdas["B"], "cmun": celdas["C"], "nombre_ine": (celdas.get("E") or "").strip()})
    return filas


def leer_poblacion(ruta: Path) -> tuple[dict[str, int], int]:
    pob, anio = {}, 0
    for serie in json.loads(ruta.read_text(encoding="utf-8")):
        meta = {m["T3_Variable"]: m for m in serie.get("MetaData", [])}
        mun = meta.get("Municipios")
        if not mun or meta.get("Sexo", {}).get("Nombre") != "Total" or not re.fullmatch(r"\d{5}", mun.get("Codigo", "")):
            continue
        if serie.get("Data"):
            pob[mun["Codigo"]] = int(serie["Data"][0]["Valor"])
            anio = max(anio, int(serie["Data"][0]["Anyo"]))
    return pob, anio


def leer_geonames(ruta: Path) -> tuple[dict[str, list[dict]], dict[str, dict], dict[str, list[dict]]]:
    """Lugares poblados por código INE, punto ADM3 por código y lugares poblados por provincia (admin2)."""
    lugares: dict[str, list[dict]] = {}
    adm3: dict[str, dict] = {}
    por_prov: dict[str, list[dict]] = {}
    with ruta.open(encoding="utf-8") as f:
        for linea in f:
            c = linea.rstrip("\n").split("\t")
            if len(c) < 15 or c[8] != "ES":
                continue
            g = {"id": int(c[0]), "nombre": c[1], "alternativos": c[3], "lat": float(c[4]), "lon": float(c[5]),
                 "clase": c[6], "codigo": c[7], "poblacion": int(c[14] or 0), "admin3": c[12]}
            if c[6] == "P":
                if re.fullmatch(r"\d{5}", c[12]):
                    lugares.setdefault(c[12], []).append(g)
                por_prov.setdefault(c[11], []).append(g)
            elif c[7] == "ADM3" and re.fullmatch(r"\d{5}", c[12]):
                adm3[c[12]] = g
    return lugares, adm3, por_prov


def leer_wikidata(ruta: Path) -> dict[str, list[tuple[str, float, float]]]:
    salida: dict[str, list[tuple[str, float, float]]] = {}
    for b in json.loads(ruta.read_text(encoding="utf-8"))["results"]["bindings"]:
        ine = b["ine"]["value"]
        m = re.match(r"Point\(([-\d.eE]+) ([-\d.eE]+)\)", b["coord"]["value"])
        if not re.fullmatch(r"\d{5}", ine) or not m:
            continue
        salida.setdefault(ine, []).append((b["item"]["value"].rsplit("/", 1)[-1], float(m[2]), float(m[1])))
    return salida


# --------------------------------------------------------------------------------------------------------------------
# Elección de coordenadas


def nombres_de(g: dict) -> set[str]:
    return {normal(g["nombre"])} | {normal(a) for a in g["alternativos"].split(",") if a}


def elegir_geonames(ine: str, nombre_ine: str, lugares: dict, adm3: dict, por_prov: dict, admin2: str | None) -> tuple[dict | None, str]:
    vs = variantes(nombre_ine)
    ref = adm3.get(ine)

    def cerca(g):
        return ref is None or km(g["lat"], g["lon"], ref["lat"], ref["lon"]) <= RADIO_ADM3_KM

    candidatos = [g for g in lugares.get(ine, []) if nombres_de(g) & vs and cerca(g)]
    if not candidatos and ref is not None and admin2:
        # GeoNames a veces pone el lugar con el código de otro municipio (El Ejido sale con el de Almería).
        candidatos = [g for g in por_prov.get(admin2, []) if nombres_de(g) & vs and cerca(g)]
    if candidatos:
        g = max(candidatos, key=lambda g: (PRIORIDAD.get(g["codigo"], 0), g["poblacion"],
                                           -km(g["lat"], g["lon"], ref["lat"], ref["lon"]) if ref else 0))
        return g, g["codigo"].lower()
    capitales = [g for g in lugares.get(ine, []) if g["codigo"] in ("PPLC", "PPLA", "PPLA2", "PPLA3") and cerca(g)]
    if capitales:
        return max(capitales, key=lambda g: (PRIORIDAD[g["codigo"]], g["poblacion"])), "capital-sin-nombre"
    if ref is not None:
        return ref, "adm3"
    return None, "sin-coordenadas"


class OraculoIGN:
    """Coste de unas coordenadas: diferencia cuadrática media con el comienzo y el fin del IGN en 2026 y 2027 (en s)."""

    def __init__(self, ign: Path, besselianos: Path):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import eclipses_bessel  # noqa: PLC0415

        self.eb = eclipses_bessel
        self.ign = json.loads(ign.read_text(encoding="utf-8"))
        sol = {e["identificador"]: e for e in json.loads(besselianos.read_text(encoding="utf-8"))["solares"]}
        self.el = {a: sol[i] for a, i in ECLIPSES_IGN.items()}

    def coste(self, ine: str, cpro: str, lat: float, lon: float) -> float | None:
        difs = []
        for anio, el in self.el.items():
            fila = self.ign.get(anio, {}).get(ine)
            if not fila:
                continue
            c = self.eb.circunstancias(el, lat, lon, 0.0, DELTA_T_IGN[anio])
            desfase = 3600 if cpro in ("35", "38") else 7200
            dia = datetime.fromisoformat(el["identificador"][:10]).replace(tzinfo=timezone.utc)
            base = dia + timedelta(hours=el["t0"])
            # Solo el primer y el último contacto: los de la totalidad dependen del borde de la franja, donde el IGN
            # da duraciones algo más cortas que la NASA y nosotros, y empujarían a elegir el punto más cercano al límite.
            for k in ("c1", "c4"):
                txt = fila.get(k) or ""
                if not re.fullmatch(r"\d\d:\d\d:\d\d", txt):
                    continue
                h, mi, s = (int(x) for x in txt.split(":"))
                ref = (dia + timedelta(seconds=h * 3600 + mi * 60 + s - desfase)).timestamp()
                t = c["contactos"].get(k) if c else None
                if t is None:
                    difs.append(60.0)  # el IGN da una fase que aquí no sale
                    continue
                difs.append((base + timedelta(seconds=t * 3600 - DELTA_T_IGN[anio])).timestamp() - ref)
        return math.sqrt(sum(d * d for d in difs) / len(difs)) if difs else None


# --------------------------------------------------------------------------------------------------------------------


def main(argv=None) -> int:
    raiz = Path(__file__).resolve().parents[2]
    p = argparse.ArgumentParser(description="Municipios de España (INE, GeoNames y Wikidata)")
    p.add_argument("--diccionario", type=Path, required=True)
    p.add_argument("--poblacion", type=Path, required=True)
    p.add_argument("--geonames", type=Path, required=True)
    p.add_argument("--wikidata", type=Path, required=True)
    p.add_argument("--ign", type=Path, help="tablas del IGN de calc/tools/ign_eclipses.py, para elegir entre fuentes")
    p.add_argument("--besselianos", type=Path, default=raiz / "calc" / "export" / "besselianos.json")
    p.add_argument("--salida", type=Path, default=raiz / "portal" / "data" / "municipios-es.csv")
    a = p.parse_args(argv)

    anteriores: dict[str, str] = {}
    if a.salida.exists():
        with a.salida.open(encoding="utf-8") as f:
            anteriores = {r["ine"]: r["slug"] for r in csv.DictReader(f) if r.get("slug")}

    dicc = leer_diccionario(a.diccionario)
    pob, anio = leer_poblacion(a.poblacion)
    lugares, adm3, por_prov = leer_geonames(a.geonames)
    wd = leer_wikidata(a.wikidata)
    oraculo = OraculoIGN(a.ign, a.besselianos) if a.ign else None
    # admin2 de GeoNames por provincia INE: el más frecuente entre los lugares de esa provincia.
    conteo: dict[str, dict[str, int]] = {}
    for prov, lista in por_prov.items():
        for g in lista:
            if re.fullmatch(r"\d{5}", g["admin3"]):
                conteo.setdefault(g["admin3"][:2], {}).setdefault(prov, 0)
                conteo[g["admin3"][:2]][prov] += 1
    admin2_de = {cpro: max(c, key=c.get) for cpro, c in conteo.items()}

    filas, metodos, revisar = [], {}, 0
    for m in dicc:
        ine = m["cpro"] + m["cmun"]
        g, metodo = elegir_geonames(ine, m["nombre_ine"], lugares, adm3, por_prov, admin2_de.get(m["cpro"]))
        w = None
        if wd.get(ine):
            w = min(wd[ine], key=lambda x: km(x[1], x[2], g["lat"], g["lon"]) if g else 0)
        lat = lon = None
        fuente, marca = "", ""
        if g and (not w or km(g["lat"], g["lon"], w[1], w[2]) <= COINCIDEN_KM):
            lat, lon, fuente = g["lat"], g["lon"], f"geonames:{g['id']}"
        elif g and w:
            if oraculo:
                cg = oraculo.coste(ine, m["cpro"], g["lat"], g["lon"])
                cw = oraculo.coste(ine, m["cpro"], w[1], w[2])
                usar_w = cg is not None and cw is not None and cw < cg
                metodo = f"{metodo}>wikidata" if usar_w else f"{metodo}>geonames"
                mejor = min(x for x in (cg, cw) if x is not None) if (cg is not None or cw is not None) else None
                if mejor is not None and mejor > 4:
                    marca = "1"
            else:
                usar_w = metodo in ("adm3", "capital-sin-nombre")
                marca = "1"
            if usar_w:
                lat, lon, fuente = w[1], w[2], f"wikidata:{w[0]}"
            else:
                lat, lon, fuente = g["lat"], g["lon"], f"geonames:{g['id']}"
        elif w:
            lat, lon, fuente, metodo = w[1], w[2], f"wikidata:{w[0]}", "wikidata"
        else:
            marca = "1"
        if oraculo and lat is not None and not marca:
            c = oraculo.coste(ine, m["cpro"], lat, lon)
            if c is not None and c > 4:
                marca = "1"
        revisar += 1 if marca else 0
        metodos[metodo] = metodos.get(metodo, 0) + 1
        filas.append({
            "ine": ine, "nombre": nombre_natural(m["nombre_ine"]), "nombre_ine": m["nombre_ine"],
            "provincia": PROVINCIAS[m["cpro"]], "cpro": m["cpro"],
            "latitud": f"{lat:.5f}" if lat is not None else "", "longitud": f"{lon:.5f}" if lon is not None else "",
            "poblacion": pob.get(ine, ""), "fuente": fuente, "metodo": metodo, "revisar": marca,
        })

    # Slugs: los de antes se conservan; los nuevos, con la regla (provincia detrás si el nombre se repite en España).
    base = {f["ine"]: slug(f["nombre"]) for f in filas}
    veces: dict[str, int] = {}
    for s in base.values():
        veces[s] = veces.get(s, 0) + 1
    usados = set(anteriores.get(f["ine"]) for f in filas if anteriores.get(f["ine"]))
    for f in filas:
        if anteriores.get(f["ine"]):
            f["slug"] = anteriores[f["ine"]]
            continue
        s = base[f["ine"]]
        if veces[s] > 1 or s in PROHIBIDOS or s in usados:
            s = f"{s}-{PROVINCIA_SLUG[f['cpro']]}"
        if s in usados or s in PROHIBIDOS:
            s = f"{s}-{f['ine']}"
        f["slug"] = s
        usados.add(s)
    assert len({f["slug"] for f in filas}) == len(filas), "slugs repetidos"

    filas.sort(key=lambda f: f["ine"])
    a.salida.parent.mkdir(parents=True, exist_ok=True)
    with a.salida.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)
    con_provincia = sum(1 for f in filas if f["slug"] != base[f["ine"]])
    print(f"escrito {a.salida}: {len(filas)} municipios, población a 1-1-{anio}, {con_provincia} slugs con provincia, "
          f"{revisar} por revisar")
    print("métodos:", dict(sorted(metodos.items(), key=lambda x: -x[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
