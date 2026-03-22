from __future__ import annotations

import tkinter as tk
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageTk

# Surfaces (airy mesh gradient family — very soft, mockup-like)
APP_SURFACE = "#F2F7FB"
NAV_DOCK_BG = "#EAF2F9"
METRICS_PANEL = APP_SURFACE
VIDEO_CARD_BG = "#E8EDF3"
VIDEO_CARD_RGB = (232, 237, 243)
METRICS_CARD_BG = "#FFFCF8"
METRICS_CARD_RGB = (255, 252, 248)

# Legacy / shared
BG_TOP = (208, 232, 242)  # #D0E8F2 sky
BG_BOTTOM = (254, 245, 231)  # #FEF5E7 warm cream
ACCENT_GREEN = "#34D399"
ACCENT_PURPLE = "#7C8DB8"
ACCENT_PINK = "#EC4899"
ACCENT_AMBER = "#FBBF24"
ACCENT_INDIGO = "#2563EB"
ACCENT_NAV_ACTIVE = "#1D4ED8"
CARD_WHITE = "#FFFFFF"
CARD_BORDER = "#D4E4EF"
CARD_OUTLINE_RGB = (212, 224, 234)  # soft rim for rounded PIL cards
CORNER_RADIUS_LG = 32
CORNER_RADIUS_MD = 26
TEXT_PRIMARY = "#1A1A1A"
TEXT_MUTED = "#6B7280"
PILL_GREY = "#F1F4F8"
PANEL_GREY = VIDEO_CARD_BG

# Glass-style card fill (semi-opaque white)
GLASS_FILL_RGBA = (255, 255, 255, 236)

# Soft CTA gradient (optional)
GRAD_CTA_LEFT = (125, 186, 230)
GRAD_CTA_RIGHT = (255, 186, 140)

FONT_TITLE = ("Helvetica", 28, "bold")
FONT_HEADING = ("Helvetica", 18, "bold")
FONT_SUB = ("Helvetica", 14)
FONT_CTA = ("Helvetica", 14, "bold")
FONT_BODY = ("Helvetica", 13)
FONT_SMALL = ("Helvetica", 12)
FONT_NAV_ACTIVE = ("Helvetica", 14, "bold")
FONT_NAV = ("Helvetica", 14)


def _interp_stops(t: np.ndarray, stops: Sequence[Tuple[float, Tuple[int, int, int]]]) -> np.ndarray:
    """t: any shape, values 0..1. stops: sorted (position, (r,g,b)). Returns float RGB array + last dim 3."""
    ts = np.array([s[0] for s in stops], dtype=np.float64)
    cols = np.array([s[1] for s in stops], dtype=np.float64)
    flat = t.ravel()
    r = np.interp(flat, ts, cols[:, 0])
    g = np.interp(flat, ts, cols[:, 1])
    b = np.interp(flat, ts, cols[:, 2])
    out = np.stack([r, g, b], axis=-1).reshape(*t.shape, 3)
    return out


def diagonal_gradient_stops(
    width: int,
    height: int,
    stops: List[Tuple[float, Tuple[int, int, int]]],
) -> Image.Image:
    """Diagonal blend (top-left → bottom-right) through color stops."""
    w = max(1, int(width))
    h = max(1, int(height))
    yy, xx = np.indices((h, w), dtype=np.float64)
    denom = float((w - 1) + (h - 1)) or 1.0
    t = np.clip((xx + yy) / denom, 0.0, 1.0)
    rgb = _interp_stops(t, stops)
    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def vertical_gradient_stops(
    width: int,
    height: int,
    stops: List[Tuple[float, Tuple[int, int, int]]],
) -> Image.Image:
    """Top → bottom through color stops (full-bleed panels)."""
    w = max(1, int(width))
    h = max(1, int(height))
    t = np.linspace(0.0, 1.0, h, dtype=np.float64)[:, np.newaxis]
    t = np.broadcast_to(t, (h, w))
    rgb = _interp_stops(t, stops)
    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def horizontal_gradient_stops(
    width: int,
    height: int,
    stops: List[Tuple[float, Tuple[int, int, int]]],
) -> Image.Image:
    """Left → right through color stops (blue / yellow / orange bands)."""
    w = max(1, int(width))
    h = max(1, int(height))
    yy, xx = np.indices((h, w), dtype=np.float64)
    denom = float(w - 1) or 1.0
    u = np.clip(xx / denom, 0.0, 1.0)
    rgb = _interp_stops(u, stops)
    return Image.fromarray(rgb.astype(np.uint8), mode="RGB")


