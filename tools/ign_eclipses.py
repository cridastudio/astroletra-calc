#!/usr/bin/env python3
"""Tablas por municipio de los eclipses de Sol de eclipses.ign.es, a JSON, para validar el motor (11-11-2026).

El IGN publica en https://eclipses.ign.es/eclipse-total-sol-de-12-de-agosto-2026.html,
https://eclipses.ign.es/eclipse-total-sol-de-2-de-agosto-2027.html y
https://eclipses.ign.es/eclipse-anular-sol-de-26-de-enero-2028.html una tabla con cada municipio (inicio, fase central,
máximo, fin, magnitud y altura y acimut del Sol, en hora oficial). El código INE sale del enlace a la infografía.
Información astronómica del Observatorio Astronómico Nacional (IGN), CC BY 4.0. Solo se usa para comprobar; no se
publica.

Uso:
    python3 -I calc/tools/ign_eclipses.py e2026.html e2027.html e2028.html --salida ign-municipios.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

COLUMNAS = ["municipio", "provincia", "infografia", "c1", "c2", "maximo", "c3", "c4", "magnitud", "altura", "acimut"]


class Tablas(HTMLParser):
    def __init__(self):
        super().__init__()
        self.en_tabla = 0
        self.fila: list[str] | None = None
        self.celda: list[str] | None = None
        self.enlace: str | None = None
        self.filas: list[dict] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and "datos-municipio-eclipse" in (a.get("class") or ""):
            self.en_tabla += 1
        elif self.en_tabla and tag == "tr":
            self.fila = []
        elif self.en_tabla and self.fila is not None and tag == "td":
            self.celda, self.enlace = [], None
        elif self.celda is not None and tag == "a" and a.get("href"):
            self.enlace = a["href"]

    def handle_endtag(self, tag):
        if tag == "table" and self.en_tabla:
            self.en_tabla -= 1
        elif tag == "td" and self.celda is not None and self.fila is not None:
            self.fila.append(self.enlace or "".join(self.celda).strip())
            self.celda = None
        elif tag == "tr" and self.fila is not None:
            if len(self.fila) == len(COLUMNAS):
                f = list(self.fila)
                # La celda del enlace va en segunda o tercera posición según la fila.
                k = next((i for i in (1, 2) if f[i].startswith("http")), 2)
                cab = [f[i] for i in range(3) if i != k]
                self.filas.append(dict(zip(COLUMNAS, cab[:2] + [f[k]] + f[3:])))
            self.fila = None

    def handle_data(self, data):
        if self.celda is not None:
            self.celda.append(data)


def leer(ruta: Path) -> dict[str, dict]:
    p = Tablas()
    p.feed(ruta.read_text(encoding="utf-8", errors="replace"))
    salida = {}
    for f in p.filas:
        m = re.search(r"/(\d{5})_", f["infografia"] or "")
        if m:
            f = dict(f, ine=m[1])
            del f["infografia"]
            salida.setdefault(m[1], f)
    return salida


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("paginas", nargs="+", type=Path, help="páginas guardadas, en el orden 2026, 2027, 2028")
    a.add_argument("--salida", type=Path, required=True)
    args = a.parse_args(argv)
    datos = {}
    for ruta in args.paginas:
        anio = re.search(r"20\d\d", ruta.name)
        filas = leer(ruta)
        datos[anio[0] if anio else ruta.stem] = filas
        print(f"{ruta.name}: {len(filas)} municipios")
    args.salida.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
