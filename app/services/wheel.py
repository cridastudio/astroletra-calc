"""Clean SVG chart wheels (single and double) generated from serialized chart data.

Glyph outlines are reused from the Kerykeion package templates (public-domain
Symbola outlines, see Kerykeion's NOTICE); if they cannot be loaded, Unicode
glyphs are used instead. The output is self-contained and renders identically in
browsers and in WeasyPrint.
"""

from __future__ import annotations

import math
import re
from functools import lru_cache
from importlib import resources
from typing import Any

SIZE = 600
CX = CY = SIZE / 2

# Radii (px) for the single wheel.
R_OUTER = 292.0
R_ZODIAC_IN = 258.0
R_TICKS_IN = 246.0
R_PLANET = 218.0
R_PLANET_DEG = 191.0
R_HOUSE_NUM = 118.0
R_INNER = 104.0

# Radii for the double wheel (synastry): B outside, A inside.
D_R_PLANET_B = 222.0
D_R_PLANET_B_DEG = 197.0
D_R_RING = 184.0
D_R_PLANET_A = 160.0
D_R_PLANET_A_DEG = 135.0
D_R_HOUSE_NUM = 110.0
D_R_INNER = 96.0

SIGN_CODES = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
SIGN_UNICODE = "♈♉♊♋♌♍♎♏♐♑♒♓"
ELEMENT_CLASS = ["fire", "earth", "air", "water"] * 3

# Public point name -> Kerykeion symbol id, Unicode fallback.
POINT_GLYPH: dict[str, tuple[str, str]] = {
    "Sun": ("Sun", "☉"),
    "Moon": ("Moon", "☽"),
    "Mercury": ("Mercury", "☿"),
    "Venus": ("Venus", "♀"),
    "Mars": ("Mars", "♂"),
    "Jupiter": ("Jupiter", "♃"),
    "Saturn": ("Saturn", "♄"),
    "Uranus": ("Uranus", "♅"),
    "Neptune": ("Neptune", "♆"),
    "Pluto": ("Pluto", "♇"),
    "North Node": ("True_North_Lunar_Node", "☊"),
    "Chiron": ("Chiron", "⚷"),
}
ASPECT_CLASS = {
    "conjunction": "asp-conj",
    "opposition": "asp-hard",
    "square": "asp-hard",
    "trine": "asp-soft",
    "sextile": "asp-soft",
}

_STYLE = """
.wheel{font-family:'DejaVu Sans','Noto Sans',Helvetica,Arial,sans-serif;color:#2a2838}
.ink{stroke:#2a2838;fill:none}
.thin{stroke:#8d8a9c;fill:none;stroke-width:.6}
.band{stroke:#2a2838;stroke-width:.8}
.fire{fill:#f6e3d6}.earth{fill:#e6ead9}.air{fill:#e2e8f3}.water{fill:#dde9ee}
.sign{fill:#2a2838;color:#2a2838}
.pt{fill:#2a2838;color:#2a2838}
.pt-b{fill:#8a5a1d;color:#8a5a1d}
.deg{font-size:8px;fill:#5c5a6b}
.deg-b{font-size:8px;fill:#8a5a1d}
.hn{font-size:9px;fill:#8d8a9c;text-anchor:middle;dominant-baseline:middle}
.axis{stroke:#2a2838;stroke-width:1.6;fill:none}
.axis-lbl{font-size:10px;font-weight:bold;fill:#2a2838;text-anchor:middle;dominant-baseline:middle}
.asp-conj{stroke:#b8963e;stroke-width:1.2;fill:none}
.asp-hard{stroke:#b3414a;stroke-width:.9;fill:none}
.asp-soft{stroke:#3f6aa6;stroke-width:.9;fill:none}
.asp-x{stroke:#8d8a9c;stroke-width:.7;fill:none;stroke-dasharray:3 2}
.rx{font-size:6px;fill:#b3414a}
.gl{font-size:15px;text-anchor:middle;dominant-baseline:middle}
"""


