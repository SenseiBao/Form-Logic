from __future__ import annotations

import tkinter as tk
from typing import List, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageTk

# Surfaces (airy mesh gradient family — very soft, mockup-like)
APP_SURFACE = "#F2F0FA"  # pale lavender-grey (main dashboard)
HOME_GREETING_BG = "#FFFFFF"  # greeting strip under header
NAV_DOCK_BG = "#EEF0F8"
METRICS_PANEL = APP_SURFACE
VIDEO_CARD_BG = "#E8EDF3"
VIDEO_CARD_RGB = (232, 237, 243)
METRICS_CARD_BG = "#FFFCF8"
METRICS_CARD_RGB = (255, 252, 248)

# Legacy / shared
BG_TOP = (208, 232, 242)  # #D0E8F2 sky
BG_BOTTOM = (254, 245, 231)  # #FEF5E7 warm cream
ACCENT_GREEN = "#34D399"
ACCENT_PURPLE = "#7C3AED"  # tagline / secondary accent (violet)
ACCENT_PINK = "#EC4899"
ACCENT_AMBER = "#FBBF24"
ACCENT_INDIGO = "#2563EB"
ACCENT_NAV_ACTIVE = "#7C3AED"  # active tab (purple)
CARD_WHITE = "#FFFFFF"
CARD_BORDER = "#E4E1F0"
CARD_OUTLINE_RGB = (218, 212, 235)  # light purple rim on white cards
COMBO_FIELD_GREY = "#EBEBF0"  # grey dropdown fields
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
FONT_DATE = ("Helvetica", 12)  # date line under header
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
    """Legacy soft mesh (TL → BR); prefer header_banner_gradient for the app chrome."""
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


def header_banner_gradient(width: int, height: int) -> Image.Image:
    """Header strip: vivid blue → indigo → purple → magenta → orange (left to right)."""
    return horizontal_gradient_stops(
        width,
        height,
        [
            (0.0, (29, 78, 216)),
            (0.28, (79, 70, 229)),
            (0.45, (124, 58, 237)),
            (0.62, (168, 85, 247)),
            (0.78, (217, 70, 239)),
            (1.0, (251, 146, 60)),
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


def begin_button_gradient_rgba(
    width: int,
    height: int,
    radius: int,
    *,
    hover: bool = False,
) -> Image.Image:
    """Primary Begin CTA: purple → magenta (left to right)."""
    w = max(1, int(width))
    h = max(1, int(height))
    r = min(radius, w // 2, h // 2)
    boost = 1.06 if hover else 1.0
    left = np.clip(np.array((91, 33, 182), dtype=np.float32) * boost, 0, 255)
    right = np.clip(np.array((217, 70, 239), dtype=np.float32) * boost, 0, 255)
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
