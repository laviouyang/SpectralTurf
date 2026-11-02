"""
test_get_fields.py - Offline checks for ml/get_fields.py (no internet).

Uses a few MADE-UP outlines in the same format Overpass returns. They are test inputs only:
they are never saved as fields and never used for training.

Run from the project folder:   python ml/test_get_fields.py
"""

import get_fields

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def rectangle(osm_id, west, south, width_m, height_m, **tags):
    """A made-up rectangular outline, width x height meters, in Overpass's format."""
    d_lat = height_m / 111_320
    d_lon = width_m / (111_320 * get_fields.math.cos(get_fields.math.radians(south)))
    corners = [(west, south), (west + d_lon, south), (west + d_lon, south + d_lat),
               (west, south + d_lat), (west, south)]
    return {"type": "way", "id": osm_id, "tags": {"leisure": "pitch", **tags},
            "geometry": [{"lon": lon, "lat": lat} for lon, lat in corners]}


# 1-2: geometry math on a 100 m x 100 m square (10,000 m²).
square = rectangle(1, -104.9, 39.7, 100, 100)
points = [(p["lon"], p["lat"]) for p in square["geometry"]]
area, (cx, cy) = get_fields.area_and_centroid(points)
check("1. a 100 m x 100 m square measures about 10,000 m²", abs(area - 10_000) < 50)
check("2. its centroid is its middle (about 50 m in from each side)",
      abs(get_fields.distance_m((cx, cy), (-104.9, 39.7)) - 70.7) < 1)

# 3-9: which outlines are kept.
field, reason = get_fields.describe(rectangle(2, -104.9, 39.7, 110, 80, sport="soccer", surface="grass"))
check("3. a grass soccer field of 8,800 m² is kept", field is not None and field["area_m2"] > 8000)
check("4. kept fields have an id, sport, area, centroid and a closed polygon",
      field["id"] == "osm_way_2" and field["sport"] == "soccer"
      and field["polygon"][0] == field["polygon"][-1] and len(field["centroid"]) == 2)
field, reason = get_fields.describe(rectangle(3, -104.9, 39.7, 110, 80, surface="artificial_turf"))
check("5. artificial turf is dropped", field is None and "surface" in reason)
field, reason = get_fields.describe(rectangle(4, -104.9, 39.7, 60, 60, surface="grass"))
check("6. a field under 8,000 m² is dropped", field is None and "8,000" in reason)
field, reason = get_fields.describe(rectangle(5, -104.9, 39.7, 110, 80, sport="tennis"))
check("7. tennis courts are dropped even without a surface tag", field is None)
field, reason = get_fields.describe(rectangle(6, -104.9, 39.7, 110, 80, sport="soccer;tennis"))
check("8. a field shared by soccer and tennis is kept (soccer is usually on grass)", field is not None)
open_line = rectangle(7, -104.9, 39.7, 110, 80)
open_line["geometry"] = open_line["geometry"][:-1]
check("9. an outline that isn't closed is dropped", get_fields.describe(open_line)[0] is None)

# 10-14: kinds, golf, and size limits.
field, _ = get_fields.describe(rectangle(8, -104.9, 39.7, 120, 90, sport="baseball"))
check("10. a baseball field is kept as kind 'baseball'", field is not None and field["kind"] == "baseball")
field, _ = get_fields.describe(rectangle(9, -104.9, 39.7, 120, 90, landuse="grass"), source="park_grass")
check("11. park grass is kept as kind 'park'", field is not None and field["kind"] == "park")
field, reason = get_fields.describe(rectangle(10, -104.9, 39.7, 200, 150, sport="golf"))
check("12. golf greens are dropped", field is None and "golf" in reason)
field, reason = get_fields.describe(rectangle(11, -104.9, 39.7, 400, 300), source="park_grass")
check("13. an area over 100,000 m² is dropped", field is None and "100,000" in reason)
strip = rectangle(14, -104.9, 39.7, 500, 20, landuse="grass")  # 10,000 m² but only 20 m wide
check("14c. a thin 20 m strip is dropped even though it is big enough",
      get_fields.describe(strip, source="park_grass")[1].startswith("a thin strip"))
far_away = rectangle(13, 5.04, 50.71, 150, 100, landuse="grass")  # in Belgium
check("14b. outlines outside the Denver box are dropped",
      get_fields.describe(far_away, source="park_grass")[1] == "outside the Denver box")
check("14. a soccer field is kind 'sports'", get_fields.describe(
    rectangle(12, -104.9, 39.7, 120, 90, sport="soccer"))[0]["kind"] == "sports")

# 15-18: choosing the 10 / 5 / 10 mix.
def grid(first_id, kind_tags, source, row):
    return [get_fields.describe(rectangle(first_id + i, -105.1 + 0.02 * i, 39.6 + 0.02 * row,
                                          120, 90, **kind_tags), source)[0] for i in range(20)]


candidates = (grid(100, {"sport": "soccer"}, "pitches", 0) + grid(200, {"sport": "baseball"}, "pitches", 1)
              + grid(300, {"landuse": "grass"}, "park_grass", 2))
neighbor = get_fields.describe(rectangle(999, -105.1 + 0.003, 39.6, 120, 90, sport="soccer"))[0]
picked = get_fields.choose(candidates + [neighbor])
counts = {kind: sum(f["kind"] == kind for f in picked) for kind in get_fields.FIELDS_PER_KIND}
check("15. picks exactly 10 sports, 5 baseball, 10 park", counts == {"sports": 10, "baseball": 5, "park": 10})
check("16. no two picked fields are closer than 1 km (one per park or complex)",
      all(get_fields.distance_m(a["centroid"], b["centroid"]) >= get_fields.MIN_SPACING_M
          for i, a in enumerate(picked) for b in picked[i + 1:]))
check("17. the same fields are picked every run (fixed seed)",
      [f["id"] for f in picked] == [f["id"] for f in get_fields.choose(candidates + [neighbor])])

geojson = get_fields.to_geojson(picked)
check("18. output is GeoJSON with the OpenStreetMap credit, one feature per field, and its kind",
      geojson["type"] == "FeatureCollection" and "OpenStreetMap" in geojson["attribution"]
      and len(geojson["features"]) == 25 and geojson["features"][0]["properties"]["kind"] == "sports"
      and geojson["features"][0]["geometry"]["type"] == "Polygon")

print(f"\nAll {passed} get_fields tests passed.")
