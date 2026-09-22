"""Per-monitor DPI awareness, declared before Tk or any screenshot exists.

Why this is required
--------------------
A DPI-unaware process gets *logical* coordinates from Win32 (``GetWindowRect``,
``ClientToScreen``, ...), while ``PIL.ImageGrab`` returns *physical* pixels. On a
scaled display the two differ by the scale factor — on the machine this was found on,
the primary monitor is 3840x2160 at 175%, reported to an unaware process as
2194x1234. Cropping the rect Win32 reported therefore reads a completely different
part of the screen, so the OCR path analyses unrelated content and then sends it to
the configured APIs.

Declaring per-monitor awareness makes every coordinate physical, so the saved chat
rect, the UI Automation control rectangles and ImageGrab all agree.

Caveat for upgraders: a ``chat_rect`` saved by a build without this fix was measured
in logical units and must be re-calibrated (frame the chat area again), otherwise it
will still be off by the scale factor.
"""

from __future__ import annotations

import ctypes


_AWARENESS_NAMES = {0: "unaware", 1: "system", 2: "per-monitor"}


def current_awareness() -> str:
    """Report the process DPI awareness as reported by shcore."""
    try:
        value = ctypes.c_int()
        ctypes.windll.shcore.GetProcessDpiAwareness(None, ctypes.byref(value))
        return _AWARENESS_NAMES.get(value.value, f"unknown({value.value})")
    except Exception:  # noqa: BLE001
        return "unknown"


def enable_dpi_awareness() -> str:
    """Declare DPI awareness for this process.

    Safe to call repeatedly: an already-aware process is reported instead of being
    re-configured. Returns a short status string for logging.
    """
    existing = current_awareness()
    if existing in ("system", "per-monitor"):
        return f"already:{existing}"

    user32 = ctypes.windll.user32

    # Windows 10 1703+: PER_MONITOR_AWARE_V2 (-4), the right choice for mixed-DPI setups.
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except Exception:  # noqa: BLE001
        pass

    try:
        if ctypes.windll.shcore.SetProcessDpiAwareness(2) == 0:  # S_OK
            return "per-monitor"
    except Exception:  # noqa: BLE001
        pass

    try:
        if user32.SetProcessDPIAware():
            return "system"
    except Exception:  # noqa: BLE001
        pass

    return "unavailable"


def ui_scale() -> float:
    """System DPI divided by 96, used to size Tk geometry in physical pixels."""
    try:
        dpi = ctypes.windll.user32.GetDpiForSystem()
        if dpi:
            return dpi / 96.0
    except Exception:  # noqa: BLE001
        pass

    try:
        hdc = ctypes.windll.user32.GetDC(0)
        try:
            dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        finally:
            ctypes.windll.user32.ReleaseDC(0, hdc)
        if dpi:
            return dpi / 96.0
    except Exception:  # noqa: BLE001
        pass

    return 1.0
