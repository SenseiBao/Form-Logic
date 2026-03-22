from __future__ import annotations

import tkinter as tk
from typing import Callable, Literal, Tuple

from PIL import ImageTk

from ui import theme


TabId = Literal["home", "history", "self", "settings"]


def _parent_bg(parent: tk.Misc, fallback: str) -> str:
    try:
        return str(parent.cget("bg"))
    except tk.TclError:
        return fallback


class RoundedPanel(tk.Canvas):
    """
    Frosted card with large corner radius (PIL rounded rect).
    expand_fill=True: fills parent; redraws on canvas resize.
    expand_fill=False: hugs inner content width/height (e.g. history rows, nav pill).
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        radius: int = theme.CORNER_RADIUS_LG,
        fill_rgb: Tuple[int, int, int] = (255, 255, 255),
        fill_alpha: int = 236,
        outline_rgb: Tuple[int, int, int] | None = None,
        inset: int | None = None,
        expand_fill: bool = True,
    ) -> None:
        pbg = _parent_bg(parent, theme.APP_SURFACE)
        super().__init__(parent, highlightthickness=0, bd=0, bg=pbg)
        self._radius = radius
        self._fill_rgb = fill_rgb
        self._fill_alpha = fill_alpha
        out = outline_rgb if outline_rgb is not None else theme.CARD_OUTLINE_RGB
        self._outline_rgba: Tuple[int, int, int, int] = (*out, 255)
        self._inset = inset if inset is not None else max(14, min(radius, 22))
        self._expand_fill = expand_fill
        self._photo: ImageTk.PhotoImage | None = None
        inner_hex = "#%02x%02x%02x" % fill_rgb
        self._inner = tk.Frame(self, bg=inner_hex, highlightthickness=0, bd=0)
        self._win_id: int | None = None
        if expand_fill:
            self.bind("<Configure>", self._on_self_configure)
        else:
            self._inner.bind("<Configure>", self._on_inner_configure)

    def body(self) -> tk.Frame:
        return self._inner

    def fit_hug(self) -> None:
        if self._expand_fill:
            return
        self._on_inner_configure()

    def _paint(self, w: int, h: int) -> None:
        if w < 4 or h < 4:
            return
        fill = (*self._fill_rgb, self._fill_alpha)
        img = theme.rounded_rectangle_rgba(w, h, self._radius, fill, self._outline_rgba, 1)
        self._photo = ImageTk.PhotoImage(img, master=self)
        self.delete("panel")
        self.create_image(0, 0, anchor="nw", image=self._photo, tags="panel")
        ins = self._inset
        iw = max(1, w - 2 * ins)
        ih = max(1, h - 2 * ins)
        if self._win_id is None:
            self._win_id = self.create_window(ins, ins, window=self._inner, anchor="nw")
        self.coords(self._win_id, ins, ins)
        self.itemconfig(self._win_id, width=iw, height=ih)

    def _on_self_configure(self, event: tk.Event) -> None:
        self._paint(max(4, event.width), max(4, event.height))

    def _on_inner_configure(self, _event: tk.Event | None = None) -> None:
        self.update_idletasks()
        try:
            mw = int(self.master.winfo_width())
        except tk.TclError:
            mw = 0
        iw = self._inner.winfo_reqwidth()
        ih = self._inner.winfo_reqheight()
        ins = self._inset
        w = max(iw + 2 * ins, mw - 8) if mw > 24 else iw + 2 * ins
        h = ih + 2 * ins
        w = max(w, 40)
        h = max(h, 28)
        self.configure(width=w, height=h)
        self._paint(w, h)


class PillButton(tk.Canvas):
    """Rounded pill-shaped button."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        width: int = 120,
        height: int = 44,
        fill: str = theme.CARD_WHITE,
        text_color: str = theme.TEXT_PRIMARY,
        font: tuple = theme.FONT_SUB,
        canvas_bg: str = "#E4EEF2",
    ) -> None:
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0, bg=canvas_bg)
        self._cmd = command
        # Do not use self._w — tkinter.Misc reserves it for the widget's Tcl path.
        self._pill_w, self._pill_h = width, height
        self._fill = fill
        self._text = text
        self._text_color = text_color
        self._font = font
        self.bind("<Button-1>", lambda e: self._cmd())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    def _on_enter(self, _e: object) -> None:
        self.itemconfig(self._rect, fill="#F3F4F6")

    def _on_leave(self, _e: object) -> None:
        self.itemconfig(self._rect, fill=self._fill)

    def _draw(self) -> None:
        self.delete("all")
        r = self._pill_h // 2
        self._rect = self.create_round_rect(
            2, 2, self._pill_w - 2, self._pill_h - 2, r, fill=self._fill, outline=theme.CARD_BORDER
        )
        self.create_text(
            self._pill_w // 2, self._pill_h // 2, text=self._text, fill=self._text_color, font=self._font
        )

    def create_round_rect(self, x1: int, y1: int, x2: int, y2: int, r: int, **kwargs: object) -> int:
        return self.create_polygon(
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1,
            smooth=True,
            **kwargs,
        )


