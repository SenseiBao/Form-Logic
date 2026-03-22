"""Windows Per-Monitor DPI awareness + Tk font scaling so layouts stay crisp at 125%–225% scaling."""

from __future__ import annotations

import sys


def enable_windows_dpi_awareness() -> None:
    """Call before creating the root Tk window (Windows)."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        # 2 = PROCESS_PER_MONITOR_DPI_AWARE (Win 8.1+)
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def apply_tk_scaling(root) -> None:
    """Map logical Tk units to physical pixels using display DPI (helps fonts/padding at high scale)."""
    try:
        px_per_inch = float(root.winfo_fpixels("1i"))
        if px_per_inch > 1:
            # ~72 pt per inch; scaling = pixels per point
            root.tk.call("tk", "scaling", px_per_inch / 72.0)
    except Exception:
        pass
