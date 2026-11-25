"""
test_regions.py - Checks for the grass regions (regions.py, turf_regions.json), added 2026-11-25.

ADD-ON ONLY: the analysis numbers must be exactly the same as before; results only get an extra
"grass_region" label. No internet: the satellite analysis and Gemini are replaced by fakes, and a
temporary accounts database is used.

Run:   python test_regions.py
"""

import copy
import json
import os
import tempfile

from fastapi.testclient import TestClient

import accounts
import assistant
import main
import regions

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


# ---- 1. The data ----
frontend_copy = os.path.join(os.path.dirname(__file__), "..", "frontend", "src", "turfRegions.json")
if os.path.exists(frontend_copy):  # (on Render only the backend folder exists)
    with open(frontend_copy, encoding="utf-8") as a, open(regions.DATA_FILE, encoding="utf-8") as b:
        check("1. the website's region file and the backend's copy are identical", json.load(a) == json.load(b))
check("2. there are 7 regions, numbered 1-7", sorted(regions.REGIONS) == [1, 2, 3, 4, 5, 6, 7])
check("3. only Region 3 is validated", [r for r in regions.REGIONS if regions.REGIONS[r]["validated"]] == [3])
check("4. every region has grasses and a source with a link",
      all(r["grasses"] and regions.DATA["sources"][r["source"]]["url"].startswith("https://")
          for r in regions.REGIONS.values()))


def ring_area(ring):
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))) / 2


check("5. the region zones cover the whole map box with no gap (126-66 W, 24-50 N)",
      abs(sum(ring_area(r["zone"]["coordinates"][0]) for r in regions.REGIONS.values()) - 60 * 26) < 1e-6)

# ---- 2. Detecting a field's region (approximate boundaries; well-known places) ----
PLACES = [
    ("Village Greens Park, Greenwood Village CO", -104.880, 39.635, 3),
    ("Denver CO", -104.99, 39.74, 3), ("Boulder CO", -105.27, 40.01, 3), ("Cheyenne WY", -104.82, 41.14, 3),
    ("Grand Junction CO (west of the Rockies)", -108.55, 39.06, 2), ("Salt Lake City UT", -111.89, 40.76, 2),
    ("Boise ID", -116.20, 43.62, 2), ("Seattle WA", -122.33, 47.61, 1), ("Portland OR", -122.68, 45.52, 1),
    ("Chicago IL", -87.63, 41.88, 4), ("Boston MA", -71.06, 42.36, 4), ("Minneapolis MN", -93.27, 44.98, 4),
    ("Phoenix AZ", -112.07, 33.45, 5), ("Las Vegas NV", -115.14, 36.17, 5), ("Los Angeles CA", -118.24, 34.05, 5),
    ("Nashville TN", -86.78, 36.16, 6), ("Kansas City MO", -94.58, 39.10, 6), ("Washington DC", -77.04, 38.91, 6),
    ("Atlanta GA", -84.39, 33.75, 7), ("Miami FL", -80.19, 25.76, 7), ("Dallas TX", -96.80, 32.78, 7),
]
wrong = [(name, regions.detect(lon, lat), expected) for name, lon, lat, expected in PLACES
         if regions.detect(lon, lat) != expected]
check(f"6. {len(PLACES)} well-known places land in the expected region", wrong == [])
check("7. outside the 48 states' map (Anchorage, Honolulu) -> no region",
      regions.detect(-149.90, 61.22) is None and regions.detect(-157.86, 21.31) is None)

# ---- 3. The analysis: same numbers, plus a region label ----
FIELD = {"type": "Polygon", "coordinates": [[[-104.8790, 39.6355], [-104.8784, 39.6355], [-104.8784, 39.6360],
                                             [-104.8790, 39.6360], [-104.8790, 39.6355]]]}
FAR_FIELD = {"type": "Polygon", "coordinates": [[[-84.40, 33.75], [-84.399, 33.75], [-84.399, 33.751],
                                                 [-84.40, 33.751], [-84.40, 33.75]]]}