class GradientPillButton(tk.Canvas):
    """Primary CTA with purple gradient (Begin / main actions)."""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        *,
        width: int = 140,
        height: int = 46,
        canvas_bg: str = theme.CARD_WHITE,
    ) -> None:
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0, bg=canvas_bg)
        self._cmd = command
        self._pill_w, self._pill_h = width, height
        self._text = text
        self._canvas_bg = canvas_bg
        self._hover = False
        self._photo: ImageTk.PhotoImage | None = None
        self.bind("<Button-1>", lambda _e: self._cmd())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    def _on_enter(self, _e: object) -> None:
        self._hover = True
        self._draw()

    def _on_leave(self, _e: object) -> None:
        self._hover = False
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        r = self._pill_h // 2
        img = theme.begin_button_gradient_rgba(self._pill_w, self._pill_h, r, hover=self._hover)
        self._photo = ImageTk.PhotoImage(img, master=self)
        self.create_image(self._pill_w // 2, self._pill_h // 2, image=self._photo)
        self.create_text(
            self._pill_w // 2,
            self._pill_h // 2,
            text=self._text,
            fill="#FFFFFF",
            font=theme.FONT_CTA,
        )


class BottomNav(tk.Frame):
    """Floating rounded glass pill over soft dock background."""

    def __init__(
        self,
        parent: tk.Misc,
        on_select: Callable[[TabId], None],
        *,
        bg: str = theme.NAV_DOCK_BG,
    ) -> None:
        super().__init__(parent, highlightthickness=0, bd=0, bg=bg)
        self._on_select = on_select
        self._active: TabId = "home"
        self._outer_bg = bg

        holder = tk.Frame(self, bg=bg, highlightthickness=0, bd=0, height=92)
        holder.pack(fill=tk.X, pady=(4, 18))
        holder.pack_propagate(False)

        self._deck = RoundedPanel(
            holder,
            radius=theme.CORNER_RADIUS_MD,
            fill_rgb=(255, 255, 255),
            fill_alpha=245,
            expand_fill=False,
        )
        self._deck.place(relx=0.5, rely=0.5, anchor="center")

        row = tk.Frame(self._deck.body(), bg=theme.CARD_WHITE, highlightthickness=0, bd=0)
        row.pack(padx=12, pady=8)

        self._btns: dict[TabId, tk.Label] = {}

        for tid, label in [
            ("home", "Home"),
            ("history", "History"),
            ("self", "Self"),
            ("settings", "Settings"),
        ]:
            lbl = tk.Label(
                row,
                text=label,
                font=theme.FONT_NAV_ACTIVE if tid == "home" else theme.FONT_NAV,
                fg=theme.ACCENT_NAV_ACTIVE if tid == "home" else theme.TEXT_MUTED,
                bg=theme.CARD_WHITE,
                cursor="hand2",
                padx=18,
                pady=4,
            )
            lbl.pack(side=tk.LEFT, expand=True)
            lbl.bind("<Button-1>", lambda e, t=tid: self._click(t))
            self._btns[tid] = lbl

        self._deck.after_idle(self._deck.fit_hug)

    def _click(self, tid: TabId) -> None:
        self._active = tid
        for t, lbl in self._btns.items():
            if t == tid:
                lbl.configure(font=theme.FONT_NAV_ACTIVE, fg=theme.ACCENT_NAV_ACTIVE)
            else:
                lbl.configure(font=theme.FONT_NAV, fg=theme.TEXT_MUTED)
        self._on_select(tid)

    def set_active(self, tid: TabId) -> None:
        self._click(tid)


class ScrollableFrame(tk.Frame):
    """Vertical scroll with mousewheel (when bound by parent)."""

    def __init__(self, parent: tk.Misc, *, bg: str) -> None:
        super().__init__(parent, highlightthickness=0, bd=0, bg=bg)
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=bg)
        self._sb = tk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._inner = tk.Frame(self._canvas, bg=bg, highlightthickness=0, bd=0)
        self._win_id = self._canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._canvas.configure(yscrollcommand=self._sb.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._sb.pack(side=tk.RIGHT, fill=tk.Y)

        self._inner.bind("<Configure>", self._on_inner_config)
        self._canvas.bind("<Configure>", self._on_canvas_config)

    def _on_inner_config(self, _e: object) -> None:
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_config(self, e: tk.Event) -> None:
        self._canvas.itemconfig(self._win_id, width=e.width)

    def body(self) -> tk.Frame:
        return self._inner

    def on_mousewheel(self, event: tk.Event) -> str | None:
        if hasattr(event, "delta") and event.delta:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        elif getattr(event, "num", None) == 4:
            self._canvas.yview_scroll(-1, "units")
        elif getattr(event, "num", None) == 5:
            self._canvas.yview_scroll(1, "units")
        return "break"
