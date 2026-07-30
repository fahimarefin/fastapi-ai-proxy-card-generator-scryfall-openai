"""
Composites a full proxy card with an MTG-inspired layout:
  • Colored outer frame matching the card's color identity
  • Mana symbols rendered as colored circle pips
  • Parchment panels for title, type line, and rules text
  • Rarity-colored set-symbol diamond
  • Planeswalker loyalty-ability badges
  • P/T or loyalty badge styled to the frame color
  • Collector number / set code in a bottom strip

NOTE ON IP: This intentionally avoids copying Wizards of the Coast's exact
frame artwork / trade-dress.  A licensed or client-provided frame asset can be
swapped in later if desired.
"""
import io
import logging
import re
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.models.schemas import ScryfallCardData

logger = logging.getLogger(__name__)

# ── Card geometry ──────────────────────────────────────────────────────────────
CARD_W, CARD_H = 750, 1050
MARGIN_X = 22          # horizontal inset for all panels

TITLE_Y1, TITLE_Y2 = 16, 96       # name + mana cost bar
ART_Y1,   ART_Y2   = 98, 558      # artwork
TYPE_Y1,  TYPE_Y2  = 561, 616     # type line + set symbol
TEXT_Y1,  TEXT_Y2  = 619, 962     # rules text box
BOT_Y1,   BOT_Y2   = 965, 1036   # artist / collector strip

PARCHMENT      = (246, 238, 212)
PARCHMENT_DARK = (232, 220, 185)
DARK_INK       = (16, 10, 6)
PANEL_OUTLINE  = (110, 90, 50)    # dark gold line around panels

# Frame fill per MTG colour identity
_FRAME_FILL: dict = {
    "W": (210, 204, 178),
    "U": (28,  98, 172),
    "B": (42,  32,  52),
    "R": (182, 60,  28),
    "G": (32, 122,  52),
    "GOLD":      (182, 140, 35),
    "COLORLESS": (160, 155, 148),
}

# Mana pip: (fill, border, text_colour)
_MANA_PIP: dict = {
    "W": ((252, 248, 220), (175, 160, 118), DARK_INK),
    "U": ((35, 118, 218),  ( 10,  55, 138), (255, 255, 255)),
    "B": ((48,  36,  58),  ( 18,  12,  24), (255, 255, 255)),
    "R": ((218,  58,  26), (138,  26,   6), (255, 255, 255)),
    "G": ((36, 154,  62),  ( 16,  82,  30), (255, 255, 255)),
    "C": ((208, 208, 208), (128, 128, 128), DARK_INK),
    "#": ((140, 130, 118), ( 76,  70,  64), (255, 255, 255)),
}

# ── Font helpers ───────────────────────────────────────────────────────────────
_FONT_DIR = Path(__file__).resolve().parent.parent.parent / "assets" / "fonts"


def _ensure_fonts() -> None:
    missing = [n for n in ("regular.ttf", "bold.ttf") if not (_FONT_DIR / n).exists()]
    if missing:
        logger.warning(
            "Font file(s) %s not found in %s. Rebuild the Docker image.",
            missing, _FONT_DIR,
        )


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = ["bold.ttf", "regular.ttf"] if bold else ["regular.ttf", "bold.ttf"]
    for name in candidates:
        p = _FONT_DIR / name
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return ImageFont.load_default()


# ── Frame colour helpers ───────────────────────────────────────────────────────
def _frame_fill(colors: list) -> tuple:
    if not colors:
        return _FRAME_FILL["COLORLESS"]
    if len(colors) > 1:
        return _FRAME_FILL["GOLD"]
    return _FRAME_FILL.get(colors[0], _FRAME_FILL["COLORLESS"])


def _lighter(c: tuple, amt: int = 50) -> tuple:
    return tuple(min(255, v + amt) for v in c)


def _darker(c: tuple, amt: int = 55) -> tuple:
    return tuple(max(0, v - amt) for v in c)


def _text_on(bg: tuple) -> tuple:
    return (255, 255, 255) if sum(bg) < 400 else DARK_INK


