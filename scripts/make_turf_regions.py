"""make_turf_regions.py - writes the SpectralTurf grass-region data (added 2026-11-25).

Run from the project folder:   python scripts/make_turf_regions.py .
Writes frontend/src/turfRegions.json and backend/turf_regions.json (identical content).
The region zones are simplified and drawn by hand (approximate); their layout follows the
"Grass Types USA" map by Simple Lawn Solutions (a visual reference only). The US state shapes
for the picture come from US Census data (scripts/make_us_map.mjs).
"""
import json
import sys

root = sys.argv[1]

# Region zones: simple polygons that share their borders and together cover the box
# 126-66 W, 24-50 N. A field's region = the zone it is in. The LAYOUT follows the
# "Grass Types USA" map by Simple Lawn Solutions (used only as a visual reference; redrawn
# here by hand, approximate). Revised 2026-11-25 at the student's request.
W, E, N, S = -126.0, -66.0, 50.0, 24.0
L12 = [[-121.0, 49.0], [-121.5, 46.0], [-121.8, 44.0], [-122.3, 42.0]]          # Cascades
L23 = [[-111.5, 49.0], [-110.0, 46.5], [-107.5, 44.5], [-106.5, 42.0],           # Rockies front
       [-105.6, 40.5], [-105.4, 39.0], [-105.6, 37.5]]
L25 = [[-122.3, 42.0], [-122.5, 40.5], [-120.5, 39.3], [-118.0, 37.6], [-115.5, 36.8],
       [-114.0, 37.0], [-109.0, 37.0], [-106.5, 37.0], [-105.6, 37.5]]
L34 = [[-98.0, 49.0], [-97.5, 46.0], [-96.5, 43.0], [-95.8, 41.5], [-95.3, 40.0]]
L36 = [[-95.3, 40.0], [-96.0, 38.6], [-100.0, 38.2], [-103.0, 37.6], [-105.0, 37.0]]
L46 = [[-95.3, 40.0], [-90.0, 40.2], [-85.0, 40.2], [-80.0, 40.3], [-75.5, 40.4], [-74.0, 40.45], [E, 40.45]]
L56 = [[-105.0, 37.0], [-104.5, 36.0], [-102.0, 35.6], [-100.0, 35.3]]
L67 = [[-100.0, 35.3], [-97.0, 35.4], [-94.0, 35.6], [-90.0, 35.8], [-86.0, 35.6], [-83.0, 35.7],
       [-80.0, 36.3], [-75.9, 36.6], [E, 36.6]]
L57 = [[-100.0, 35.3], [-99.5, 33.0], [-100.0, 30.5], [-100.3, 28.3], [-99.5, S]]


def ring(points):
    return points + [points[0]]


ZONES = {
    1: [[W, N], [-121.0, N]] + L12 + [[W, 42.0]],
    2: [[-121.0, N], [-111.5, N]] + L23 + L25[::-1] + L12[::-1][1:],
    3: [[-111.5, N], [-98.0, N]] + L34 + L36[1:] + [[-105.6, 37.5]] + L23[::-1][1:],
    4: [[-98.0, N], [E, N]] + L46[::-1] + L34[::-1][1:],
    5: [[W, 42.0]] + L25 + [[-105.0, 37.0]] + L56[1:] + L57[1:] + [[W, S]],
    6: L46 + L67[::-1][:-1] + L56[::-1][:-1] + L36[::-1][:-1],
    7: L67 + [[E, S]] + L57[::-1][:-1],
}

SOURCES = {
    "layout": {"name": "Region layout adapted from the \"Grass Types USA\" map by Simple Lawn Solutions "
                       "(a lawn-care company; used as a visual reference only)",
               "url": None},
    "states": {"name": "State shapes: U.S. Census Bureau cartographic boundaries, via the us-atlas project",
               "url": "https://github.com/topojson/us-atlas"},
    "framework": [
        {"name": "University of Maryland Extension: Lawn Grasses Grown in Maryland (map of cool-season, transition and warm-season zones)",
         "url": "https://extension.umd.edu/resource/lawn-grasses-grown-maryland"},
        {"name": "Kansas State University Turf: map of the approximate boundaries of the turfgrass transition zone (July 2026)",
         "url": "https://www.k-state.edu/news/turf/articles/2026/07/summer-turf-wars-battling-drought-heat-and-seasonal-pests-part-one-dought-and-heat-stress.html"},
    ],
    "OSU": {"name": "Oregon State University Extension: Practical Lawn Care for Western Oregon (EC 1521)",
            "url": "https://extension.oregonstate.edu/catalog/pub/ec-1521-practical-lawn-care-western-oregon"},
    "USU": {"name": "Utah State University Extension: Turfgrass Cultivars for Utah",
            "url": "https://extension.usu.edu/yardandgarden/research/turfgrass-cultivars-for-utah.php"},
    "CSU": {"name": "Colorado State University Extension: Turfgrass Species Selection Guidelines",
            "url": "https://extension.colostate.edu/resource/turfgrass-species-selection-guidelines"},
    "UMN": {"name": "University of Minnesota Extension: Buying turfgrass seed for Minnesota lawns",
            "url": "https://extension.umn.edu/lawn-care/buying-turfgrass-seed-minnesota-lawns"},
    "UA": {"name": "University of Arizona Extension: Turfgrass Maintenance Guide for Lawns in the Low Elevation Arizona Desert",
           "url": "https://extension.arizona.edu/publication/turfgrass-maintenance-guide-residential-and-commercial-lawns-low-elevation-Arizona"},
    "NCSU": {"name": "NC State Extension TurfFiles: Turfgrasses",
             "url": "https://www.turffiles.ncsu.edu/grasses"},
    "UF": {"name": "University of Florida IFAS Extension: Selecting a Turfgrass for Florida Lawns (LH005)",
           "url": "https://edis.ifas.ufl.edu/publication/LH005"},
}

