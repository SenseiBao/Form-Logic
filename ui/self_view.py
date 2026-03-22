from __future__ import annotations

import tkinter as tk

from ui import theme
from ui.components import RoundedPanel


class SelfView(tk.Frame):
    """Placeholder profile / settings tab."""

    def __init__(self, parent: tk.Misc, *, bg: str = theme.APP_SURFACE) -> None:
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        tk.Label(
            self,
            text="Self",
            font=theme.FONT_TITLE,
            fg=theme.TEXT_PRIMARY,
            bg=bg,
        ).pack(anchor="w", padx=28, pady=(16, 8))

        card = RoundedPanel(
            self,
            radius=theme.CORNER_RADIUS_LG,
            fill_rgb=(255, 255, 255),
            fill_alpha=theme.GLASS_FILL_RGBA[3],
        )
        card.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)

        tk.Label(
            card.body(),
            text="",
            font=theme.FONT_BODY,
            fg=theme.TEXT_MUTED,
            bg=theme.CARD_WHITE,
        ).pack(expand=True)