@lru_cache(maxsize=1)
def _glyph_defs() -> dict[str, str]:
    """Extract the needed <symbol> definitions from Kerykeion's wheel template."""
    wanted = set(SIGN_CODES) | {k[0] for k in POINT_GLYPH.values()} | {"retrograde"}
    try:
        src = resources.files("kerykeion").joinpath("charts/templates/wheel_only.xml").read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, ModuleNotFoundError):
        return {}
    out: dict[str, str] = {}
    for sym_id in wanted:
        m = re.search(r'<symbol id="%s"[^>]*>.*?</symbol>' % re.escape(sym_id), src, re.S)
        if not m:
            continue
        body = re.sub(r"var\(--kerykeion-chart-color-[a-z0-9-]+\)", "currentColor", m.group(0))
        body = re.sub(r"\s+", " ", body).replace("> <", "><")
        body = body.replace('id="%s"' % sym_id, 'id="g-%s"' % sym_id, 1)
        out[sym_id] = body
    return out


def _polar(radius: float, abs_deg: float, asc_deg: float, cx: float = CX, cy: float = CY) -> tuple[float, float]:
    """Chart coordinates: Ascendant on the left, zodiac running counter-clockwise."""
    a = math.radians(abs_deg - asc_deg)
    return (cx - radius * math.cos(a), cy + radius * math.sin(a))


def _f(x: float) -> str:
    return f"{x:.1f}"


def _spread(positions: list[float], min_gap: float = 7.5) -> list[float]:
    """Push angular positions apart so glyphs never overlap (circular relaxation)."""
    n = len(positions)
    if n < 2:
        return positions[:]
    min_gap = min(min_gap, 360.0 / n)
    order = sorted(range(n), key=lambda i: positions[i])
    pos = [positions[i] % 360 for i in order]
    for _ in range(200):
        moved = False
        for k in range(n):
            j = (k + 1) % n
            # Unwrapped gap: the last pair wraps around the circle.
            gap = (pos[j] + (360.0 if j == 0 else 0.0)) - pos[k]
            if gap < min_gap - 1e-6:
                push = (min_gap - gap) / 2
                pos[k] -= push
                pos[j] += push
                moved = True
        if not moved:
            break
    out = [0.0] * n
    for k, i in enumerate(order):
        out[i] = pos[k] % 360
    return out


def _glyph(sym_id: str, fallback: str, x: float, y: float, size: float, cls: str, defs: dict[str, str]) -> str:
    if sym_id in defs:
        scale = size / 24
        return (
            f'<g class="{cls}" transform="translate({_f(x - size / 2)},{_f(y - size / 2)}) scale({scale:.3f})">'
            f'<use xlink:href="#g-{sym_id}"/></g>'
        )
    return f'<text class="gl {cls}" x="{_f(x)}" y="{_f(y)}" style="font-size:{size:.0f}px">{fallback}</text>'


def _zodiac_ring(asc_deg: float, defs: dict[str, str], r_out: float, r_in: float, r_glyph: float) -> list[str]:
    parts = []
    for i in range(12):
        start, end = i * 30.0, (i + 1) * 30.0
        x1, y1 = _polar(r_out, start, asc_deg)
        x2, y2 = _polar(r_out, end, asc_deg)
        x3, y3 = _polar(r_in, end, asc_deg)
        x4, y4 = _polar(r_in, start, asc_deg)
        # Counter-clockwise on screen means sweep-flag 0 for the outer arc.
        path = (
            f"M{_f(x1)},{_f(y1)} A{_f(r_out)},{_f(r_out)} 0 0 0 {_f(x2)},{_f(y2)} "
            f"L{_f(x3)},{_f(y3)} A{_f(r_in)},{_f(r_in)} 0 0 1 {_f(x4)},{_f(y4)} Z"
        )
        parts.append(f'<path class="band {ELEMENT_CLASS[i]}" d="{path}"/>')
        gx, gy = _polar(r_glyph, start + 15, asc_deg)
        parts.append(_glyph(SIGN_CODES[i], SIGN_UNICODE[i], gx, gy, 16, "sign", defs))
    return parts


def _ticks(asc_deg: float, r_out: float, r_in: float) -> list[str]:
    parts = [f'<circle class="thin" cx="{CX}" cy="{CY}" r="{_f(r_in)}"/>']
    for d in range(0, 360, 5):
        length = (r_out - r_in) if d % 10 == 0 else (r_out - r_in) * 0.5
        x1, y1 = _polar(r_in, d, asc_deg)
        x2, y2 = _polar(r_in + length, d, asc_deg)
        parts.append(f'<line class="thin" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>')
    return parts


