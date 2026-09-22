import sys
from pathlib import Path


# Keep the calibrated Jev question set single-sourced in tools/jev when running
# from source. PyInstaller follows the same import during the packaged build.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from jev_windows.dpi import enable_dpi_awareness

# Declare DPI awareness before Tk exists: without it Win32 reports logical
# coordinates while ImageGrab captures physical pixels, so the framed chat rect
# lands somewhere else entirely on a scaled display (see jev_windows/dpi.py).
DPI_STATUS = enable_dpi_awareness()

from jev_windows.app import main


if __name__ == "__main__":
    main()