# ── Mana symbol rendering ──────────────────────────────────────────────────────
def _parse_mana_cost(raw: str) -> list:
    return re.findall(r"\{([^}]+)\}", raw)


def _pip_config(sym: str) -> tuple:
    if sym in _MANA_PIP:
        return _MANA_PIP[sym]
    if re.fullmatch(r"[0-9XYZ]+", sym):
        return _MANA_PIP["#"]
    return _MANA_PIP["C"]


def _draw_pip(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, sym: str, font) -> None:
    fill, border, txt_col = _pip_config(sym)
    draw.ellipse([cx - r,     cy - r,     cx + r,     cy + r    ], fill=border)
    draw.ellipse([cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2], fill=fill)
    label = sym if len(sym) <= 2 else sym[0]
    try:
        bb = font.getbbox(label)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        tw = th = r
    draw.text((cx - tw // 2, cy - th // 2 - 1), label, font=font, fill=txt_col)


def _draw_mana_cost(
    draw: ImageDraw.ImageDraw,
    mana_str: str,
    x_right: int,
    y_center: int,
    pip_r: int = 16,
) -> int:
    """Draw mana pips right-aligned from x_right. Returns left edge used."""
    syms = _parse_mana_cost(mana_str)
    if not syms:
        return x_right
    pip_font = _load_font(pip_r - 2, bold=True)
    gap = 4
    total_w = len(syms) * (pip_r * 2 + gap) - gap
    x = x_right - total_w
    for sym in syms:
        _draw_pip(draw, x + pip_r, y_center, pip_r, sym, pip_font)
        x += pip_r * 2 + gap
    return x_right - total_w


# ── Set symbol ─────────────────────────────────────────────────────────────────
_RARITY_COLOUR: dict = {
    "common":   (185, 185, 185),
    "uncommon": (155, 178, 200),
    "rare":     (198, 168, 58),
    "mythic":   (208, 108, 28),
    "special":  (138, 78, 188),
    "bonus":    (138, 78, 188),
}


def _draw_set_symbol(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, rarity: str) -> None:
    fill   = _RARITY_COLOUR.get(rarity, (148, 143, 133))
    border = _darker(fill, 50)
    pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(pts, fill=fill, outline=border)


# ── Text utilities ─────────────────────────────────────────────────────────────
def _clean(text: str) -> str:
    return (
        text
        .replace("\u2212", "-")
        .replace("\u2014", " - ")
        .replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    box: tuple,
    text: str,
    font,
    fill: tuple = DARK_INK,
    spacing: int = 5,
) -> int:
    x0, y0, x1, y1 = box
    avg_cw = max(font.getbbox("A")[2], 6)
    cpl    = max(10, int((x1 - x0) / avg_cw))
    y      = y0
    for para in text.split("\n"):
        for line in textwrap.wrap(para, width=cpl) or [""]:
            if y + 22 > y1:
                return y
            draw.text((x0, y), line, font=font, fill=fill)
            bb = font.getbbox(line)
            y += (bb[3] - bb[1]) + spacing
    return y


# ── Panel helper ───────────────────────────────────────────────────────────────
def _panel(
    draw: ImageDraw.ImageDraw,
    x0: int, y0: int, x1: int, y1: int,
    radius: int = 8,
    fill: tuple = PARCHMENT,
    outline: tuple = PANEL_OUTLINE,
    width: int = 2,
) -> None:
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)


# ── Planeswalker ability helpers ───────────────────────────────────────────────
_COST_RE = re.compile(r"^([+\-\u22120][0-9X]+|0)\s*:\s*(.*)", re.MULTILINE)


def _parse_pw_text(oracle: str):
    lines   = oracle.split("\n")
    static  = []
    abilities = []
    in_ab   = False
    for line in lines:
        m = _COST_RE.match(line)
        if m:
            in_ab = True
            abilities.append((m.group(1).replace("\u2212", "-"), m.group(2)))
        elif not in_ab:
            static.append(line)
    return "\n".join(static).strip(), abilities


def _draw_ability_badge(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int,
    cost: str,
    font,
    frame_col: tuple,
) -> None:
    bw, bh = 68, 34
    x0, y0 = cx - bw // 2, cy - bh // 2
    x1, y1 = cx + bw // 2, cy + bh // 2
    dark    = _darker(frame_col, 55)
    light   = _lighter(frame_col, 35)
    draw.rounded_rectangle([x0, y0, x1, y1], radius=9, fill=frame_col, outline=dark, width=2)
    draw.rounded_rectangle([x0 + 3, y0 + 3, x1 - 3, y1 - 3], radius=6, outline=light, width=1)
    txt_col = _text_on(frame_col)
    try:
        bb = font.getbbox(cost)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    except Exception:
        tw = th = 12
    draw.text((cx - tw // 2, cy - th // 2), cost, font=font, fill=txt_col)


def _render_pw_abilities(
    draw: ImageDraw.ImageDraw,
    oracle: str,
    body_font,
    badge_font,
    frame_col: tuple,
) -> None:
    static, abilities = _parse_pw_text(oracle)
    x0 = MARGIN_X + 14
    x1 = CARD_W - MARGIN_X - 14
    y  = TEXT_Y1 + 14

    if static:
        y = _draw_wrapped(draw, (x0, y, x1, TEXT_Y2 - 14), static, body_font)
        y += 10

    for cost, ability_text in abilities:
        line_cy   = y + 17
        badge_cx  = x0 + 42
        _draw_ability_badge(draw, badge_cx, line_cy, cost, badge_font, frame_col)
        text_x0   = x0 + 92
        y = _draw_wrapped(draw, (text_x0, y, x1, TEXT_Y2 - 14), ability_text, body_font)
        y += 7


# ── Stat badge (P/T or loyalty) ───────────────────────────────────────────────
def _draw_stat_badge(
    draw: ImageDraw.ImageDraw,
    font,
    text: str,
    frame_col: tuple,
) -> None:
    try:
        bb = font.getbbox(text)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
    except Exception:
        tw = th = 30
    pad_x, pad_y = 16, 10
    bw   = max(tw + pad_x * 2, 72)
    bh   = th + pad_y * 2 + 4
    bx0  = CARD_W - MARGIN_X - bw
    by0  = TEXT_Y2 - bh + 6
    bx1  = CARD_W - MARGIN_X
    by1  = TEXT_Y2 + 14
    dark = _darker(frame_col, 55)
    lite = _lighter(frame_col, 40)
    draw.rounded_rectangle([bx0, by0, bx1, by1], radius=10, fill=frame_col, outline=dark, width=3)
    draw.rounded_rectangle([bx0 + 3, by0 + 3, bx1 - 3, by1 - 3], radius=7, outline=lite, width=1)
    cx  = (bx0 + bx1) // 2
    cy  = (by0 + by1) // 2
    txt_col = _text_on(frame_col)
    draw.text((cx - tw // 2, cy - th // 2), text, font=font, fill=txt_col)


# ── Main render ────────────────────────────────────────────────────────────────
def render_hybrid_card(card: ScryfallCardData, art_bytes: bytes) -> bytes:
    """Combine AI artwork with accurate card data into an MTG-inspired proxy."""
    _ensure_fonts()

    frame_col  = _frame_fill(card.colors)
    frame_dark = _darker(frame_col, 60)
    frame_lite = _lighter(frame_col, 45)

    # ── Canvas ──────────────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (CARD_W, CARD_H), color=frame_col)
    draw   = ImageDraw.Draw(canvas)

    # Outer dark border
    draw.rounded_rectangle(
        [3, 3, CARD_W - 3, CARD_H - 3],
        radius=32, outline=frame_dark, width=9,
    )
    # Inner light accent line
    draw.rounded_rectangle(
        [12, 12, CARD_W - 12, CARD_H - 12],
        radius=25, outline=frame_lite, width=2,
    )

    # ── Title bar ───────────────────────────────────────────────────────────────
    _panel(draw, MARGIN_X, TITLE_Y1, CARD_W - MARGIN_X, TITLE_Y2, radius=10)
    name_font = _load_font(30, bold=True)
    draw.text((MARGIN_X + 10, TITLE_Y1 + 11), card.name, font=name_font, fill=DARK_INK)
    if card.mana_cost:
        _draw_mana_cost(
            draw, card.mana_cost,
            x_right  = CARD_W - MARGIN_X - 8,
            y_center = (TITLE_Y1 + TITLE_Y2) // 2,
            pip_r    = 16,
        )

    # ── Art box ─────────────────────────────────────────────────────────────────
    ax0, ax1 = MARGIN_X, CARD_W - MARGIN_X
    draw.rectangle([ax0, ART_Y1, ax1, ART_Y2], outline=PANEL_OUTLINE, width=3)
    try:
        art   = Image.open(io.BytesIO(art_bytes)).convert("RGB")
        art_w = ax1 - ax0 - 6
        art_h = ART_Y2 - ART_Y1 - 6
        art   = _cover_resize(art, art_w, art_h)
        canvas.paste(art, (ax0 + 3, ART_Y1 + 3))
        draw.rectangle([ax0, ART_Y1, ax1, ART_Y2], outline=PANEL_OUTLINE, width=3)
    except Exception:
        logger.exception("Failed to place artwork.")
        draw.rectangle([ax0, ART_Y1, ax1, ART_Y2], fill=(155, 155, 155), outline=PANEL_OUTLINE, width=3)

    # ── Type line ───────────────────────────────────────────────────────────────
    _panel(draw, MARGIN_X, TYPE_Y1, CARD_W - MARGIN_X, TYPE_Y2, radius=6)
    type_font = _load_font(22, bold=True)
    draw.text((MARGIN_X + 10, TYPE_Y1 + 10), _clean(card.type_line), font=type_font, fill=DARK_INK)
    _draw_set_symbol(
        draw,
        cx     = CARD_W - MARGIN_X - 28,
        cy     = (TYPE_Y1 + TYPE_Y2) // 2,
        r      = 17,
        rarity = card.rarity,
    )

    # ── Rules text box ──────────────────────────────────────────────────────────
    _panel(draw, MARGIN_X, TEXT_Y1, CARD_W - MARGIN_X, TEXT_Y2, radius=8, fill=PARCHMENT_DARK)
    body_font  = _load_font(19)
    badge_font = _load_font(17, bold=True)
    oracle     = _clean(card.oracle_text or "")

    if "planeswalker" in card.type_line.lower():
        _render_pw_abilities(draw, oracle, body_font, badge_font, frame_col)
    else:
        full_text = oracle
        if card.flavor_text:
            full_text += f'\n\n\"{_clean(card.flavor_text)}\"'
        _draw_wrapped(
            draw,
            (MARGIN_X + 14, TEXT_Y1 + 14, CARD_W - MARGIN_X - 14, TEXT_Y2 - 14),
            full_text,
            body_font,
        )

    # ── P/T or Loyalty badge ────────────────────────────────────────────────────
    stat_font = _load_font(26, bold=True)
    if card.power and card.toughness:
        _draw_stat_badge(draw, stat_font, f"{card.power}/{card.toughness}", frame_col)
    elif card.loyalty:
        _draw_stat_badge(draw, stat_font, str(card.loyalty), frame_col)

    # ── Bottom info strip ───────────────────────────────────────────────────────
    bot_font = _load_font(13)
    info_parts = []
    if card.collector_number and card.set_code:
        info_parts.append(f"{card.collector_number}/{card.set_code.upper()}")
    if card.rarity:
        info_parts.append(card.rarity.title())
    if info_parts:
        draw.text(
            (MARGIN_X + 6, BOT_Y1 + 10),
            "  \u2022  ".join(info_parts),
            font=bot_font,
            fill=_lighter(frame_col, 80),
        )

    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    return buffer.getvalue()


# ── Utility ────────────────────────────────────────────────────────────────────
def _cover_resize(image: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize + center-crop to exactly fill target_w × target_h."""
    src_w, src_h = image.size
    scale  = max(target_w / src_w, target_h / src_h)
    new_w  = int(src_w * scale) + 1
    new_h  = int(src_h * scale) + 1
    image  = image.resize((new_w, new_h), Image.LANCZOS)
    left   = (new_w - target_w) // 2
    top    = (new_h - target_h) // 2
    return image.crop((left, top, left + target_w, top + target_h))