def _houses(chart: dict[str, Any], asc_deg: float, r_out: float, r_in: float, r_num: float, labels: bool = True) -> list[str]:
    parts = []
    houses = chart.get("houses") or []
    for cusp in houses:
        deg = cusp["abs_degree"]
        x1, y1 = _polar(r_in, deg, asc_deg)
        x2, y2 = _polar(r_out, deg, asc_deg)
        is_axis = cusp["house"] in (1, 4, 7, 10)
        parts.append(
            f'<line class="{"axis" if is_axis else "thin"}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>'
        )
    if labels:
        for idx, cusp in enumerate(houses):
            nxt = houses[(idx + 1) % 12]["abs_degree"]
            span = (nxt - cusp["abs_degree"]) % 360
            mid = (cusp["abs_degree"] + span / 2) % 360
            x, y = _polar(r_num, mid, asc_deg)
            parts.append(f'<text class="hn" x="{_f(x)}" y="{_f(y)}">{cusp["house"]}</text>')
    angles = chart.get("angles")
    if angles:
        for key, label in (("asc", "AC"), ("mc", "MC"), ("dsc", "DC"), ("ic", "IC")):
            deg = angles[key]["abs_degree"]
            x, y = _polar(r_out + 7, deg, asc_deg)
            parts.append(f'<text class="axis-lbl" x="{_f(x)}" y="{_f(y)}">{label}</text>')
    return parts


def _planet_layer(
    planets: list[dict[str, Any]],
    asc_deg: float,
    defs: dict[str, str],
    *,
    r_glyph: float,
    r_deg: float,
    r_tick: float,
    cls: str,
    deg_cls: str,
    size: float = 17,
) -> list[str]:
    parts = []
    true_pos = [p["abs_degree"] for p in planets]
    shown = _spread(true_pos, min_gap=9.5 if size >= 16 else 8.5)
    for p, tdeg, sdeg in zip(planets, true_pos, shown):
        sym, fallback = POINT_GLYPH.get(p["name"], ("", p["name"][:2]))
        # Marker at the true position, short connector to the (possibly shifted) glyph.
        tx1, ty1 = _polar(r_tick, tdeg, asc_deg)
        tx2, ty2 = _polar(r_tick - 6, tdeg, asc_deg)
        parts.append(f'<line class="ink" style="stroke-width:1.1" x1="{_f(tx1)}" y1="{_f(ty1)}" x2="{_f(tx2)}" y2="{_f(ty2)}"/>')
        gx, gy = _polar(r_glyph, sdeg, asc_deg)
        if abs(((sdeg - tdeg) + 180) % 360 - 180) > 0.4:
            cx2, cy2 = _polar(r_glyph + size * 0.7, sdeg, asc_deg)
            parts.append(f'<line class="thin" x1="{_f(tx2)}" y1="{_f(ty2)}" x2="{_f(cx2)}" y2="{_f(cy2)}"/>')
        parts.append(_glyph(sym, fallback, gx, gy, size, cls, defs))
        dx, dy = _polar(r_deg, sdeg, asc_deg)
        parts.append(
            f'<text class="{deg_cls}" x="{_f(dx)}" y="{_f(dy)}" text-anchor="middle" dominant-baseline="middle">{int(p["degree"])}°</text>'
        )
        if p.get("retrograde"):
            rx, ry = _polar(r_deg - 10, sdeg, asc_deg)
            parts.append(_glyph("retrograde", "r", rx, ry, 7, deg_cls, defs))
    return parts


def _aspect_lines(
    aspects: list[dict[str, Any]],
    pos_p1: dict[str, float],
    pos_p2: dict[str, float],
    asc_deg: float,
    r: float,
    max_orb: float | None = None,
) -> list[str]:
    parts = []
    for a in aspects:
        if a["type"] not in ASPECT_CLASS or a["type"] == "conjunction":
            continue
        if max_orb is not None and a["orb"] > max_orb:
            continue
        d1 = pos_p1.get(a.get("p1", a.get("a")))
        d2 = pos_p2.get(a.get("p2", a.get("b")))
        if d1 is None or d2 is None:
            continue
        x1, y1 = _polar(r, d1, asc_deg)
        x2, y2 = _polar(r, d2, asc_deg)
        parts.append(f'<line class="{ASPECT_CLASS[a["type"]]}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>')
    return parts


