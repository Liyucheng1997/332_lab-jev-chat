"""Tests for jev_windows.dpi — the process DPI awareness used by screen capture.

Without awareness Win32 reports logical coordinates while ImageGrab captures physical
pixels, so a rect taken from Win32 lands elsewhere on a scaled display. These tests
pin the contract that makes the two coordinate systems agree.
"""

import sys

import pytest

from jev_windows.dpi import current_awareness, enable_dpi_awareness, ui_scale


pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="DPI awareness is a Windows-only concern"
)


def test_enable_dpi_awareness_creates_an_aware_process():
    enable_dpi_awareness()
    assert current_awareness() in ("system", "per-monitor")


def test_enable_dpi_awareness_is_idempotent():
    enable_dpi_awareness()
    # Whatever the entry state, the second call must observe an already-configured
    # process instead of trying to reconfigure it.
    assert enable_dpi_awareness().startswith("already:")


def test_ui_scale_is_a_sane_multiplier():
    scale = ui_scale()
    assert isinstance(scale, float)
    assert 1.0 <= scale <= 4.0


def test_px_scales_hard_coded_pixel_sizes_by_the_display_dpi():
    from jev_windows.app import px

    assert px(500) == round(500 * ui_scale())
    assert px(500) >= 500
