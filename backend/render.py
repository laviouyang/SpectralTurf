"""
render.py - Turn the index numbers into small PNG pictures for the map.

DISPLAY ONLY: nothing here changes any number used in the statistics.
The pictures are made from the very same pixels as the statistics, so the
colors on the map and the numbers in the table can never disagree.

  - Every colored square is one real 10 m pixel (NDMI: 20 m data shown as ~2x2 blocks).
  - Pixels outside the drawn area are transparent.
  - Pixels inside the area that were rejected (cloud, shadow, ...) are gray,
    so the user can see where data is missing.
"""

import base64
import io

import numpy as np
from PIL import Image

import indices

# Color scales as (value, color) pairs. Values in between are blended; values
# beyond the ends get the end color. These are DISPLAY choices that keep colors
# meaning the same thing on every field - they are NOT health categories.
NDVI_COLORS = [
    (0.0, "#8c510a"),  # brown: bare ground, pavement (water is below 0)
    (0.2, "#d8b365"),
    (0.4, "#f7fcb9"),
    (0.6, "#78c679"),
    (0.8, "#006837"),  # dark green: dense green vegetation
]
NDMI_COLORS = [
    (-0.4, "#8c510a"),  # brown: dry
    (-0.2, "#d8b365"),
    (0.0, "#f5f5f5"),
    (0.2, "#5ab4ac"),
    (0.4, "#01665e"),  # teal: more water in leaves
]
REJECTED_RGBA = (150, 150, 150, 170)  # see-through gray

# Inspection layer colors.
LOW_RGBA = (231, 41, 138, 255)  # pink: notably less green than the rest of the field
CHECKED_RGBA = (255, 255, 255, 90)  # faint white: checked, not notably low
# Edge ring (not checked) and outside the area stay transparent.

# Same brightening as the /api/test/truecolor image. Only for viewing.
TRUE_COLOR_GAIN = 2.5


def _hex_to_rgb(color):
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def colorize(values, valid, inside, scale):
    """Color each valid pixel by its value; gray for rejected; transparent outside."""
    values = np.asarray(values, dtype=np.float64)
    rgba = np.zeros(values.shape + (4,), dtype=np.uint8)  # fully transparent to start

    stops = [value for value, _ in scale]
    colors = np.array([_hex_to_rgb(color) for _, color in scale])
    show = valid & np.isfinite(values)
    for channel in range(3):  # red, green, blue
        rgba[..., channel][show] = np.interp(values[show], stops, colors[:, channel]).round()
    rgba[..., 3][show] = 255

    rgba[inside & ~show] = REJECTED_RGBA
    return rgba


def true_color(b04, b03, b02, inside):
    """Natural-color picture (red, green, blue bands), brightened only for viewing."""
    rgb = np.stack([b04, b03, b02], axis=-1).astype(np.float64) * TRUE_COLOR_GAIN
    rgba = np.zeros(rgb.shape[:2] + (4,), dtype=np.uint8)
    rgba[..., :3] = (np.clip(rgb, 0, 1) * 255).round()
    rgba[..., 3] = np.where(inside, 255, 0)
    return rgba


def inspection_picture(ndvi, valid, inside):
    """Pink = notably low, faint white = checked and fine, gray = rejected (cloud etc.)."""
    masks = indices.inspection_masks(ndvi, valid, inside)
    rgba = np.zeros(np.shape(ndvi) + (4,), dtype=np.uint8)
    rgba[inside & ~valid] = REJECTED_RGBA
    rgba[masks["checked"]] = CHECKED_RGBA
    rgba[masks["low"]] = LOW_RGBA
    return rgba


def to_data_url(rgba):
    """Encode a picture as a PNG 'data URL' the browser can show directly."""
    buffer = io.BytesIO()
    Image.fromarray(rgba).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def make_images(bands):
    """The three map layers for one analysis. Row 0 of each picture is the north edge."""
    inside = np.asarray(bands["dataMask"]) > 0
    valid = indices.valid_pixel_mask(bands["SCL"], bands["dataMask"])
    ndvi = indices.compute_ndvi(bands["B04"], bands["B08"])
    ndmi = indices.compute_ndmi(bands["B8A"], bands["B11"])
    return {
        "ndvi": to_data_url(colorize(ndvi, valid, inside, NDVI_COLORS)),
        "ndmi": to_data_url(colorize(ndmi, valid, inside, NDMI_COLORS)),
        "true_color": to_data_url(true_color(bands["B04"], bands["B03"], bands["B02"], inside)),
        "inspection": to_data_url(inspection_picture(ndvi, valid, inside)),
    }


def color_scales():
    """The scales, sent to the website so its legends use exactly the same colors."""
    return {
        "ndvi": NDVI_COLORS,
        "ndmi": NDMI_COLORS,
        "rejected": "rgba(150, 150, 150, 0.67)",
        "inspection_low": "rgb(231, 41, 138)",
        "inspection_checked": "rgba(255, 255, 255, 0.35)",
    }
