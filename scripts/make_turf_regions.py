"""make_turf_regions.py - writes the SpectralTurf grass-region data (added 2026-11-25).

Run from the project folder:   python scripts/make_turf_regions.py .
Writes frontend/src/turfRegions.json and backend/turf_regions.json (identical content).
The outline and region zones are simplified and drawn by hand for this project (approximate).
"""
import json
import sys

root = sys.argv[1]

# Simplified outline of the 48 states (lon, lat), drawn by hand for this project. Great Lakes are
# left out (shoreline); small bays and islands are skipped. Only for the picture.
US_OUTLINE = [
    [-124.72, 48.38], [-123.1, 48.15], [-122.75, 49.0], [-95.15, 49.0], [-95.15, 49.38], [-94.8, 49.32],
    [-94.6, 48.72], [-93.2, 48.6], [-92.0, 48.35], [-90.0, 48.1], [-89.6, 47.95], [-92.1, 46.75],
    [-90.4, 46.6], [-88.4, 47.4], [-88.0, 47.45], [-87.6, 46.5], [-86.0, 46.67], [-84.6, 46.45],
    [-84.7, 45.85], [-85.6, 45.95], [-87.6, 45.1], [-87.9, 44.5], [-87.5, 43.5], [-87.8, 42.5],
    [-87.6, 41.8], [-87.0, 41.6], [-86.5, 42.1], [-86.2, 43.0], [-86.5, 44.3], [-85.6, 45.0],
    [-84.7, 45.75], [-83.4, 45.0], [-83.3, 44.3], [-83.9, 43.9], [-82.5, 43.6], [-82.4, 43.0],
    [-83.0, 42.3], [-83.4, 41.7], [-82.7, 41.45], [-81.7, 41.5], [-80.1, 42.15], [-79.0, 42.75],
    [-79.05, 43.25], [-77.6, 43.25], [-76.2, 43.5], [-76.3, 44.1], [-75.3, 44.85], [-74.75, 45.0],
    [-71.5, 45.0], [-71.1, 45.3], [-70.25, 45.95], [-70.0, 46.7], [-69.25, 47.45], [-68.25, 47.35],
    [-67.8, 47.05], [-67.8, 45.7], [-67.0, 44.9], [-68.8, 44.3], [-70.2, 43.6], [-70.8, 42.9],
    [-71.0, 42.3], [-70.0, 42.05], [-69.95, 41.65], [-70.6, 41.55], [-71.4, 41.45], [-72.9, 41.25],
    [-73.9, 40.85], [-74.0, 40.45], [-74.1, 39.75], [-74.95, 38.93], [-75.05, 38.45], [-75.6, 37.6],
    [-75.95, 37.1], [-75.95, 36.55], [-75.5, 35.25], [-76.5, 34.7], [-77.9, 33.9], [-79.0, 33.35],
    [-80.0, 32.65], [-80.9, 32.0], [-81.4, 30.7], [-81.3, 29.8], [-80.6, 28.45], [-80.05, 26.8],
    [-80.1, 25.8], [-80.4, 25.2], [-81.1, 25.15], [-81.7, 25.95], [-82.6, 27.5], [-82.8, 28.2],
    [-82.7, 29.0], [-83.6, 29.9], [-84.4, 30.0], [-85.4, 29.7], [-86.5, 30.4], [-88.0, 30.4],
    [-89.4, 30.25], [-89.15, 29.2], [-89.4, 29.0], [-90.2, 29.1], [-91.3, 29.25], [-92.3, 29.55],
    [-93.8, 29.7], [-94.75, 29.35], [-95.9, 28.65], [-96.8, 28.1], [-97.3, 27.5], [-97.4, 26.5],
    [-97.15, 25.95], [-98.3, 26.1], [-99.1, 26.45], [-99.5, 27.5], [-100.3, 28.3], [-101.4, 29.77],
    [-102.4, 29.8], [-103.0, 29.1], [-104.4, 29.6], [-104.7, 30.3], [-106.5, 31.78], [-108.2, 31.78],
    [-108.2, 31.33], [-111.07, 31.33], [-114.8, 32.5], [-114.72, 32.72], [-117.12, 32.53],
    [-117.25, 32.85], [-117.4, 33.25], [-118.0, 33.65], [-118.5, 34.0], [-119.2, 34.15], [-119.9, 34.4],
    [-120.5, 34.45], [-120.65, 34.9], [-121.0, 35.5], [-121.9, 36.3], [-121.95, 36.95], [-122.4, 37.2],
    [-122.5, 37.8], [-123.0, 38.0], [-123.7, 38.9], [-123.85, 39.8], [-124.35, 40.3], [-124.1, 41.0],
    [-124.2, 41.95], [-124.55, 42.8], [-124.1, 43.7], [-123.95, 45.3], [-124.0, 46.25], [-124.1, 46.9],
    [-124.72, 48.38],
]

