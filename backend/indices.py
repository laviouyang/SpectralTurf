"""
indices.py - The science math for SpectralTurf AI.

No internet here: just numbers in, numbers out. That makes it easy to test
(see test_indices.py) and easy to explain.

  NDVI = (B08 - B04) / (B08 + B04)    "how green / leafy is it?"     (10 m bands)
  NDMI = (B8A - B11) / (B8A + B11)    "how much water is in leaves?" (20 m bands)
"""

import numpy as np

# Sentinel-2 L2A Scene Classification (SCL) codes we REJECT.
# Source: Sentinel-2 L2A docs (SCL band). SCL itself is a 20 m product.
INVALID_SCL_CLASSES = {
    0: "no data",
    1: "saturated or defective",
    2: "dark area / topographic shadow",
    3: "cloud shadow",
    8: "cloud (medium probability)",
    9: "cloud (high probability)",
    10: "thin cirrus",
    11: "snow or ice",
}
# Kept: 4 vegetation, 5 not vegetated, 6 water, 7 unclassified.

# Our project's practical minimum - NOT a published scientific standard.
# 20 pixels at 10 m = 2,000 square meters, about 1/4 of a soccer field.
MIN_VALID_PIXELS = 20

# When to show a data-quality warning. Also OUR project's choices, not standards.
WARN_BELOW_VALID_FRACTION = 0.8  # more than 20% of the area's pixels rejected
WARN_ABOVE_TILE_CLOUD = 10  # whole satellite tile more than 10% cloudy
WARN_BELOW_NDMI_MEASUREMENTS = 20  # fewer than 20 independent 20 m pixels
# Median NDVI below this is typical of surfaces that are not living plants
# (pavement, bare soil, artificial turf). Approximate, from general NDVI ranges.
# Artificial turf at Cherry Creek HS looked green but measured NDVI 0.17 (2026-08-05).
WARN_BELOW_MEDIAN_NDVI = 0.3

# "May warrant inspection" rule - OUR project's choices, NOT a validated method.
# A pixel is "notably low" if its NDVI is more than LOW_NDVI_MARGIN below the
# field's own median NDVI on the same day. On turf that looked uniformly healthy at
# Village Greens (2026-08-05), NDVI varied by about 0.05-0.08 (standard deviation),
# so 0.20 is roughly 3x that normal variation.
LOW_NDVI_MARGIN = 0.20
# Flag the field only if notably-low pixels are at least 5% of the checked turf
# AND at least 5 pixels (500 m²), so one odd pixel can't trigger it.
FLAG_MIN_FRACTION = 0.05
FLAG_MIN_PIXELS = 5


def normalized_difference(a, b):
    """
    (a - b) / (a + b), computed safely.
    If a + b is zero (or almost zero), the answer is undefined, so we return
    NaN ("not a number") instead of crashing or inventing a value.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    total = a + b
    result = np.full(total.shape, np.nan)
    ok = np.abs(total) > 1e-6
    result[ok] = (a[ok] - b[ok]) / total[ok]
    return result


def compute_ndvi(b04, b08):
    return normalized_difference(b08, b04)


def compute_ndmi(b8a, b11):
    return normalized_difference(b8a, b11)


def valid_pixel_mask(scl, data_mask):
    """True where the pixel has real data AND isn't cloud, shadow, snow, etc."""
    scl = np.asarray(scl).round().astype(int)
    has_data = np.asarray(data_mask) > 0
    is_bad_class = np.isin(scl, list(INVALID_SCL_CLASSES.keys()))
    return has_data & ~is_bad_class


def summarize(values, mask):
    """Statistics for the pixels where mask is True and the value is a real number."""
    good = values[mask & np.isfinite(values)]
    if good.size == 0:
        return {"valid_pixels": 0, "mean": None, "median": None, "min": None, "max": None, "std": None}
    return {
        "valid_pixels": int(good.size),
        "mean": round(float(good.mean()), 3),
        "median": round(float(np.median(good)), 3),
        "min": round(float(good.min()), 3),
        "max": round(float(good.max()), 3),
        "std": round(float(good.std()), 3),
    }


