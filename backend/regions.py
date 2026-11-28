"""
regions.py - US turfgrass "grass regions" (added 2026-11-25, Version 2). ADD-ON ONLY: nothing in
the analysis math changes; results just get an extra "grass_region" label.

The 7 regions are a SIMPLIFIED project map with APPROXIMATE boundaries (see turf_regions.json,
"about" and "sources"). Only Region 3 (Northern & Central Plains, where our Denver-area fields
are) has a validated healthy-turf baseline and AI model. Everywhere else the app says
"not validated for this region yet"; the within-field check still works anywhere.

turf_regions.json here is an exact copy of frontend/src/turfRegions.json (the website uses the
same file to draw the map and detect the region). test_regions.py checks that they match.
Both are written by scripts/make_turf_regions.py.
"""

import json
import os

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "turf_regions.json")

with open(DATA_FILE, encoding="utf-8") as f:
    DATA = json.load(f)

REGIONS = {r["id"]: r for r in DATA["regions"]}
VALIDATED_REGION = DATA["validated_region"]


def point_in_ring(lon, lat, ring):
    """Ray casting: is (lon, lat) inside the polygon ring [[lon, lat], ...]?"""
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat):
            x_cross = x1 + (lat - y1) * (x2 - x1) / (y2 - y1)
            if lon < x_cross:
                inside = not inside
    return inside


def center_of(geometry):
    """The middle of a GeoJSON Polygon's bounding box: good enough to tell which region a field is in.
    Since 2026-11-27 also a MultiPolygon (a field in several pieces): the box around all pieces."""
    if geometry.get("type") == "MultiPolygon":
        ring = [p for part in geometry["coordinates"] for p in part[0]]
    else:
        ring = geometry["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return (min(lons) + max(lons)) / 2, (min(lats) + max(lats)) / 2


def detect(lon, lat):
    """The region id (1-7) for a location, or None outside the mapped area (48 states' box)."""
    for region_id, region in REGIONS.items():
        if point_in_ring(lon, lat, region["zone"]["coordinates"][0]):
            return region_id
    return None


def describe(region_id, how):
    """What the app says about a region. how = 'detected' or 'given' (sent by the website)."""
    region = REGIONS[region_id]
    validated = region_id == VALIDATED_REGION
    return {
        "id": region_id,
        "name": region["name"],
        "label": f"Region {region_id}: {region['name']}",
        "climate": region["climate"],
        "common_grasses": region["grasses"],
        "validated": validated,
        "status": "Validated (Denver-area fields)" if validated else "Not validated for this region yet",
        "note": DATA["validated_note"] if validated else DATA["not_validated_note"],
        "how": "detected from the field's location" if how == "detected" else "region sent by the website "
               "(detected from the field's location, or changed by the user)",
        "boundaries": "approximate (a simplified project map)",
    }


def resolve(region_id, geometry):
    """The grass region for a field: the website's region if it sent one, else detected from the
    field's location. None if the field is outside the mapped area."""
    if region_id is not None:
        return describe(region_id, "given")
    found = detect(*center_of(geometry))
    return describe(found, "detected") if found else None
