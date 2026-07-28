"""
config.py
=========
Centralised constants, colour schemes, and the PlotConfig dataclass.

All other modules import from here — no magic numbers scattered through the codebase.
"""
from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Colour constants
# ---------------------------------------------------------------------------
COLOR_GREEN  = "#00CC00"
COLOR_YELLOW = "#FFD700"
COLOR_RED    = "#CC0000"

# ---------------------------------------------------------------------------
# Plotting tuning constants
# ---------------------------------------------------------------------------
GRID_RESOLUTION: int   = 100    # interpolation grid points per axis
WAFER_RADIUS_FACTOR: float = 1.05  # expand radius slightly beyond data extents
MIN_POINTS_FOR_PLOT: int  = 4   # minimum die points needed to attempt a plot
MAX_WAFERS_PER_PAGE: int  = 25  # 5×5 grid on each PDF page
LINES_PER_SUMMARY_PAGE: int = 55
# DPI for the per-page PNG snapshots that become PowerPoint slides. These feed
# ONLY the PPTX (the PDF itself is vector), so this trades slide-image sharpness
# for deck size: at 110 a big multi-thousand-slide deck is roughly half the
# bytes of 150 and assembles faster, while still looking crisp on screen.
PAGE_PNG_DPI: int = 110


# ---------------------------------------------------------------------------
# ColorScheme
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ColorScheme:
    """RGB hex colours for the three threshold zones."""
    low:  str
    mid:  str
    high: str

    @classmethod
    def from_mode(cls, high_is_green: bool) -> "ColorScheme":
        """
        high_is_green=True  → low zone is red,   high zone is green.
        high_is_green=False → low zone is green, high zone is red.
        """
        if high_is_green:
            return cls(low=COLOR_RED, mid=COLOR_YELLOW, high=COLOR_GREEN)
        return cls(low=COLOR_GREEN, mid=COLOR_YELLOW, high=COLOR_RED)


# ---------------------------------------------------------------------------
# PlotConfig
# ---------------------------------------------------------------------------
@dataclass
class PlotConfig:
    """
    Immutable bundle of all user-facing plotting parameters.

    Centralising these here means every function receives a single typed
    object instead of a sprawling list of keyword arguments.
    """
    t_low:        float
    t_high:       float
    use_log:      bool = False
    high_is_green: bool = False
    mirror_x:     bool = False
    mirror_y:     bool = False
    rot_deg:      int  = 0   # must be one of {0, 90, 180, 270}

    def __post_init__(self) -> None:
        # Guarantee t_low ≤ t_high regardless of user input order
        self.t_low, self.t_high = min(self.t_low, self.t_high), max(self.t_low, self.t_high)
        if self.rot_deg not in (0, 90, 180, 270):
            raise ValueError(f"rot_deg must be 0/90/180/270, got {self.rot_deg}")

    @property
    def color_scheme(self) -> ColorScheme:
        return ColorScheme.from_mode(self.high_is_green)

    @property
    def log_suffix(self) -> str:
        """File-name suffix appended when log scale is active."""
        return "_LOG" if self.use_log else ""
