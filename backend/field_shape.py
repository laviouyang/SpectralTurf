"""
field_shape.py - A field can be SEVERAL separate pieces (added 2026-11-27, student request).

Why: many parks have several grass fields with walkways between them. Excluding every walkway
was very inconvenient, so the user can now draw several shapes, and they are saved and analyzed
as ONE field.

How it is stored: standard GeoJSON.
  - one piece  -> {"type": "Polygon", "coordinates": [ring]}            (exactly as before)
  - 2+ pieces  -> {"type": "MultiPolygon", "coordinates": [[ring], [ring], ...]}
Sentinel Hub's Process and Statistical APIs accept both types, so the satellite math is the same:
pixels inside ANY piece are measured, pixels in between (walkways) are not.

Rules (project choices):
  - at most MAX_FIELD_PARTS pieces;
  - each piece is checked exactly like a single outline (clean_polygon in main.py);
  - pieces may touch but must not overlap (the website merges overlapping shapes first).
"""

MAX_FIELD_PARTS = 20


def outer_rings(geometry):
    """The outline ring of every piece: [ring] for a Polygon, [ring, ring, ...] for a MultiPolygon."""
    if geometry["type"] == "MultiPolygon":
        return [part[0] for part in geometry["coordinates"]]
    return [geometry["coordinates"][0]]


def all_points(geometry):
    return [point for ring in outer_rings(geometry) for point in ring]


def bbox(geometry):
    """The smallest box (west, south, east, north) around all pieces."""
    points = all_points(geometry)
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    return min(lons), min(lats), max(lons), max(lats)


def box_center(geometry):
    """The middle of the box around all pieces (used to find the grass region)."""
    west, south, east, north = bbox(geometry)
    return (west + east) / 2, (south + north) / 2


# ---- overlap check (no extra libraries: plain geometry) ----

def _side(p, q, r):
    return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])


def _segments_cross(a, b, c, d):
    """True if segment a-b properly crosses segment c-d (touching ends or edges does not count)."""
    return _side(a, b, c) * _side(a, b, d) < 0 and _side(c, d, a) * _side(c, d, b) < 0


def _on_segment(p, a, b, tolerance=1e-12):
    if abs(_side(a, b, p)) > tolerance:
        return False
    return min(a[0], b[0]) - tolerance <= p[0] <= max(a[0], b[0]) + tolerance and \
        min(a[1], b[1]) - tolerance <= p[1] <= max(a[1], b[1]) + tolerance


def _strictly_inside(point, ring):
    """Inside the ring and not on its edge (ray casting)."""
    if any(_on_segment(point, a, b) for a, b in zip(ring, ring[1:])):
        return False
    lon, lat = point
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        if (y1 > lat) != (y2 > lat):
            if lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def _probe_points(ring):
    """Corners plus the middle of every edge: enough to notice one piece lying on top of another."""
    corners = ring[:-1]
    middles = [[(a[0] + b[0]) / 2, (a[1] + b[1]) / 2] for a, b in zip(ring, ring[1:])]
    return corners + middles


def rings_overlap(r1, r2):
    """True if two outlines share some area (only touching along an edge or corner is allowed)."""
    if any(_segments_cross(a, b, c, d) for a, b in zip(r1, r1[1:]) for c, d in zip(r2, r2[1:])):
        return True
    if any(_strictly_inside(p, r2) for p in _probe_points(r1)):
        return True
    if any(_strictly_inside(p, r1) for p in _probe_points(r2)):
        return True
    # Exactly the same shape twice: every corner of one lies on the other's edge.
    return sorted(map(tuple, r1[:-1])) == sorted(map(tuple, r2[:-1]))


def clean_field(geometry, clean_polygon, bad):
    """Check a field outline sent by the browser and return a clean copy.

    clean_polygon: main.clean_polygon (checks ONE outline, raises a 400 error if it is bad).
    bad(reason):   raises a 400 error with "Invalid area: <reason>".
    A Polygon goes through clean_polygon exactly as before this change.
    """
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        bad("it must be a GeoJSON Polygon or MultiPolygon.")
    if geometry["type"] == "Polygon":
        return clean_polygon(geometry)

    parts = geometry.get("coordinates")
    if not isinstance(parts, list) or not parts:
        bad("a MultiPolygon needs at least one piece.")
    if len(parts) > MAX_FIELD_PARTS:
        bad(f"a field can have at most {MAX_FIELD_PARTS} separate pieces.")
    cleaned = [clean_polygon({"type": "Polygon", "coordinates": part})["coordinates"] for part in parts]
    if len(cleaned) == 1:  # one piece is simply a Polygon
        return {"type": "Polygon", "coordinates": cleaned[0]}
    rings = [part[0] for part in cleaned]
    for i, r1 in enumerate(rings):
        for r2 in rings[i + 1:]:
            if rings_overlap(r1, r2):
                bad("the pieces of a field must not overlap.")
    return {"type": "MultiPolygon", "coordinates": cleaned}
