"""Single-composite image generator for SAFE-T claim attachment.

Implements `mahika_capture_specs.md §7.1`:

    ┌──────────────────────────────────────────────┐
    │  Order ID + dispatch date          (header)  │
    ├────────────────────┬─────────────────────────┤
    │  PK_FRONT          │  PK_BACK    (SENT)      │
    ├────────────────────┼─────────────────────────┤
    │  RT_FRONT          │  RT_BACK    (RECEIVED)  │
    ├────────────────────┴─────────────────────────┤
    │  Order details + FPC compare + verdict       │
    │  Mahika ❄️ watermark                          │
    └──────────────────────────────────────────────┘

Canvas: 2400 × 3000 px, JPEG @ 85% (≈4–6 MB output). Source 2K images are
fit-scaled into 1200×1200 cells preserving aspect via letterbox.

The output is a single court-grade evidence file. Amazon SAFE-T form expects
one image, reviewer attention isn't split, audit trail stays clean.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mahika.services.verdict import VerdictSuggestion

# ─── Canvas geometry (px) ────────────────────────────────────────────────
CANVAS_W = 2400
CANVAS_H = 3000
HEADER_H = 120
ROW_LABEL_W = 60       # left-edge strip with "SENT" / "RECEIVED" labels
CELL_GAP = 16          # gap between cells + rows
FOOTER_H = 540
CELL_W = (CANVAS_W - ROW_LABEL_W - CELL_GAP) // 2  # ≈ 1162
CELL_H = (CANVAS_H - HEADER_H - FOOTER_H - 3 * CELL_GAP) // 2  # ≈ 1099

BG = (245, 245, 245)
HEADER_BG = (15, 60, 90)
HEADER_FG = (255, 255, 255)
LABEL_BG = (200, 220, 235)
CELL_BG = (255, 255, 255)
FOOTER_BG = (250, 250, 250)
INK = (20, 20, 20)
ACCENT = (15, 60, 90)
WARN = (200, 40, 40)

# Mahika brand mark — snowflake glyph
WATERMARK = "Mahika ❄️"

# JPEG quality per spec §2.3 — 85%
JPEG_QUALITY = 85


# ─── Font discovery ──────────────────────────────────────────────────────
# Windows ships Arial; Linux usually has DejaVu Sans. Fall back to Pillow's
# bitmap default if neither is found.
_FONT_CANDIDATES_REGULAR = [
    "arial.ttf",
    "Arial.ttf",
    "DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
]
_FONT_CANDIDATES_BOLD = [
    "arialbd.ttf",
    "Arial-Bold.ttf",
    "DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    # Last-ditch fallback — Pillow's built-in bitmap font (unscalable, ugly,
    # but the pipeline still produces output).
    return ImageFont.load_default()


# ─── Helpers ─────────────────────────────────────────────────────────────


def _fit_into_cell(src_path: Path, target_w: int, target_h: int) -> Image.Image:
    """Open `src_path`, resize preserving aspect, letterbox to cell size.

    Returns an RGB image exactly target_w × target_h. Missing or unreadable
    source images yield a placeholder rectangle with "image missing" text so
    the composite still renders for partial bundles.
    """
    placeholder_label: str | None = None
    try:
        src = Image.open(src_path).convert("RGB")
    except Exception:
        placeholder_label = f"{src_path.name} missing"
        src = Image.new("RGB", (target_w, target_h), (220, 220, 220))

    src_w, src_h = src.size
    if src_w == 0 or src_h == 0:
        placeholder_label = f"{src_path.name} empty"
        src = Image.new("RGB", (target_w, target_h), (220, 220, 220))
        src_w, src_h = target_w, target_h

    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(src_w * scale))
    new_h = max(1, int(src_h * scale))
    resized = src.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (target_w, target_h), CELL_BG)
    off_x = (target_w - new_w) // 2
    off_y = (target_h - new_h) // 2
    canvas.paste(resized, (off_x, off_y))

    if placeholder_label:
        draw = ImageDraw.Draw(canvas)
        font = _load_font(40, bold=True)
        draw.text(
            (target_w // 2 - 200, target_h // 2 - 20),
            placeholder_label,
            fill=WARN,
            font=font,
        )

    return canvas


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    box: tuple[int, int, int, int],
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    """Draw `text` centred inside the (left, top, right, bottom) box."""
    left, top, right, bottom = box
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = left + ((right - left) - tw) // 2 - bbox[0]
    y = top + ((bottom - top) - th) // 2 - bbox[1]
    draw.text((x, y), text, font=font, fill=fill)


def _format_date(value: str | None) -> str:
    """Pretty-print a date string. Falls through to raw input if unparseable."""
    if not value:
        return "—"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d %b %Y"):
        try:
            return datetime.strptime(value[: len(fmt)], fmt).strftime("%d %b %Y")
        except ValueError:
            continue
    return value


# ─── Public API ──────────────────────────────────────────────────────────


def build_composite(
    *,
    order_id: str,
    pk_front: Path,
    pk_back: Path,
    rt_front: Path,
    rt_back: Path,
    dispatched_at: str | None,
    returned_at: str | None,
    fpc_sent: str | None,
    fpc_received: str | None,
    suggested: VerdictSuggestion | None,
    output_path: Path,
) -> Path:
    """Render the 2x2 composite + header + footer. Save to `output_path`.

    Returns the written path. Always succeeds — missing source images render
    as labelled placeholders (per fit_into_cell).
    """
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    draw = ImageDraw.Draw(canvas)

    # ─── Header bar ────────────────────────────────────────────────
    draw.rectangle((0, 0, CANVAS_W, HEADER_H), fill=HEADER_BG)
    header_text = f"Order {order_id}    |    Dispatched {_format_date(dispatched_at)}"
    _draw_centered_text(
        draw, header_text, (0, 0, CANVAS_W, HEADER_H),
        font=_load_font(50, bold=True), fill=HEADER_FG,
    )

    # ─── Row labels (SENT / RECEIVED vertical strip) ───────────────
    row1_top = HEADER_H + CELL_GAP
    row1_bot = row1_top + CELL_H
    row2_top = row1_bot + CELL_GAP
    row2_bot = row2_top + CELL_H

    draw.rectangle((0, row1_top, ROW_LABEL_W, row1_bot), fill=LABEL_BG)
    draw.rectangle((0, row2_top, ROW_LABEL_W, row2_bot), fill=LABEL_BG)

    # Rotate text 90° for vertical labels — draw on a tmp image then paste
    def _vertical_label(text: str, y_top: int, y_bot: int) -> None:
        label_font = _load_font(34, bold=True)
        # Make a tall narrow strip, draw, rotate, paste
        strip_w = y_bot - y_top
        strip_h = ROW_LABEL_W
        strip = Image.new("RGBA", (strip_w, strip_h), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(strip)
        bbox = sdraw.textbbox((0, 0), text, font=label_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        sdraw.text(
            ((strip_w - tw) // 2 - bbox[0], (strip_h - th) // 2 - bbox[1]),
            text, font=label_font, fill=ACCENT,
        )
        rotated = strip.rotate(90, expand=True)
        canvas.paste(rotated, (0, y_top), rotated)

    _vertical_label("SENT", row1_top, row1_bot)
    _vertical_label("RECEIVED", row2_top, row2_bot)

    # ─── 2×2 image cells ───────────────────────────────────────────
    col1_left = ROW_LABEL_W
    col1_right = col1_left + CELL_W
    col2_left = col1_right + CELL_GAP
    col2_right = col2_left + CELL_W

    def _paste_cell(src: Path, box: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = box
        cell_img = _fit_into_cell(src, right - left, bottom - top)
        canvas.paste(cell_img, (left, top))
        draw.rectangle((left, top, right - 1, bottom - 1), outline=(180, 180, 180), width=2)

    _paste_cell(pk_front, (col1_left, row1_top, col1_right, row1_bot))
    _paste_cell(pk_back, (col2_left, row1_top, col2_right, row1_bot))
    _paste_cell(rt_front, (col1_left, row2_top, col1_right, row2_bot))
    _paste_cell(rt_back, (col2_left, row2_top, col2_right, row2_bot))

    # ─── Footer block ──────────────────────────────────────────────
    footer_top = CANVAS_H - FOOTER_H
    draw.rectangle((0, footer_top, CANVAS_W, CANVAS_H), fill=FOOTER_BG)
    draw.line(
        ((0, footer_top), (CANVAS_W, footer_top)),
        fill=ACCENT,
        width=4,
    )

    title_font = _load_font(48, bold=True)
    body_font = _load_font(36, bold=False)
    accent_font = _load_font(40, bold=True)

    draw.text((40, footer_top + 24), "SENT vs RECEIVED", fill=ACCENT, font=title_font)

    lines: list[tuple[str, tuple[int, int, int], bool]] = [
        (f"Order ID:       {order_id}", INK, False),
        (f"Dispatched:     {_format_date(dispatched_at)}", INK, False),
        (f"Returned:       {_format_date(returned_at)}", INK, False),
    ]
    if fpc_sent or fpc_received:
        sent_str = fpc_sent or "(not detected)"
        recv_str = fpc_received or "(not detected)"
        fpc_match_visible = bool(fpc_sent and fpc_received and fpc_sent.upper() == fpc_received.upper())
        match_marker = "✓" if fpc_match_visible else "✗"
        match_colour = ACCENT if fpc_match_visible else WARN
        lines.append((f"FPC sent:       {sent_str}", INK, False))
        lines.append((f"FPC received:   {recv_str}   {match_marker}", match_colour, False))

    if suggested is not None:
        lines.append(
            (f"Suggested verdict: {suggested.verdict.value}  (confidence {suggested.confidence:.0%})",
             WARN if suggested.verdict.value != "OK" else ACCENT, True)
        )

    y = footer_top + 100
    for text, colour, bold in lines:
        font = accent_font if bold else body_font
        draw.text((50, y), text, fill=colour, font=font)
        y += 48

    # Mahika watermark — bottom right
    wm_font = _load_font(38, bold=True)
    bbox = draw.textbbox((0, 0), WATERMARK, font=wm_font)
    wm_w = bbox[2] - bbox[0]
    draw.text(
        (CANVAS_W - wm_w - 40, CANVAS_H - 60),
        WATERMARK,
        fill=ACCENT,
        font=wm_font,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output_path
