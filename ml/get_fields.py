"""
get_fields.py - Stage 10, Step 1: collect real grass-field outlines for training the AI.

The AI should work on ANY grass field people draw in the app, so it learns from a mix:
  - "sports":   sports fields (soccer, football, multi-use, untagged pitches)
  - "baseball": baseball/softball fields (grass outfield + dirt infield, as people draw them)
  - "park":     park lawns (grass areas inside parks; some watered, some not)

Where the outlines come from: OpenStreetMap (OSM), a free map that volunteers draw.
Sports fields are tagged leisure=pitch; park lawns are tagged landuse=grass inside a
leisure=park. We ask OSM's Overpass API for each kind ONCE, save the answers to disk,
and pick fields from those saved copies.

Which fields we keep (all project choices, not standards):
  - closed outlines only (a polygon, not a line)
  - grass only: drop anything tagged artificial turf, dirt, asphalt, etc., sports that are
    almost never on grass (tennis, basketball, ...), and areas that aren't really fields
    (golf greens, shooting ranges, model airfields)
  - between MIN_AREA_M2 (8,000 m², about 2 acres: many 10 m pixels) and MAX_AREA_M2
    (100,000 m²: keeps satellite processing cost reasonable)
  - an average width of at least 30 m (MIN_AVERAGE_WIDTH_M): no thin strips
  - inside the Denver box, and at least MIN_SPACING_M (1 km) apart, so we don't pick
    several fields from one park or sports complex
    (side-by-side fields share watering and soil, which would make testing on
    "fields the model never saw" too easy later)
  - a fixed number of each kind (FIELDS_PER_KIND), picked at random with a fixed seed,
    so every run picks the same ones
Artificial turf that isn't tagged can't be spotted here; Step 2 drops fields whose NDVI
never rises above 0.3 during the season (real grass greens up at least in spring).

Field outlines: © OpenStreetMap contributors (ODbL license).

Run from the project folder (backend venv active):
    python ml/get_fields.py
To download again, delete the files in ml/data/cache/ first.
"""

import json
import math
import random
import sys
import time
from datetime import date
from pathlib import Path

import requests

ML_DIR = Path(__file__).resolve().parent
CACHE_DIR = ML_DIR / "data" / "cache"
OUTPUT_FILE = ML_DIR / "data" / "fields.geojson"

# Denver metro area: south, west, north, east (latitude/longitude).
DENVER_BOX = (39.55, -105.15, 39.95, -104.70)

FIELDS_PER_KIND = {"sports": 10, "baseball": 5, "park": 10}  # chosen by Lavi, 2026-11-01
MIN_AREA_M2 = 8_000
MAX_AREA_M2 = 100_000
# Average width = 2 x area / perimeter. A long, thin strip (like a greenway between houses)
# is mostly edge pixels mixed with roofs and roads. 30 m = 3 satellite pixels; a normal
# soccer field is about 50 m by this measure. A project choice.
MIN_AVERAGE_WIDTH_M = 30
MIN_SPACING_M = 1_000  # 300 m still let 3 fields of one soccer complex in
RANDOM_SEED = 2026

# Surface tags that are definitely NOT natural grass.
NOT_GRASS_SURFACES = {
    "artificial_turf", "artificial", "artificial_grass", "astroturf", "synthetic",
    "synthetic_turf", "acrylic", "tartan", "rubber", "asphalt", "concrete", "paved",
    "clay", "dirt", "sand", "gravel", "fine_gravel", "ground", "compacted", "earth",
    "wood", "ice",
}
# Sports that are almost never played on grass, even when the surface isn't tagged.
NOT_GRASS_SPORTS = {
    "tennis", "basketball", "skateboard", "running", "athletics", "volleyball",
    "beachvolleyball", "pickleball", "padel", "handball", "equestrian", "shooting",
    "bmx", "racquet", "netball", "bowls", "boules", "table_tennis", "ice_hockey",
    "roller_skating", "motocross", "karting", "skating",
}
# Grass, but not the kind of field this app is for (managed very differently).
NOT_A_FIELD_SPORTS = {"golf", "shooting_range", "model_aerodrome", "disc_golf", "miniature_golf"}
BASEBALL_SPORTS = {"baseball", "softball"}

# Visual review (2026-11-01): the picked fields were checked on the Esri satellite photo, and
# these were removed because the tags didn't show the problem. Anything unclear from a photo
# is left in; Step 2 drops fields whose NDVI never rises above 0.3 (likely artificial turf).
VISUAL_REVIEW_EXCLUDE = {
    "osm_way_1288554701": "looks like artificial turf (stadium, uniform color, painted markings)",
    "osm_way_337232573": "looks like artificial turf (uniform color, painted markings)",
    "osm_way_547800355": "looks like artificial turf (stadium, pale gray-white surface)",
    "osm_way_484156819": "mostly bare ground and a path, not a lawn",
    "osm_way_447273314": "bare dirt lot with a building, not a lawn",
    "osm_way_45004469": "creek corridor between houses, not a field",
    "osm_way_224311074": "golf-course fairway with sand traps (not tagged as golf)",
    "osm_way_556551903": "outline includes school buildings and parking",
    "osm_way_484156737": "mostly bare dry ground, not a lawn",
}

