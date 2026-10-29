"""Bundled fonts (SIL OFL): Source Serif 4 for reading, Inter for the interface."""
import functools
import os

from PIL import ImageFont

DIR = os.environ.get("ROSSINI_FONT_DIR") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "fonts")


@functools.lru_cache(maxsize=64)
def load_font(family, size, bold=False):
    """family: 'serif' (reading) | 'sans' (interface)."""
    size = int(size)
    if family == "serif":
        f = ImageFont.truetype(os.path.join(DIR, "SourceSerif4.ttf"), size)
        f.set_variation_by_axes([600 if bold else 400, 20])  # [weight, optical size]
        return f
    return ImageFont.truetype(os.path.join(DIR, "Inter-SemiBold.otf" if bold else "Inter-Regular.otf"), size)