def analyze_bands(b04, b08, b8a, b11, scl, data_mask):
    """
    Turn raw band arrays into the results the app reports.
    All arrays are on the same 10 m grid. B8A, B11 and SCL are really 20 m
    data that Sentinel Hub repeated into 2x2 blocks (nearest neighbor) -
    this does NOT create any new detail.
    """
    has_data = np.asarray(data_mask) > 0
    valid = valid_pixel_mask(scl, data_mask)

    ndvi = compute_ndvi(b04, b08)
    ndmi = compute_ndmi(b8a, b11)

    # Count why pixels were rejected, so the user can see it honestly.
    scl_int = np.asarray(scl).round().astype(int)
    rejected = {}
    for code, name in INVALID_SCL_CLASSES.items():
        n = int(np.sum(has_data & (scl_int == code)))
        if n > 0:
            rejected[name] = n

    # total     = every pixel in the rectangle around the area
    # with_data = pixels INSIDE the drawn area that have data (outside the area, dataMask is 0)
    # n_valid   = of those, the ones that are not cloud, shadow, snow, etc.
    total = int(has_data.size)
    with_data = int(has_data.sum())
    n_valid = int(valid.sum())

    ndvi_stats = summarize(ndvi, valid)
    ndmi_stats = summarize(ndmi, valid)
    inspection = inspection_indicator(ndvi, valid, has_data)

    if ndvi_stats["valid_pixels"] < MIN_VALID_PIXELS:
        status = "insufficient_evidence"
        message = (
            f"Only {ndvi_stats['valid_pixels']} clear pixels (minimum {MIN_VALID_PIXELS}). "
            "Try a larger area or a different date range."
        )
    else:
        status = "ok"
        message = "Enough clear pixels for a preliminary snapshot."

    return {
        "status": status,
        "message": message,
        "pixels": {
            "total_in_box": total,
            "with_data": with_data,
            "valid_after_masking": n_valid,
            # Share of the pixels inside the area that are usable (not of the whole rectangle).
            "valid_fraction": round(n_valid / with_data, 3) if with_data else 0,
            "rejected_by_reason": rejected,
        },
        "ndvi": ndvi_stats,
        "ndmi": {
            **ndmi_stats,
            "note": "NDMI uses 20 m bands. Each 20 m pixel covers four 10 m grid cells, "
                    f"so this is roughly {ndmi_stats['valid_pixels'] // 4} independent 20 m measurements.",
        },
        # Sanity check: raw surface reflectance should be roughly 0-1.
        # (If status is insufficient_evidence, these numbers are still real but too few
        # to rely on - the website does not show them as results.)
        "mean_reflectance": {
            name: (round(float(np.asarray(band)[valid].mean()), 4) if n_valid else None)
            for name, band in [("B04_red", b04), ("B08_nir", b08), ("B8A_nir_narrow", b8a), ("B11_swir", b11)]
        },
        "inspection": inspection,
    }


# ---------------------------------------------------------------------------
# Excluded areas (parts the user says are not turf, e.g. dirt infields)
# ---------------------------------------------------------------------------

def points_in_polygon(lons, lats, ring):
    """
    True where the point (lon, lat) is inside the polygon ring.
    "Ray casting": walk east from the point and count how many edges you cross.
    An odd number of crossings means the point is inside.
    """
    inside = np.zeros(np.shape(lons), dtype=bool)
    for (x1, y1), (x2, y2) in zip(ring[:-1], ring[1:]):
        crosses = (y1 > lats) != (y2 > lats)  # this edge spans the point's latitude
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = x1 + (lats - y1) * (x2 - x1) / (y2 - y1)  # where the edge is at that latitude
        inside ^= crosses & (lons < x_at)  # flip inside/outside at each crossing
    return inside


def excluded_pixel_mask(exclusions, box, shape):
    """
    True for every grid pixel whose CENTER falls inside any excluded polygon.
    The grid covers the box evenly, with row 0 at the north edge (same as the
    satellite data), so we can work out each pixel's center coordinates.
    """
    west, south, east, north = box
    height, width = shape
    lons = west + (np.arange(width) + 0.5) * (east - west) / width
    lats = north - (np.arange(height) + 0.5) * (north - south) / height
    lon_grid, lat_grid = np.meshgrid(lons, lats)

    mask = np.zeros(shape, dtype=bool)
    for geometry in exclusions:
        mask |= points_in_polygon(lon_grid, lat_grid, geometry["coordinates"][0])
    return mask


def apply_exclusions(bands, exclusions, box):
    """
    Treat excluded pixels exactly like pixels outside the outline: dataMask = 0.
    Then nothing downstream (statistics, warnings, inspection rule, pictures)
    uses them. Returns how many pixels inside the outline were excluded.
    """
    if not exclusions:
        return 0
    data_mask = np.asarray(bands["dataMask"])
    excluded = excluded_pixel_mask(exclusions, box, data_mask.shape)
    n_excluded = int(np.sum(excluded & (data_mask > 0)))
    bands["dataMask"] = np.where(excluded, 0, data_mask)
    return n_excluded


# ---------------------------------------------------------------------------
# "May warrant inspection" indicator (Stage 7)
# ---------------------------------------------------------------------------

def interior_mask(inside):
    """
    True for pixels inside the area whose 4 neighbors (up, down, left, right) are
    also inside. This skips the outer ring of pixels, which often mix turf with
    whatever is just outside the outline (dirt, pavement, trees).
    """
    inside = np.asarray(inside, dtype=bool)
    interior = inside.copy()
    interior[1:, :] &= inside[:-1, :]   # neighbor above is inside
    interior[:-1, :] &= inside[1:, :]   # neighbor below is inside
    interior[:, 1:] &= inside[:, :-1]   # neighbor to the left is inside
    interior[:, :-1] &= inside[:, 1:]   # neighbor to the right is inside
    # Pixels on the picture's border have a missing neighbor, so they are edges too.
    interior[0, :] = interior[-1, :] = False
    interior[:, 0] = interior[:, -1] = False
    return interior