# Region zones: simple polygons that share their borders and together cover the box
# 126-66 W, 24-50 N. Approximate, drawn for this project from the cool-season /
# transition / warm-season framework (sources below). A field's region = the zone it is in.
W, E, N, S = -126.0, -66.0, 50.0, 24.0
L1 = [[-121.0, 49.0], [-121.5, 46.0], [-121.8, 44.0], [-122.3, 42.0], [-123.0, 40.0], [-123.2, 39.0]]
L1_SOUTH = [[-122.2, 37.5], [-121.5, 36.5], [-120.6, 35.0], [-120.6, 34.2]]
L2 = [[-112.0, 49.0], [-111.0, 47.0], [-109.5, 45.0], [-106.5, 43.0], [-105.3, 41.0], [-105.3, 37.0]]
L2_SOUTH = [[-117.5, 37.0], [-120.0, 39.0]]
L46 = [[-97.0, 40.0], [-90.0, 40.5], [-85.0, 40.5], [-80.0, 40.8], [-75.0, 40.6], [-74.0, 40.45], [E, 40.45]]
L67 = [[-100.0, 34.5], [-95.0, 34.3], [-90.0, 34.5], [-85.0, 34.3], [-80.0, 35.0], [-77.4, 34.5], [E, 34.5]]


def ring(points):
    return points + [points[0]]


ZONES = {
    1: [[W, N], [-121.0, N]] + L1 + L1_SOUTH + [[W, 34.2]],
    2: [[-121.0, N], [-112.0, N]] + L2 + L2_SOUTH + [[-123.2, 39.0]] + L1[::-1][1:],
    3: [[-112.0, N], [-97.0, N], [-97.0, 40.0], [-97.0, 37.0]] + L2[::-1],
    4: [[-97.0, N], [E, N]] + L46[::-1],
    5: [[W, 34.2]] + L1_SOUTH[::-1] + [[-123.2, 39.0]] + L2_SOUTH[::-1] + [[-105.3, 37.0], [-100.0, 37.0],
                                                                         [-100.0, 34.5], [-100.0, S], [W, S]],
    6: L46[:-1] + [[E, 40.45], [E, 34.5]] + L67[::-1][1:] + [[-100.0, 37.0], [-97.0, 37.0]],
    7: L67 + [[E, S], [-100.0, S]],
}

SOURCES = {
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
     "source": "OSU", "label": [-123.6, 45.6]},
    {"id": 2, "name": "Intermountain West", "short": "Intermountain", "climate": "cool and dry",
     "grasses": ["Kentucky bluegrass", "tall fescue", "fine fescues", "perennial ryegrass", "wheatgrass"],
     "source": "USU", "label": [-115.8, 41.6]},
    {"id": 3, "name": "Northern & Central Plains", "short": "Plains (Denver)", "climate": "cool, semi-dry",
     "grasses": ["Kentucky bluegrass", "tall fescue", "buffalograss", "blue grama", "fine fescues",
                 "perennial ryegrass"],
     "source": "CSU", "label": [-101.2, 44.0]},
    {"id": 4, "name": "Upper Midwest & Northeast", "short": "Midwest & NE", "climate": "cool and humid",
     "grasses": ["Kentucky bluegrass", "fine fescues", "perennial ryegrass", "tall fescue"],
     "source": "UMN", "label": [-90.5, 44.2]},
    {"id": 5, "name": "Southwest", "short": "Southwest", "climate": "warm and dry",
     "grasses": ["bermudagrass", "zoysiagrass", "St. Augustinegrass", "buffalograss (cooler, higher areas)"],
     "source": "UA", "label": [-110.5, 33.6]},
    {"id": 6, "name": "Transition zone", "short": "Transition", "climate": "hot summers, cold winters",
     "grasses": ["tall fescue", "Kentucky bluegrass", "perennial ryegrass", "zoysiagrass", "bermudagrass"],
     "source": "NCSU", "label": [-88.0, 37.6]},
    {"id": 7, "name": "Southeast & Gulf Coast", "short": "Southeast & Gulf", "climate": "warm and humid",
     "grasses": ["St. Augustinegrass", "bahiagrass", "centipedegrass", "zoysiagrass", "bermudagrass"],
     "source": "UF", "label": [-84.6, 32.6]},
]

data = {
    "about": ("SpectralTurf grass regions (made 2026-11-25). A SIMPLIFIED project map: boundaries are "
              "approximate and drawn for this project from the cool-season / transition / warm-season "
              "framework in the 'framework' sources; each region's grass list comes from that region's "
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
    "us_outline": US_OUTLINE,
    "regions": [{**r, "validated": r["id"] == 3,
                 "zone": {"type": "Polygon", "coordinates": [ring(ZONES[r["id"]])]}} for r in REGIONS],
}

text = json.dumps(data, indent=1) + "\n"
for path in (root + "/frontend/src/turfRegions.json", root + "/backend/turf_regions.json"):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
print("written", len(text), "bytes")