def diagonal_gradient_rgba(width: int, height: int) -> Image.Image:
    """Very subtle mesh: pale blue (TL) → cream → whisper peach/yellow (BR)."""
    return diagonal_gradient_stops(
        width,
        height,
        [
            (0.0, (205, 228, 246)),
            (0.35, (250, 251, 253)),
            (0.62, (255, 246, 236)),
            (0.85, (255, 250, 232)),
            (1.0, (254, 248, 226)),
        ],
    )


def rounded_rectangle_rgba(
    width: int,
    height: int,
    radius: int,
    fill: Tuple[int, int, int, int],
    outline: Tuple[int, int, int, int] | None = None,
    outline_w: int = 1,
) -> Image.Image:
    w = max(1, int(width))
    h = max(1, int(height))
    r = min(radius, w // 2, h // 2)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rect = (0, 0, w - 1, h - 1)
    draw.rounded_rectangle(rect, radius=r, fill=fill, outline=outline, width=outline_w if outline else 0)
    return img


def gradient_photo(master: tk.Misc, width: int, height: int) -> ImageTk.PhotoImage:
    img = diagonal_gradient_rgba(width, height)
    return ImageTk.PhotoImage(img, master=master)


def card_photo(
    master: tk.Misc,
    width: int,
    height: int,
    radius: int = 24,
    alpha: int = 242,
) -> ImageTk.PhotoImage:
    """Semi-opaque white card."""
    img = rounded_rectangle_rgba(width, height, radius, (255, 255, 255, alpha))
    return ImageTk.PhotoImage(img, master=master)


def nav_pill_photo(master: tk.Misc, width: int, height: int, radius: int = 28) -> ImageTk.PhotoImage:
    o = (*CARD_OUTLINE_RGB, 255)
    img = rounded_rectangle_rgba(width, height, radius, (255, 255, 255, 248), o, 1)
    return ImageTk.PhotoImage(img, master=master)


def gradient_cta_rgba(
    width: int,
    height: int,
    radius: int,
    *,
    hover: bool = False,
) -> Image.Image:
    """Horizontal soft blue→peach pill (RGBA, rounded)."""
    w = max(1, int(width))
    h = max(1, int(height))
    r = min(radius, w // 2, h // 2)
    boost = 1.09 if hover else 1.0
    left = np.clip(np.array(GRAD_CTA_LEFT, dtype=np.float32) * boost, 0, 255)
    right = np.clip(np.array(GRAD_CTA_RIGHT, dtype=np.float32) * boost, 0, 255)
    t = np.linspace(0.0, 1.0, w, dtype=np.float32)[np.newaxis, :, np.newaxis]
    row = left * (1.0 - t) + right * t
    rgb = np.broadcast_to(row, (h, w, 3)).astype(np.uint8)
    pil_rgb = Image.fromarray(rgb, mode="RGB")
    mask = rounded_rectangle_rgba(w, h, r, (255, 255, 255, 255))
    pil = pil_rgb.convert("RGBA")
    pil.putalpha(mask.split()[-1])
    return pil


def gradient_cta_photo(
    master: tk.Misc,
    width: int,
    height: int,
    radius: int,
    *,
    hover: bool = False,
) -> ImageTk.PhotoImage:
    img = gradient_cta_rgba(width, height, radius, hover=hover)
    return ImageTk.PhotoImage(img, master=master)
