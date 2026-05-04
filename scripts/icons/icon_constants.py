"""
Shared constants and helpers for icon generation scripts.

Importing this module sets the matplotlib font globally.
"""

import matplotlib

matplotlib.rcParams["font.family"] = "sans-serif"

# Output dimensions (all icons)
WIDTH = 800
HEIGHT = 500

# Render DPI (all icons)
DPI = 150

# GIF frame stride (1 = every timestep)
STEP = 1

# Station map colors
OCEAN_COLOR = "#a8c8e0"
LAND_COLOR = "#e8e0cc"
COUNTRY_EDGE_COLOR = "#777777"
STATE_EDGE_COLOR = "#999999"


def title_kwargs(scale, target_pt=12):
    """
    Return ax.text kwargs for a consistent title annotation, scaled to be
    readable in the final output regardless of render scale.

    Parameters
    ----------
    scale : int or float
        Render scale factor (e.g. 5 for static PNGs, 2 for GIFs).
    target_pt : int
        Desired apparent font size in the final output image.
    """
    return dict(
        fontsize=target_pt * scale,
        fontweight="normal",
        color="black",
        ha="right",
        va="top",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.5),
    )
