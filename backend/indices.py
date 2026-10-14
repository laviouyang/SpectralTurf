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

# Healthy-turf BASELINE - also OUR project's choices, NOT published standards.
# Comparing a field only with itself can't see a problem that covers the whole field,
# so we also compare every pixel with fixed values measured on real turf.
# Measured 2026 (interior pixels, real Sentinel-2 data):
#   healthy irrigated turf, 6 Colorado fields, Aug:  NDVI 5th percentile 0.57-0.86,
#                                                    NDMI 5th percentile 0.10-0.28
#   dry, unwatered meadow (Village Greens North Park): NDVI median 0.18, NDMI -0.14
#   artificial turf (Cherry Creek HS):                 NDVI median 0.19, NDMI -0.09
# The cutoffs sit in the gap between healthy turf and dry ground.
BASELINE_NDVI = 0.5
BASELINE_NDMI = 0.0
# Color check: does the pixel LOOK deep green, or yellow / pale, the way a person sees it?
# NGRDI = (Green - Red) / (Green + Red), a published visible-light greenness index
# (Tucker 1979). 10 m bands (B03, B04). Below 0 = more red than green (truly yellow,
# tan, or brown). Between 0 and 0.15 = pale or yellowish green.
# The student chose 0.15: only DEEP green counts as good. Measured share of pixels below
# 0.15: Memorial Park (deep green) 1-5%; DSG south 20%; Gates North (pale spots) 36% on
# 2025-06-01 and 52% on 2026-08-05; DSG east 64%; Village Greens 96%; dry meadow 100%.
# Strict on purpose: it flags many real fields that NDVI says are growing.
YELLOW_NGRDI = 0.15
# If at least half the checked turf is below the baseline, call it a whole-field problem.
WHOLE_FIELD_FRACTION = 0.5
# The baseline was measured on summer and early-fall turf. Grass that is still green-ing
# up in spring or dormant in winter is naturally lower, so we warn outside these months.
BASELINE_MONTHS = range(5, 11)  # May to October


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


def compute_ngrdi(b03, b04):
    """Visible greenness: green light vs red light. Below 0 looks yellow/brown."""
    return normalized_difference(b03, b04)


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


