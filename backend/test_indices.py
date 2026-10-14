"""
test_indices.py - Checks the NDVI/NDMI math with numbers we can work out by hand.
No internet or credentials needed.

Run:  python test_indices.py
"""

import math

import numpy as np

from indices import (
    analyze_bands,
    apply_exclusions,
    excluded_pixel_mask,
    points_in_polygon,
    compute_ndmi,
    compute_ndvi,
    compute_ngrdi,
    inspection_indicator,
    interior_mask,
    quality_warnings,
    valid_pixel_mask,
)
from render import NDVI_COLORS, REJECTED_RGBA, colorize, to_data_url

# 1. Healthy grass: lots of NIR, little red.  (0.40 - 0.05) / (0.40 + 0.05) = 0.778
assert abs(compute_ndvi([0.05], [0.40])[0] - 0.7778) < 0.001
print("PASS  healthy grass NDVI = 0.778")

# 2. Pavement: red and NIR about equal -> NDVI near 0
assert abs(compute_ndvi([0.20], [0.22])[0] - 0.0476) < 0.001
print("PASS  pavement NDVI = 0.048")

# 3. Wetter leaves: B8A > B11 -> positive NDMI. (0.35 - 0.20) / 0.55 = 0.273
assert abs(compute_ndmi([0.35], [0.20])[0] - 0.2727) < 0.001
print("PASS  NDMI = 0.273")

# 4. Zero denominator must give NaN, not a crash or a made-up number
assert math.isnan(compute_ndvi([0.0], [0.0])[0])
print("PASS  0/0 gives NaN (no data), not an error")

# 5. Cloud (SCL 9), shadow (3) and no-data pixels are rejected; vegetation (4) kept
scl = np.array([4, 9, 3, 4])
data_mask = np.array([1, 1, 1, 0])
assert valid_pixel_mask(scl, data_mask).tolist() == [True, False, False, False]
print("PASS  cloud, shadow and no-data pixels are masked out")

# 6. Too few clear pixels -> honest "insufficient evidence"
small = np.full((3, 3), 0.1)
r = analyze_bands(small, small * 4, small * 3, small * 2, np.full((3, 3), 4), np.ones((3, 3)))
assert r["status"] == "insufficient_evidence"
print("PASS  9 pixels -> insufficient_evidence")

# 7. Fully cloudy box -> no statistics invented
big = np.full((10, 10), 0.1)
r = analyze_bands(big, big * 4, big * 3, big * 2, np.full((10, 10), 9), np.ones((10, 10)))
assert r["ndvi"]["mean"] is None and r["status"] == "insufficient_evidence"
print("PASS  all-cloud box -> no mean reported")

# 8. Pixels outside the drawn area (dataMask 0) are ignored, even if they look like grass.
#    Left half: inside the area, NDVI 0.6. Right half: outside, NDVI 0.0 (should not count).
red = np.full((10, 10), 0.10)
nir = np.full((10, 10), 0.40)
nir[:, 5:] = 0.10
inside = np.zeros((10, 10))
inside[:, :5] = 1
r = analyze_bands(red, nir, nir, nir * 0.5, np.full((10, 10), 4), inside)
assert r["ndvi"]["mean"] == 0.6 and r["pixels"]["with_data"] == 50
assert r["pixels"]["valid_fraction"] == 1.0
print("PASS  pixels outside the drawn area are ignored")

# 9. A clear, large area has no warnings; a half-cloudy one warns and names the reason.
clear = analyze_bands(red, nir, nir, nir * 0.5, np.full((10, 10), 4), np.ones((10, 10)))
assert quality_warnings(clear, tile_cloud_cover=0) == []
half_cloud = np.full((10, 10), 4)
half_cloud[:5] = 9
cloudy = analyze_bands(red, nir, nir, nir * 0.5, half_cloud, np.ones((10, 10)))
warnings = quality_warnings(cloudy, tile_cloud_cover=0)
assert "50%" in warnings[0] and "cloud" in warnings[0]
# Only 50 clear pixels = about 12 independent 20 m measurements -> NDMI warning too.
assert len(warnings) == 2 and "12 independent" in warnings[1]
print("PASS  half-cloudy area -> '50% ... rejected (cloud)' + small-NDMI warning")

# 9b. Completely cloudy: say there is NO usable data (not "describes the clear part").
all_cloud = analyze_bands(red, nir, nir, nir * 0.5, np.full((10, 10), 9), np.ones((10, 10)))
warnings = quality_warnings(all_cloud, tile_cloud_cover=0)
assert len(warnings) == 1 and "Every pixel" in warnings[0] and "no usable data" in warnings[0]
print("PASS  all-cloud area -> 'Every pixel ... rejected ... no usable data'")

