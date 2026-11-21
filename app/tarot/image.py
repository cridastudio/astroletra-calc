"""Compose the spread image with Pillow.

Cards are read from ``<assets_dir>/<card_id>.png``. When a scan is missing a
placeholder card with the card title is drawn instead, so the service keeps
working while the asset folder is being filled.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.tarot.draw import Draw, DrawnCard

BG = (243, 239, 230)
INK = (42, 40, 56)
MUTED = (110, 108, 125)
CARD_BG = (250, 247, 240)
CARD_BORDER = (120, 95, 60)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSerif.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        candidate = f"{current} {w}".strip()
        if draw.textlength(candidate, font=font) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def _placeholder(dc: DrawnCard, size: tuple[int, int], lang: str) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, CARD_BG)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4, 4, w - 5, h - 5), radius=int(w * 0.06), outline=CARD_BORDER, width=max(3, w // 60))
    d.rounded_rectangle((int(w * 0.08), int(w * 0.08), w - int(w * 0.08), h - int(w * 0.08)), radius=int(w * 0.04), outline=CARD_BORDER, width=1)
    card = dc.card
    title_font = _font(max(14, w // 11))
    small_font = _font(max(11, w // 15))
    if card.arcana == "major":
        from app.tarot.cards import ROMAN

        header = ROMAN[card.number]
    else:
        header = card.suit.upper() if card.suit else ""
    d.text((w / 2, h * 0.16), header, font=title_font, fill=INK, anchor="mm")
    y = h * 0.42
    for line in _wrap(d, card.name_fr.upper(), title_font, int(w * 0.8)):
        d.text((w / 2, y), line, font=title_font, fill=INK, anchor="mm")
        y += title_font.size * 1.3
    y += title_font.size * 0.6
    for line in _wrap(d, card.names.get(lang, card.names["es"]), small_font, int(w * 0.8)):
        d.text((w / 2, y), line, font=small_font, fill=MUTED, anchor="mm")
        y += small_font.size * 1.3
    return img


def load_card(assets_dir: Path, dc: DrawnCard, size: tuple[int, int], lang: str) -> tuple[Image.Image, bool]:
    """Return ``(image, is_placeholder)`` scaled to ``size`` (cover + center crop)."""
    path = assets_dir / f"{dc.card.card_id}.png"
    if path.exists():
        try:
            with Image.open(path) as src:
                img = src.convert("RGB")
            w, h = size
            scale = max(w / img.width, h / img.height)
            img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
            left = (img.width - w) // 2
            top = (img.height - h) // 2
            img = img.crop((left, top, left + w, top + h))
            return img, False
        except OSError:
            pass
    return _placeholder(dc, size, lang), True


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _paste_card(canvas: Image.Image, img: Image.Image, xy: tuple[int, int]) -> None:
    mask = _rounded_mask(img.size, max(6, img.width // 25))
    shadow = Image.new("RGB", img.size, (205, 200, 190))
    canvas.paste(shadow, (xy[0] + 4, xy[1] + 5), mask)
    canvas.paste(img, xy, mask)


def _label(draw: ImageDraw.ImageDraw, text: str, center_x: float, top: float, font: ImageFont.FreeTypeFont, width: int) -> None:
    y = top
    for line in _wrap(draw, text, font, width):
        draw.text((center_x, y), line, font=font, fill=INK, anchor="ma")
        y += font.size * 1.25


def compose_three(d: Draw, assets_dir: Path, lang: str) -> tuple[Image.Image, list[str]]:
    cw, ch, gap, margin, label_h = 300, 540, 48, 48, 84
    width = margin * 2 + cw * 3 + gap * 2
    height = margin * 2 + ch + label_h
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    font = _font(22)
    missing: list[str] = []
    for i, dc in enumerate(d.cards):
        img, placeholder = load_card(assets_dir, dc, (cw, ch), lang)
        if placeholder:
            missing.append(dc.card.card_id)
        if dc.reversed:
            img = img.rotate(180)
        x = margin + i * (cw + gap)
        _paste_card(canvas, img, (x, margin))
        _label(draw, f"{dc.position.position} · {dc.position.labels[lang]}", x + cw / 2, margin + ch + 16, font, cw)
    return canvas, missing


def compose_celtic(d: Draw, assets_dir: Path, lang: str) -> tuple[Image.Image, list[str]]:
    cw, ch, gap, margin, label_h = 220, 396, 40, 40, 60
    cell_h = ch + label_h
    staff_gap = 70
    width = margin * 2 + cw * 4 + gap * 2 + staff_gap
    height = margin * 2 + cell_h * 4 + gap * 3
    canvas = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(canvas)
    font = _font(17)
    missing: list[str] = []

    col = [margin + i * (cw + gap) for i in range(3)]
    col.append(margin + 3 * (cw + gap) + staff_gap)
    staff_rows = [margin + i * (cell_h + gap) for i in range(4)]
    cross_rows = [staff_rows[0] + (cell_h + gap) * 0.5 + i * (cell_h + gap) for i in range(3)]
    cross_rows = [int(r) for r in cross_rows]

    # position -> (x, y) of the top-left corner of the card
    place = {
        1: (col[1], cross_rows[1]),
        3: (col[1], cross_rows[2]),
        4: (col[0], cross_rows[1]),
        5: (col[1], cross_rows[0]),
        6: (col[2], cross_rows[1]),
        7: (col[3], staff_rows[3]),
        8: (col[3], staff_rows[2]),
        9: (col[3], staff_rows[1]),
        10: (col[3], staff_rows[0]),
    }
    images: dict[int, Image.Image] = {}
    for dc in d.cards:
        img, placeholder = load_card(assets_dir, dc, (cw, ch), lang)
        if placeholder:
            missing.append(dc.card.card_id)
        if dc.reversed:
            img = img.rotate(180)
        images[dc.position.position] = img

    by_pos = {dc.position.position: dc for dc in d.cards}
    for pos, xy in place.items():
        _paste_card(canvas, images[pos], xy)
        dc = by_pos[pos]
        text = f"{pos} · {dc.position.labels[lang]}"
        if pos == 1:
            dc2 = by_pos[2]
            text += f"\n2 · {dc2.position.labels[lang]}"
        for k, line in enumerate(text.split("\n")):
            _label(draw, line, xy[0] + cw / 2, xy[1] + ch + 10 + k * (font.size * 1.3), font, cw + gap)
    # Card 2 crosses card 1: rotated a quarter turn and centred on it.
    crossing = images[2].rotate(90, expand=True)
    x1, y1 = place[1]
    cx, cy = x1 + cw // 2, y1 + ch // 2
    _paste_card(canvas, crossing, (cx - crossing.width // 2, cy - crossing.height // 2))
    return canvas, missing


def compose(d: Draw, assets_dir: Path, lang: str = "es") -> tuple[Image.Image, list[str]]:
    if d.spread == "three":
        return compose_three(d, assets_dir, lang)
    if d.spread == "celtic":
        return compose_celtic(d, assets_dir, lang)
    raise ValueError(f"unknown spread: {d.spread}")


def to_png_bytes(img: Image.Image, colors: int = 256) -> bytes:
    """Palette PNG (no dithering): the scans are already 256-colour images, so this keeps the
    spread well under 1 MB (Workflow step outputs and D1 values are capped) with no visible loss."""
    buf = io.BytesIO()
    quantized = img.convert("RGB").quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    quantized.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def to_png_base64(img: Image.Image) -> str:
    return base64.b64encode(to_png_bytes(img)).decode("ascii")