SOUTH, WEST, NORTH, EAST = DENVER_BOX
BOX = f"{SOUTH},{WEST},{NORTH},{EAST}"
QUERIES = {
    # Every sports field in the box.
    "pitches": f"""
        [out:json][timeout:180];
        way["leisure"="pitch"]({BOX});
        out tags geom;
    """,
    # Grass areas that lie inside a park: first find the parks, then the grass inside them.
    "park_grass": f"""
        [out:json][timeout:180];
        (way["leisure"="park"]({BOX}); relation["leisure"="park"]({BOX});)->.parks;
        .parks map_to_area -> .park_areas;
        way["landuse"="grass"](area.park_areas);
        out tags geom;
    """,
}

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",  # a public mirror, tried only if the first fails
]
HEADERS = {"User-Agent": "SpectralTurf student project (field outlines for a school AI project)"}
# When a server says it's busy, wait this many seconds before each retry (Overpass asks
# clients to wait longer each time instead of retrying right away).
RETRY_WAITS = [30, 90]


def cache_file(name):
    # "pitches" keeps its original file name, so the first download is reused.
    return CACHE_DIR / ("overpass_pitches.json" if name == "pitches" else f"overpass_{name}.json")


def download(name):
    """Run one Overpass query, or reuse its saved answer. Never downloads what is cached."""
    path = cache_file(name)
    if path.exists():
        print(f"Using cached OpenStreetMap data: {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    data = None
    attempts = [(url, 0) for url in OVERPASS_URLS] + [(OVERPASS_URLS[0], wait) for wait in RETRY_WAITS]
    for url, wait in attempts:
        if wait:
            print(f"  Waiting {wait} s before trying again (the server asked clients to back off)...")
            time.sleep(wait)
        print(f"Downloading '{name}' from OpenStreetMap ({url}) ... this can take a minute or two.")
        try:
            response = requests.post(url, data={"data": QUERIES[name]}, headers=HEADERS, timeout=240)
            response.raise_for_status()
            data = response.json()
            break
        except requests.HTTPError as e:
            busy = " (server busy)" if e.response.status_code in (429, 502, 503, 504) else ""
            print(f"  That didn't work (HTTP {e.response.status_code}{busy}).")
        except (requests.RequestException, ValueError) as e:
            print(f"  That didn't work ({type(e).__name__}).")
    if data is None:
        sys.exit(f"Could not download '{name}' from Overpass. Nothing was saved.\n"
                 "If Cloudflare WARP is on, switch it off for this one download, then back on.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    print(f"  Saved {len(data.get('elements', []))} outlines to {path.name}")
    return data


def to_meters(points):
    """Turn [lon, lat] corners into x/y meters around the shape's middle.
    Accurate enough for field-sized shapes (same idea as the app's cos(latitude) correction)."""
    lat0 = sum(lat for _, lat in points) / len(points)
    lon0 = sum(lon for lon, _ in points) / len(points)
    m_per_deg_lat = 111_320
    m_per_deg_lon = 111_320 * math.cos(math.radians(lat0))
    xy = [((lon - lon0) * m_per_deg_lon, (lat - lat0) * m_per_deg_lat) for lon, lat in points]
    return xy, lon0, lat0, m_per_deg_lon, m_per_deg_lat


def area_and_centroid(points):
    """Area (m²) and middle point (lon, lat) of a closed outline, with the shoelace formula."""
    xy, lon0, lat0, m_lon, m_lat = to_meters(points)
    twice_area, cx, cy = 0.0, 0.0, 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if twice_area == 0:
        return 0.0, (lon0, lat0)
    cx /= 3 * twice_area
    cy /= 3 * twice_area
    return abs(twice_area) / 2, (lon0 + cx / m_lon, lat0 + cy / m_lat)


def perimeter_m(points):
    xy = to_meters(points)[0]
    return sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(xy, xy[1:]))


def distance_m(a, b):
    """Distance in meters between two (lon, lat) points (fine at city scale)."""
    m_lon = 111_320 * math.cos(math.radians((a[1] + b[1]) / 2))
    return math.hypot((a[0] - b[0]) * m_lon, (a[1] - b[1]) * 111_320)


def describe(element, source="pitches"):
    """Turn one Overpass result into a field dict, or return (None, reason) if we skip it."""
    tags = element.get("tags", {})
    geometry = element.get("geometry") or []
    points = [(p["lon"], p["lat"]) for p in geometry]
    if len(points) < 4 or points[0] != points[-1]:
        return None, "not a closed outline"
    if f"osm_way_{element['id']}" in VISUAL_REVIEW_EXCLUDE:
        return None, "removed after visual review (see VISUAL_REVIEW_EXCLUDE)"
    surface = tags.get("surface", "").lower()
    sports = {s.strip().lower() for s in tags.get("sport", "").split(";") if s.strip()}
    if surface in NOT_GRASS_SURFACES:
        return None, "not grass (surface tag)"
    if sports and sports <= NOT_GRASS_SPORTS:
        return None, "not grass (sport is never on grass)"
    if sports & NOT_A_FIELD_SPORTS or tags.get("golf"):
        return None, "not a field (golf, shooting range, model airfield)"
    area, centroid = area_and_centroid(points)
    if not (WEST <= centroid[0] <= EAST and SOUTH <= centroid[1] <= NORTH):
        return None, "outside the Denver box"  # the park search can return far-away parks
    if area < MIN_AREA_M2:
        return None, "smaller than 8,000 m²"
    if area > MAX_AREA_M2:
        return None, "larger than 100,000 m²"
    if 2 * area / perimeter_m(points) < MIN_AVERAGE_WIDTH_M:
        return None, "a thin strip (average width under 30 m)"

    if source == "park_grass":
        kind = "park"
    elif sports & BASEBALL_SPORTS:
        kind = "baseball"
    else:
        kind = "sports"
    return {
        "id": f"osm_way_{element['id']}",
        "osm_id": element["id"],
        "kind": kind,
        "name": tags.get("name", ""),
        "sport": tags.get("sport", ""),
        "surface": surface or "(not tagged)",
        "area_m2": round(area),
        "centroid": [round(centroid[0], 6), round(centroid[1], 6)],
        "polygon": [[round(lon, 7), round(lat, 7)] for lon, lat in points],
    }, None


def choose(candidates, per_kind=None, spacing=MIN_SPACING_M, seed=RANDOM_SEED):
    """Random but repeatable pick: go through the fields in a shuffled order and take one if
    its kind still needs fields and it isn't too close to a field already picked."""
    per_kind = per_kind or FIELDS_PER_KIND
    order = sorted(candidates, key=lambda f: f["osm_id"])  # same start order every run
    random.Random(seed).shuffle(order)
    picked = []
    for field in order:
        if sum(p["kind"] == field["kind"] for p in picked) >= per_kind.get(field["kind"], 0):
            continue
        if all(distance_m(field["centroid"], p["centroid"]) >= spacing for p in picked):
            picked.append(field)
    kinds = list(per_kind)
    return sorted(picked, key=lambda f: kinds.index(f["kind"]))


def to_geojson(fields):
    return {
        "type": "FeatureCollection",
        "attribution": "Field outlines © OpenStreetMap contributors (ODbL)",
        "created": date.today().isoformat(),
        "rules": {"fields_per_kind": FIELDS_PER_KIND, "min_area_m2": MIN_AREA_M2,
                  "min_average_width_m": MIN_AVERAGE_WIDTH_M,
                  "visual_review_exclude": VISUAL_REVIEW_EXCLUDE,
                  "max_area_m2": MAX_AREA_M2, "min_spacing_m": MIN_SPACING_M,
                  "random_seed": RANDOM_SEED, "box_south_west_north_east": DENVER_BOX},
        "features": [
            {
                "type": "Feature",
                "properties": {k: v for k, v in f.items() if k != "polygon"},
                "geometry": {"type": "Polygon", "coordinates": [f["polygon"]]},
            }
            for f in fields
        ],
    }


def main():
    candidates, seen = [], set()
    for source in QUERIES:
        elements = download(source).get("elements", [])
        skipped = {}
        for element in elements:
            if element["id"] in seen:
                continue  # the same outline can't be counted twice
            seen.add(element["id"])
            field, reason = describe(element, source)
            if field:
                candidates.append(field)
            else:
                skipped[reason] = skipped.get(reason, 0) + 1
        print(f"\n{source}: {len(elements)} outlines downloaded")
        for reason, count in sorted(skipped.items(), key=lambda kv: -kv[1]):
            print(f"  skipped {count:>5}: {reason}")

    print("\nUsable fields by kind:")
    for kind in FIELDS_PER_KIND:
        print(f"  {kind:<9}{sum(f['kind'] == kind for f in candidates):>5}")

    fields = choose(candidates)
    for kind, wanted in FIELDS_PER_KIND.items():
        got = sum(f["kind"] == kind for f in fields)
        if got < wanted:
            print(f"Note: only {got} '{kind}' fields meet the rules (wanted {wanted}).")

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(to_geojson(fields), indent=1), encoding="utf-8")

    print(f"\nPicked {len(fields)} fields (at least {MIN_SPACING_M} m apart, seed {RANDOM_SEED}):\n")
    print(f"{'#':>3}  {'kind':<9}{'id':<20}{'name':<26}{'sport':<16}{'surface':<14}{'area m²':>9}  centroid")
    print("-" * 118)
    for i, f in enumerate(fields, 1):
        print(f"{i:>3}  {f['kind']:<9}{f['id']:<20}{(f['name'] or '-')[:25]:<26}{(f['sport'] or '-')[:15]:<16}"
              f"{f['surface'][:13]:<14}{f['area_m2']:>9,}  {f['centroid'][1]:.5f}, {f['centroid'][0]:.5f}")
    print(f"\nSaved {OUTPUT_FILE}")
    print("Field outlines © OpenStreetMap contributors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