# 9c. Green-looking but low NDVI (like artificial turf, NDVI ~0.17) -> "not living plants" warning.
fake = analyze_bands(np.full((10, 10), 0.10), np.full((10, 10), 0.14), nir, nir * 0.5,
                     np.full((10, 10), 4), np.ones((10, 10)))
assert any("artificial turf" in w for w in quality_warnings(fake, tile_cloud_cover=0))
assert not any("artificial turf" in w for w in quality_warnings(clear, tile_cloud_cover=0))
print("PASS  low-NDVI area -> 'may be artificial turf, bare ground...' warning")

# 10. Map picture: valid pixel colored by value, rejected pixel gray, outside transparent.
values = np.array([[0.8, 0.8, 0.8]])
valid = np.array([[True, False, False]])
inside = np.array([[True, True, False]])
picture = colorize(values, valid, inside, NDVI_COLORS)
assert picture[0, 0].tolist() == [0x00, 0x68, 0x37, 255]  # NDVI 0.8 -> dark green
assert tuple(picture[0, 1]) == REJECTED_RGBA  # inside but rejected -> gray
assert picture[0, 2, 3] == 0  # outside the area -> transparent
assert to_data_url(picture).startswith("data:image/png;base64,")
print("PASS  map picture: green / gray / transparent are correct")

# 11. The outer ring of pixels is skipped by the inspection rule.
ring = interior_mask(np.ones((4, 4)))
assert ring.sum() == 4 and ring[1:3, 1:3].all()  # only the middle 2x2 is "interior"
print("PASS  inspection rule skips the outer ring of pixels")

# 12. Even field (NDVI 0.7 everywhere) -> no area stands out.
field = np.full((12, 12), 0.7)
everywhere = np.ones((12, 12), dtype=bool)
wet = np.full((12, 12), 0.2)  # healthy NDMI, above the baseline
r = inspection_indicator(field, wet, everywhere, everywhere)
assert r["status"] == "no_area_stands_out" and r["low_pixels"] == 0
print("PASS  even field -> 'No area stands out'")

# 13. A 3x3 brown patch (NDVI 0.3) in the middle -> flagged: 9 px of 100 checked = 9%.
patchy = field.copy()
patchy[5:8, 5:8] = 0.3
r = inspection_indicator(patchy, wet, everywhere, everywhere)
assert r["status"] == "may_warrant_inspection"
assert r["low_pixels"] == 9 and r["pixels_checked"] == 100 and r["low_area_m2"] == 900
print("PASS  3x3 low patch -> 'May warrant inspection', 9 px = 900 m²")

# 14. The same low values ONLY on the edge ring -> ignored (likely mixed edge pixels).
edgy = field.copy()
edgy[0, :] = 0.3
r = inspection_indicator(edgy, wet, everywhere, everywhere)
assert r["status"] == "no_area_stands_out"
print("PASS  low values only on the edge -> ignored")

# 15. Too small to check -> insufficient evidence (never a guess).
r = inspection_indicator(np.full((4, 4), 0.7), np.full((4, 4), 0.2), np.ones((4, 4), bool), np.ones((4, 4), bool))
assert r["status"] == "insufficient_evidence"
print("PASS  tiny area -> inspection 'Insufficient evidence'")

# 16. Point-in-polygon: a unit square contains (0.5, 0.5) but not (1.5, 0.5).
square = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
assert points_in_polygon(np.array([0.5, 1.5]), np.array([0.5, 0.5]), square).tolist() == [True, False]
print("PASS  point-in-polygon: inside vs outside")

# 17. Excluding the west half of a 4x4 grid marks exactly the 2 left columns.
west_half = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 4], [0, 4], [0, 0]]]}
mask = excluded_pixel_mask([west_half], (0, 0, 4, 4), (4, 4))
assert mask[:, :2].all() and not mask[:, 2:].any()
print("PASS  excluded area covers exactly the right pixels")

# 18. The infield case: turf (NDVI 0.7) with a 3x3 dirt patch (NDVI 0.3) in a 12x12 field.
#     Before excluding the dirt -> flagged. After excluding it -> nothing stands out.
def field_bands():
    red = np.full((12, 12), 0.05)
    nir = np.full((12, 12), 0.05 * 0.85 / 0.15)  # NDVI 0.7
    nir[5:8, 5:8] = 0.05 * 1.3 / 0.7  # NDVI 0.3 (dirt)
    return {"B04": red, "B08": nir, "SCL": np.full((12, 12), 4), "dataMask": np.ones((12, 12))}

def inspect(bands):
    ndvi = compute_ndvi(bands["B04"], bands["B08"])
    valid = valid_pixel_mask(bands["SCL"], bands["dataMask"])
    return inspection_indicator(ndvi, wet, valid, np.asarray(bands["dataMask"]) > 0)