def _open(title: str, defs: dict[str, str]) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {SIZE} {SIZE}" width="{SIZE}" height="{SIZE}" class="wheel" role="img" aria-label="{title}">',
        f"<title>{title}</title>",
        f"<style>{_STYLE}</style>",
        "<defs>" + "".join(defs.values()) + "</defs>",
    ]


def _planet_positions(planets: list[dict[str, Any]], angles: dict[str, Any] | None) -> dict[str, float]:
    pos = {p["name"]: p["abs_degree"] for p in planets}
    if angles:
        pos["Ascendant"] = angles["asc"]["abs_degree"]
        pos["MC"] = angles["mc"]["abs_degree"]
    return pos


def natal_wheel_svg(chart: dict[str, Any], title: str = "Chart wheel") -> str:
    """Single wheel. ``chart`` is the dict produced by ``serialize_chart``."""
    defs = _glyph_defs()
    angles = chart.get("angles")
    asc_deg = angles["asc"]["abs_degree"] if angles else 0.0
    parts = _open(title, defs)
    parts.append(f'<circle class="ink" cx="{CX}" cy="{CY}" r="{_f(R_OUTER)}"/>')
    parts += _zodiac_ring(asc_deg, defs, R_OUTER, R_ZODIAC_IN, (R_OUTER + R_ZODIAC_IN) / 2)
    parts += _ticks(asc_deg, R_ZODIAC_IN, R_TICKS_IN)
    parts.append(f'<circle class="ink" cx="{CX}" cy="{CY}" r="{_f(R_INNER)}"/>')
    if chart.get("has_time"):
        parts += _houses(chart, asc_deg, R_TICKS_IN, R_INNER, R_HOUSE_NUM)
    planets = chart.get("planets", [])
    pos = _planet_positions(planets, angles)
    parts += _aspect_lines(chart.get("aspects", []), pos, pos, asc_deg, R_INNER)
    parts += _planet_layer(planets, asc_deg, defs, r_glyph=R_PLANET, r_deg=R_PLANET_DEG, r_tick=R_TICKS_IN, cls="pt", deg_cls="deg")
    parts.append("</svg>")
    return "".join(parts)


def double_wheel_svg(chart_a: dict[str, Any], chart_b: dict[str, Any], inter_aspects: list[dict[str, Any]], title: str = "Synastry wheel") -> str:
    """Double wheel: chart A (houses and planets) inside, chart B planets on the outer band."""
    defs = _glyph_defs()
    angles_a = chart_a.get("angles")
    asc_deg = angles_a["asc"]["abs_degree"] if angles_a else 0.0
    parts = _open(title, defs)
    parts.append(f'<circle class="ink" cx="{CX}" cy="{CY}" r="{_f(R_OUTER)}"/>')
    parts += _zodiac_ring(asc_deg, defs, R_OUTER, R_ZODIAC_IN, (R_OUTER + R_ZODIAC_IN) / 2)
    parts += _ticks(asc_deg, R_ZODIAC_IN, R_TICKS_IN)
    parts.append(f'<circle class="thin" cx="{CX}" cy="{CY}" r="{_f(D_R_RING)}"/>')
    parts.append(f'<circle class="ink" cx="{CX}" cy="{CY}" r="{_f(D_R_INNER)}"/>')
    if chart_a.get("has_time"):
        parts += _houses(chart_a, asc_deg, R_TICKS_IN, D_R_INNER, D_R_HOUSE_NUM)
    planets_a = chart_a.get("planets", [])
    planets_b = chart_b.get("planets", [])
    pos_a = _planet_positions(planets_a, angles_a)
    pos_b = _planet_positions(planets_b, chart_b.get("angles"))
    parts += _aspect_lines(inter_aspects, pos_a, pos_b, asc_deg, D_R_INNER, max_orb=3.0)
    parts += _planet_layer(planets_b, asc_deg, defs, r_glyph=D_R_PLANET_B, r_deg=D_R_PLANET_B_DEG, r_tick=R_TICKS_IN, cls="pt-b", deg_cls="deg-b", size=15)
    parts += _planet_layer(planets_a, asc_deg, defs, r_glyph=D_R_PLANET_A, r_deg=D_R_PLANET_A_DEG, r_tick=D_R_RING, cls="pt", deg_cls="deg", size=15)
    parts.append("</svg>")
    return "".join(parts)