REGIONS = [
    {"id": 1, "name": "Pacific Northwest coast", "short": "Pacific NW", "climate": "cool and wet",
     "grasses": ["perennial ryegrass", "fine fescues", "Kentucky bluegrass", "bentgrass", "tall fescue"],
     "source": "OSU", "label": [-123.0, 46.3]},
    {"id": 2, "name": "Intermountain West", "short": "Intermountain", "climate": "cool and dry",
     "grasses": ["Kentucky bluegrass", "tall fescue", "fine fescues", "perennial ryegrass", "wheatgrass"],
     "source": "USU", "label": [-115.5, 42.3]},
    {"id": 3, "name": "Northern & Central Plains", "short": "Plains (Denver)", "climate": "cool, semi-dry",
     "grasses": ["Kentucky bluegrass", "tall fescue", "buffalograss", "blue grama", "fine fescues",
                 "perennial ryegrass"],
     "source": "CSU", "label": [-101.5, 44.3]},
    {"id": 4, "name": "Upper Midwest & Northeast", "short": "Midwest & NE", "climate": "cool and humid",
     "grasses": ["Kentucky bluegrass", "fine fescues", "perennial ryegrass", "tall fescue"],
     "source": "UMN", "label": [-89.8, 44.6]},
    {"id": 5, "name": "Southwest", "short": "Southwest", "climate": "warm and dry",
     "grasses": ["bermudagrass", "zoysiagrass", "St. Augustinegrass", "buffalograss (cooler, higher areas)"],
     "source": "UA", "label": [-111.5, 34.2]},
    {"id": 6, "name": "Transition zone", "short": "Transition", "climate": "hot summers, cold winters",
     "grasses": ["tall fescue", "Kentucky bluegrass", "perennial ryegrass", "zoysiagrass", "bermudagrass"],
     "source": "NCSU", "label": [-89.0, 37.9]},
    {"id": 7, "name": "Southeast & Gulf Coast", "short": "Southeast & Gulf", "climate": "warm and humid",
     "grasses": ["St. Augustinegrass", "bahiagrass", "centipedegrass", "zoysiagrass", "bermudagrass"],
     "source": "UF", "label": [-86.6, 32.4]},
]

data = {
    "about": ("SpectralTurf grass regions (made 2026-11-25). A SIMPLIFIED project map: boundaries are "
              "approximate, redrawn by hand following the layout of the 'Grass Types USA' map by Simple "
              "Lawn Solutions (a visual reference, not a scientific source), within the cool-season / "
              "transition / warm-season framework in the 'framework' sources; each region's grass list comes from that region's "
              "own university extension source. Not an official USDA map. Only Region 3 (Denver-area "
              "fields) has a validated healthy-turf baseline and AI model."),
    "validated_region": 3,
    "validated_note": ("Validated with Denver-area fields only: the healthy-turf baseline, color cutoff "
                       "and AI model were made from Denver-area fields."),
    "not_validated_note": ("Not validated for this region yet. The healthy-turf baseline (NDVI 0.5, NDMI 0), "
                           "the color cutoff (NGRDI 0.15) and the AI model were made from Denver-area fields, "
                           "so their results here may not be accurate. The within-field check (comparing "
                           "the field with itself) still works anywhere."),
    "sources": SOURCES,
    "regions": [{**r, "validated": r["id"] == 3,
                 "zone": {"type": "Polygon", "coordinates": [ring(ZONES[r["id"]])]}} for r in REGIONS],
}

text = json.dumps(data, indent=1) + "\n"
for path in (root + "/frontend/src/turfRegions.json", root + "/backend/turf_regions.json"):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
print("written", len(text), "bytes")