assert inspect(field_bands())["status"] == "may_warrant_inspection"
bands = field_bands()
infield = {"type": "Polygon", "coordinates": [[[5, 4], [8, 4], [8, 7], [5, 7], [5, 4]]]}  # box 0..12, rows 5-7
n = apply_exclusions(bands, [infield], (0, 0, 12, 12))
assert n == 9 and inspect(bands)["status"] == "no_area_stands_out"
print("PASS  dirt patch flagged -> excluded (9 px) -> 'No area stands out'")

# 19. The WHOLE field is evenly dry (NDVI 0.25, NDMI -0.1). Comparing the field with itself
#     finds nothing, but the healthy-turf baseline flags the whole field.
r = inspection_indicator(np.full((12, 12), 0.25), np.full((12, 12), -0.1), everywhere, everywhere)
assert r["low_pixels"] == 0  # the within-field check alone would have missed it
assert r["status"] == "may_warrant_inspection" and r["scope"] == "whole_field"
assert r["baseline"]["below_fraction"] == 1.0
print("PASS  evenly dry field -> 'Most of this field may warrant inspection'")

# 20. Mostly dry with a few green spots: the median is dry, so the green spots don't make the
#     dry part look "normal". The baseline still flags the whole field.
spotty = np.full((12, 12), 0.3)
spotty[2:5, 2:5] = 0.8
r = inspection_indicator(spotty, wet, everywhere, everywhere)
assert r["scope"] == "whole_field"
print("PASS  dry field with green spots -> still flagged as a whole-field problem")

# 21. Green (NDVI 0.7) but leaf moisture below the baseline everywhere -> flagged by NDMI.
r = inspection_indicator(field, np.full((12, 12), -0.05), everywhere, everywhere)
assert r["scope"] == "whole_field" and r["baseline"]["below_ndmi_fraction"] == 1.0
assert r["baseline"]["below_ndvi_fraction"] == 0.0
print("PASS  low NDMI alone -> flagged")

# 22. A 3x3 dry patch in healthy turf is 'some areas', not the whole field.
r = inspection_indicator(patchy, wet, everywhere, everywhere)
assert r["scope"] == "some_areas" and r["baseline"]["below_pixels"] == 9
print("PASS  small dry patch -> 'Some areas may warrant inspection'")

# 23. Outside May-October, warn that the baseline was measured on summer turf.
assert any("May-October" in w for w in quality_warnings(clear, 0, observation_month=3))
assert not any("May-October" in w for w in quality_warnings(clear, 0, observation_month=7))
print("PASS  winter/spring image -> season warning")

# 24. Color check: NGRDI = (green - red) / (green + red). More red than green -> below 0 (yellow).
assert abs(compute_ngrdi([0.08], [0.06])[0] - 0.1429) < 0.001  # green grass
assert compute_ngrdi([0.07], [0.08])[0] < 0  # yellow/tan: more red than green
print("PASS  NGRDI: green grass > 0, yellow grass < 0")

# 25. Green-looking field with a 3x3 yellow patch (NDVI still fine) -> 'some areas', yellow.
green = np.full((12, 12), 0.25)  # deep green (above the 0.15 cutoff)
yellow_patch = green.copy()
yellow_patch[5:8, 5:8] = -0.03
r = inspection_indicator(field, wet, everywhere, everywhere, yellow_patch)
assert r["scope"] == "some_areas" and r["color"]["yellow_pixels"] == 9
assert r["baseline"]["below_pixels"] == 0 and r["low_pixels"] == 0  # only the color check sees it
print("PASS  yellow patch (NDVI fine) -> 'Some areas', found by the color check")

# 26. The whole field looks yellow, even though NDVI/NDMI are fine -> whole-field problem.
r = inspection_indicator(field, wet, everywhere, everywhere, np.full((12, 12), -0.02))
assert r["scope"] == "whole_field" and r["color"]["yellow_fraction"] == 1.0
print("PASS  whole field yellow -> 'Most of this field may warrant inspection'")

# 26b. Pale green (NGRDI 0.10, like Gates North's pale spots) also counts: only deep green is good.
r = inspection_indicator(field, wet, everywhere, everywhere, np.full((12, 12), 0.10))
assert r["scope"] == "whole_field"
print("PASS  pale green (NGRDI 0.10) counts as yellow with the 0.15 cutoff")

# 27. Green everywhere on all checks -> no area stands out.
r = inspection_indicator(field, wet, everywhere, everywhere, green)
assert r["status"] == "no_area_stands_out" and r["color"]["yellow_pixels"] == 0
print("PASS  green on every check -> 'No area stands out'")

print("\nAll tests passed.")