def inspection_masks(ndvi, valid, inside):
    """
    Which pixels the rule checked, and which of those are notably low.
    Used for both the numbers and the map picture, so they always match.
    """
    ndvi = np.asarray(ndvi, dtype=np.float64)
    checked = valid & interior_mask(inside) & np.isfinite(ndvi)
    if checked.sum() < MIN_VALID_PIXELS:
        return {"checked": checked, "low": np.zeros_like(checked), "median": None, "cutoff": None}
    median = float(np.median(ndvi[checked]))
    cutoff = median - LOW_NDVI_MARGIN
    low = checked & (ndvi < cutoff)
    return {"checked": checked, "low": low, "median": median, "cutoff": cutoff}


def inspection_indicator(ndvi, valid, inside):
    """Rule-based, preliminary: does any part of this field stand out as less green?"""
    masks = inspection_masks(ndvi, valid, inside)
    n_checked = int(masks["checked"].sum())
    rule = (
        f"A 10 m pixel counts as notably low if its NDVI is more than {LOW_NDVI_MARGIN} below "
        f"this field's own median NDVI on the same day. The field is flagged if those pixels are at "
        f"least {FLAG_MIN_FRACTION:.0%} of the checked turf and at least {FLAG_MIN_PIXELS} pixels. "
        "The outer ring of pixels is skipped because it mixes turf with whatever is outside the "
        "outline. These numbers are this project's choices, not a validated standard."
    )

    if masks["median"] is None:
        return {
            "status": "insufficient_evidence",
            "headline": "Insufficient evidence",
            "reason": (
                f"Only {n_checked} clear pixels away from the outline's edge "
                f"(minimum {MIN_VALID_PIXELS}). Draw a larger area or choose a clearer date."
            ),
            "rule": rule,
            "pixels_checked": n_checked,
        }

    n_low = int(masks["low"].sum())
    low_fraction = n_low / n_checked
    details = {
        "rule": rule,
        "pixels_checked": n_checked,
        "field_median_ndvi": round(masks["median"], 3),
        "cutoff_ndvi": round(masks["cutoff"], 3),
        "low_pixels": n_low,
        "low_fraction": round(low_fraction, 3),
        "low_area_m2": n_low * 100,  # each pixel is 10 m x 10 m
    }

    if n_low >= FLAG_MIN_PIXELS and low_fraction >= FLAG_MIN_FRACTION:
        low_mean = float(np.asarray(ndvi)[masks["low"]].mean())
        return {
            "status": "may_warrant_inspection",
            "headline": "May warrant inspection",
            "reason": (
                f"{low_fraction:.0%} of the checked turf (about {n_low * 100:,} m²) is notably less "
                f"green than the rest of this field: average NDVI {low_mean:.2f} there, compared with "
                f"{masks['median']:.2f} for the field as a whole. These spots are pink on the "
                "Inspection map layer."
            ),
            **details,
        }

    return {
        "status": "no_area_stands_out",
        "headline": "No area stands out",
        "reason": (
            f"Only {low_fraction:.0%} of the checked turf is notably less green than the rest of "
            "the field. This compares parts of the field with each other, so a problem affecting "
            "the whole field evenly would not stand out."
        ),
        **details,
    }


def quality_warnings(results, tile_cloud_cover):
    """Plain-language warnings about how much to trust one analysis."""
    warnings = []
    pixels = results["pixels"]

    reasons = "; ".join(pixels["rejected_by_reason"]) or "invalid values"
    if pixels["with_data"] and pixels["valid_after_masking"] == 0:
        warnings.append(
            f"Every pixel inside your area was rejected. Reason: {reasons}. "
            "There is no usable data for this date - try a different date range."
        )
    elif pixels["with_data"] and pixels["valid_fraction"] < WARN_BELOW_VALID_FRACTION:
        rejected_pct = round((1 - pixels["valid_fraction"]) * 100)
        warnings.append(
            f"{rejected_pct}% of the pixels inside your area were rejected. Reason: {reasons}. "
            "The numbers describe only the clear part."
        )

    if tile_cloud_cover > WARN_ABOVE_TILE_CLOUD:
        warnings.append(
            f"The satellite image tile was {tile_cloud_cover}% cloudy overall. Thin haze can slip "
            "past cloud masking, so compare with the true-color picture."
        )

    median_ndvi = results["ndvi"]["median"]
    if results["status"] == "ok" and median_ndvi < WARN_BELOW_MEDIAN_NDVI:
        warnings.append(
            f"This area's typical NDVI ({median_ndvi}) is in the range of surfaces that are not "
            "living plants. It may be artificial turf, bare ground, pavement, or grass that is "
            "dormant or dead. Artificial turf can look green in photos but does not reflect "
            "near-infrared light like real leaves, so this app cannot evaluate it."
        )

    measurements_20m = results["ndmi"]["valid_pixels"] // 4
    if results["status"] == "ok" and measurements_20m < WARN_BELOW_NDMI_MEASUREMENTS:
        warnings.append(
            f"NDMI is based on only about {measurements_20m} independent 20 m measurements, "
            "so treat it with extra caution."
        )
    return warnings