def analyze_bands(b04, b08, b8a, b11, scl, data_mask, b03=None):
    """
    Turn raw band arrays into the results the app reports.
    b03 (green) is used for the "looks yellow" color check; without it that check is skipped.
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
    ngrdi = compute_ngrdi(b03, b04) if b03 is not None else None
    inspection = inspection_indicator(ndvi, ndmi, valid, has_data, ngrdi)

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
        "ngrdi": summarize(ngrdi, valid) if ngrdi is not None else None,
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


def inspection_masks(ndvi, ndmi, valid, inside, ngrdi=None):
    """
    Which pixels the rules checked, and which of those are
      yellow         - LOOK yellow or pale instead of deep green (NGRDI below YELLOW_NGRDI)
      below_baseline - below the healthy-turf NDVI/NDMI baseline (compared with fixed values)
      low            - notably less green than the rest of this field (compared with itself)
    Used for both the numbers and the map picture, so they always match.
    """
    ndvi = np.asarray(ndvi, dtype=np.float64)
    ndmi = np.asarray(ndmi, dtype=np.float64)
    checked = valid & interior_mask(inside) & np.isfinite(ndvi)
    nothing = np.zeros_like(checked)
    if checked.sum() < MIN_VALID_PIXELS:
        return {"checked": checked, "low": nothing, "below_ndvi": nothing, "below_ndmi": nothing,
                "below_baseline": nothing, "yellow": nothing, "median": None, "cutoff": None}
    median = float(np.median(ndvi[checked]))
    cutoff = median - LOW_NDVI_MARGIN
    low = checked & (ndvi < cutoff)
    below_ndvi = checked & (ndvi < BASELINE_NDVI)
    below_ndmi = checked & (ndmi < BASELINE_NDMI)  # NaN NDMI compares False: never flagged
    yellow = nothing if ngrdi is None else checked & (np.asarray(ngrdi, dtype=np.float64) < YELLOW_NGRDI)
    return {"checked": checked, "low": low, "below_ndvi": below_ndvi, "below_ndmi": below_ndmi,
            "below_baseline": below_ndvi | below_ndmi, "yellow": yellow,
            "median": median, "cutoff": cutoff}


def _is_flagged(n_pixels, fraction):
    """Big enough to report: at least FLAG_MIN_FRACTION of the turf AND FLAG_MIN_PIXELS pixels."""
    return n_pixels >= FLAG_MIN_PIXELS and fraction >= FLAG_MIN_FRACTION


def inspection_indicator(ndvi, ndmi, valid, inside, ngrdi=None):
    """
    Rule-based, preliminary: does this field, or part of it, look less healthy?
    Three checks on the same pixels:
      1. Color: does the turf look yellow or pale instead of deep green?
      2. Baseline: is the turf below NDVI/NDMI values measured on healthy turf?
      3. Within-field: is a spot much less green than the rest of the field?
    Checks 1 and 2 compare with fixed values, so they also find whole-field problems.
    """
    masks = inspection_masks(ndvi, ndmi, valid, inside, ngrdi)
    n_checked = int(masks["checked"].sum())
    rule = (
        "Three checks, using only pixels away from the outline's edge (edge pixels mix turf with "
        "whatever is outside). (1) Color: a 10 m pixel counts as yellow or pale (not deep green) "
        f"if NGRDI = (green - red) / (green + red) is below {YELLOW_NGRDI}. Below 0 means more red "
        f"than green light (truly yellow or brown); 0 to {YELLOW_NGRDI} is pale green. Deep-green "
        "Memorial Park fields had at most 5% of pixels below this line. (2) Baseline: a pixel is below the healthy-turf baseline if its NDVI is "
        f"under {BASELINE_NDVI} or its NDMI is under {BASELINE_NDMI}. Healthy watered turf we "
        "measured at six Colorado fields in summer 2026 stayed above both; a dry, unwatered meadow "
        "was far below. NDMI is 20 m data, so it can only flag areas in blocks of about 20 m. "
        f"(3) Within-field: a pixel is notably low if its NDVI is more than {LOW_NDVI_MARGIN} below "
        f"this field's own median. If at least {WHOLE_FIELD_FRACTION:.0%} of the turf fails check 1 "
        "or 2, the whole field is flagged. Otherwise each check reports an area if it is at least "
        f"{FLAG_MIN_FRACTION:.0%} of the checked turf and at least {FLAG_MIN_PIXELS} pixels. "
        "All of these numbers are this project's choices, not a validated standard."
    )

    if masks["median"] is None:
        return {
            "status": "insufficient_evidence",
            "scope": None,
            "headline": "Insufficient evidence",
            "reason": (
                f"Only {n_checked} clear pixels away from the outline's edge "
                f"(minimum {MIN_VALID_PIXELS}). Draw a larger area or choose a clearer date."
            ),
            "rule": rule,
            "pixels_checked": n_checked,
        }

    ndvi = np.asarray(ndvi, dtype=np.float64)
    ndmi = np.asarray(ndmi, dtype=np.float64)
    median_ndmi = float(np.nanmedian(ndmi[masks["checked"]]))

    def share(mask):
        n = int(mask.sum())
        return n, n / n_checked

    n_yellow, yellow_fraction = share(masks["yellow"])  # check 1: color
    n_below, below_fraction = share(masks["below_baseline"])  # check 2: NDVI/NDMI baseline
    n_low, low_fraction = share(masks["low"])  # check 3: within-field
    n_bad, bad_fraction = share(masks["yellow"] | masks["below_baseline"])  # fails check 1 or 2

    details = {
        "rule": rule,
        "pixels_checked": n_checked,
        "field_median_ndvi": round(masks["median"], 3),
        "field_median_ndmi": round(median_ndmi, 3),
        "color": {
            "checked": ngrdi is not None,
            "ngrdi_cutoff": YELLOW_NGRDI,
            "yellow_pixels": n_yellow,
            "yellow_fraction": round(yellow_fraction, 3),
            "yellow_area_m2": n_yellow * 100,  # each pixel is 10 m x 10 m
        },
        "baseline": {
            "ndvi": BASELINE_NDVI,
            "ndmi": BASELINE_NDMI,
            "below_pixels": n_below,
            "below_fraction": round(below_fraction, 3),
            "below_ndvi_fraction": round(int(masks["below_ndvi"].sum()) / n_checked, 3),
            "below_ndmi_fraction": round(int(masks["below_ndmi"].sum()) / n_checked, 3),
            "below_area_m2": n_below * 100,
        },
        "cutoff_ndvi": round(masks["cutoff"], 3),
        "low_pixels": n_low,
        "low_fraction": round(low_fraction, 3),
        "low_area_m2": n_low * 100,
    }
    medians = f"median NDVI {masks['median']:.2f}, median NDMI {median_ndmi:.2f}"
    baseline = f"NDVI {BASELINE_NDVI} / NDMI {BASELINE_NDMI}"

    # One sentence per check that found something big enough to report.
    parts = []
    if _is_flagged(n_yellow, yellow_fraction):
        parts.append(
            f"{yellow_fraction:.0%} of the checked turf (about {n_yellow * 100:,} m²) looks yellow or "
            "pale instead of deep green (yellow on the Inspection map)."
        )
    if _is_flagged(n_below, below_fraction):
        parts.append(
            f"{below_fraction:.0%} (about {n_below * 100:,} m²) is below the healthy-turf baseline "
            f"({baseline}) (orange on the Inspection map)."
        )
    if _is_flagged(n_low, low_fraction):
        low_mean = float(ndvi[masks["low"]].mean())
        parts.append(
            f"{low_fraction:.0%} (about {n_low * 100:,} m²) is notably less green than the rest of "
            f"this field: average NDVI {low_mean:.2f} there (pink on the Inspection map)."
        )

    # Most of the field looks yellow or is below the baseline: a whole-field problem.
    if bad_fraction >= WHOLE_FIELD_FRACTION:
        return {
            "status": "may_warrant_inspection",
            "scope": "whole_field",
            "headline": "Most of this field may warrant inspection",
            "reason": (
                f"{bad_fraction:.0%} of the checked turf looks yellow or pale, or is below the "
                f"healthy-turf baseline. {' '.join(parts)} This field: {medians}. Healthy watered "
                "turf we measured in summer 2026 had median NDVI 0.64 to 0.92."
            ),
            **details,
        }

    if parts:
        return {
            "status": "may_warrant_inspection",
            "scope": "some_areas",
            "headline": "Some areas may warrant inspection",
            "reason": f"{' '.join(parts)} The field as a whole: {medians}.",
            **details,
        }

    return {
        "status": "no_area_stands_out",
        "scope": None,
        "headline": "No area stands out",
        "reason": (
            f"This field ({medians}) looks deep green, is above the healthy-turf baseline ({baseline}), "
            f"and only {low_fraction:.0%} of the checked turf is notably less green than the rest "
            "of the field."
        ),
        **details,
    }


def quality_warnings(results, tile_cloud_cover, observation_month=None):
    """Plain-language warnings about how much to trust one analysis."""
    warnings = []
    if observation_month is not None and observation_month not in BASELINE_MONTHS:
        warnings.append(
            "This image is from outside May-October. The healthy-turf baseline was measured on "
            "summer turf, and grass that is dormant or still greening up is naturally below it, "
            "so a low result this time of year may be normal for the season."
        )
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