FAKE_RESULT = {
    "status": "ok", "observation": {"date": "2026-08-05", "tile_cloud_cover": 0.0},
    "pixels": {"valid_after_masking": 30, "valid_fraction": 1.0},
    "ndvi": {"median": 0.754}, "ndmi": {"median": 0.239}, "ngrdi": {"median": 0.2},
    "inspection": {"status": "no_area_stands_out", "scope": None, "headline": "No area stands out",
                   "reason": "Nothing flagged."},
    "warnings": [],
}
main.run_analysis = lambda geometry, start, end, max_cloud, exclusions=(): copy.deepcopy(FAKE_RESULT)
client = TestClient(main.app)

r = client.post("/api/analyze", json={"geometry": FIELD, "save": False}).json()
without_region = {k: v for k, v in r.items() if k != "grass_region"}
check("8. Denver-area analysis: numbers exactly as before, only 'grass_region' added",
      without_region == FAKE_RESULT)
check("9. Denver-area field -> Region 3, validated, detected from its location",
      r["grass_region"]["id"] == 3 and r["grass_region"]["validated"] is True
      and r["grass_region"]["how"].startswith("detected"))
r = client.post("/api/analyze", json={"geometry": FAR_FIELD, "save": False}).json()
check("10. an Atlanta field -> Region 7, 'not validated for this region yet' + the within-field note",
      r["grass_region"]["id"] == 7 and r["grass_region"]["validated"] is False
      and "within-field check" in r["grass_region"]["note"])
r = client.post("/api/analyze", json={"geometry": FIELD, "save": False, "region": 6}).json()
check("11. the user can change the region (sent by the website)",
      r["grass_region"]["id"] == 6 and r["grass_region"]["how"].startswith("region sent"))
check("12. a region number outside 1-7 is refused (422)",
      client.post("/api/analyze", json={"geometry": FIELD, "region": 9}).status_code == 422)

# ---- 4. Ask SpectralTurf gets the region ----
assistant.limiter = assistant.RateLimiter(per_minute=100)
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token = accounts.sign_up(db, "region_tester", "password-region-123")

    def test_db():
        conn = accounts.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[main.get_db] = test_db
    auth = {"Authorization": f"Bearer {token}"}
    sent = []

    def fake_gemini(contents):
        sent.append(copy.deepcopy(contents))
        if len(sent) == 1:
            return {"role": "model", "parts": [{"functionCall": {"name": "get_my_fields", "args": {}, "id": "c1"}}]}
        return {"role": "model", "parts": [{"text": "This field is in Region 7, which is not validated yet. "
                                                    "Confirm in person."}]}

    assistant.call_gemini = fake_gemini
    r = client.post("/api/ai/ask", json={"question": "Where is my field?", "geometry": FAR_FIELD,
                                         "field": "screen", "as_of": "2026-08-15"}, headers=auth)
    tool_result = sent[1][-1]["parts"][0]["functionResponse"]["response"]["result"]
    check("13. Ask: tool results include the field's region and 'validated' (Atlanta -> 7, not validated)",
          r.status_code == 200 and tool_result["grass_region"]["id"] == 7
          and tool_result["grass_region"]["validated"] is False)
    check("14. Ask: Gemini is told the region in the question's context",
          "Region 7: Southeast & Gulf Coast" in sent[0][0]["parts"][0]["text"])
    check("15. Ask: the answer mentioning 'Region 7' passes the number check", r.json()["status"] == "ok")
    sent.clear()
    client.post("/api/ai/ask", json={"question": "Where is my field?", "geometry": FIELD, "field": "screen",
                                     "as_of": "2026-08-15"}, headers=auth)
    check("16. Ask: a Denver-area field -> Region 3, validated",
          "Region 3: Northern & Central Plains (Validated" in sent[0][0]["parts"][0]["text"])
    main.app.dependency_overrides.clear()
    db.close()

print(f"\nAll {passed} checks passed.")
