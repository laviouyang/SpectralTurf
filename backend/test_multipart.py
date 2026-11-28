"""
test_multipart.py - Checks for fields drawn as SEVERAL shapes (added 2026-11-27, student request):
backend/field_shape.py, main.clean_field, and every place that reads a field's outline.

No internet: Sentinel Hub and the AI checks are replaced by fakes that record what they were given.
A throwaway database file is used.

Run:   python test_multipart.py
"""

import json
import os
import tempfile
from datetime import date

from fastapi import HTTPException
from fastapi.testclient import TestClient

import accounts
import field_shape
import main
import predict
import regions
import sentinel

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def box(west, south, east, north):
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


# Two Village Greens turf boxes (Stage 3 grass_A and grass_B) with a gap between them.
A = box(-104.8790, 39.6337, -104.8784, 39.6344)
B = box(-104.8790, 39.6355, -104.8784, 39.6360)
POLY_A = {"type": "Polygon", "coordinates": [A]}
MULTI = {"type": "MultiPolygon", "coordinates": [[A], [B]]}


def refused(geometry):
    try:
        main.clean_field(geometry)
        return None
    except HTTPException as e:
        return e.detail if e.status_code == 400 else f"status {e.status_code}"


# ---- 1-9. checking the outline ----
check("1. one shape (Polygon) is cleaned exactly like before", main.clean_field(POLY_A) == main.clean_polygon(POLY_A))
check("2. two separate shapes -> MultiPolygon with both pieces", main.clean_field(MULTI) == MULTI)
check("3. a MultiPolygon with only one piece becomes a plain Polygon",
      main.clean_field({"type": "MultiPolygon", "coordinates": [[A]]}) == POLY_A)
overlap = {"type": "MultiPolygon", "coordinates": [[A], [box(-104.8787, 39.6340, -104.8780, 39.6350)]]}
check("4. overlapping pieces are refused", "must not overlap" in (refused(overlap) or ""))
inside = {"type": "MultiPolygon", "coordinates": [[A], [box(-104.8789, 39.6338, -104.8786, 39.6340)]]}
check("5. a piece lying completely inside another is refused", "must not overlap" in (refused(inside) or ""))
check("6. the same piece twice is refused", "must not overlap" in (refused({"type": "MultiPolygon", "coordinates": [[A], [A]]}) or ""))
touching = {"type": "MultiPolygon", "coordinates": [[A], [box(-104.8784, 39.6337, -104.8778, 39.6344)]]}
check("7. pieces that only touch along an edge are allowed", refused(touching) is None)
many = {"type": "MultiPolygon", "coordinates": [[box(-104.9 + i * 0.001, 39.6, -104.9 + i * 0.001 + 0.0005, 39.6005)]
                                                for i in range(field_shape.MAX_FIELD_PARTS + 1)]}
check(f"8. more than {field_shape.MAX_FIELD_PARTS} pieces is refused", "at most" in (refused(many) or ""))
check("9. a broken piece (2 corners) or a wrong type is refused",
      refused({"type": "MultiPolygon", "coordinates": [[A], [[[0, 0], [1, 1], [0, 0]]]]}) is not None
      and "Polygon or MultiPolygon" in (refused({"type": "Point", "coordinates": [0, 0]}) or "")
      and refused({"type": "MultiPolygon", "coordinates": "x"}) is not None)

# ---- 10-15. everything that reads the outline understands several pieces ----
check("10. the satellite box covers all pieces", sentinel.geometry_bbox(MULTI) == (-104.8790, 39.6337, -104.8784, 39.6360))
check("11. ...and is unchanged for one shape", sentinel.geometry_bbox(POLY_A) == (-104.8790, 39.6337, -104.8784, 39.6344))
check("12. grass region detected from all pieces (Denver -> Region 3)", regions.resolve(None, MULTI)["id"] == 3)
lon, lat = predict.centroid(MULTI)
check("13. AI check center = average corner of all pieces", abs(lon + 104.8787) < 1e-9 and abs(lat - 39.6349) < 1e-9)
hole_b = {"type": "Polygon", "coordinates": [box(-104.8789, 39.6356, -104.8787, 39.6357)]}
shape, note = predict.field_geometry(MULTI, [hole_b])
check("14. AI check: an excluded area becomes a hole in the piece it lies in",
      note is None and shape["type"] == "MultiPolygon" and shape["coordinates"][0] == [A]
      and shape["coordinates"][1] == [B, hole_b["coordinates"][0]])
gap = {"type": "Polygon", "coordinates": [box(-104.8789, 39.6346, -104.8787, 39.6350)]}  # between the pieces
shape, note = predict.field_geometry(MULTI, [gap])
check("15. ...an excluded area outside every piece is not used (with a note), like before",
      shape == MULTI and "NOT used" in note)

# ---- 16-22. the endpoints accept a field in several pieces ----
seen = {}


def fake_run_analysis(geometry, start, end, max_cloud, exclusions=()):
    seen["analyze"] = geometry
    return {"status": "ok", "geometry_seen": geometry}


def fake_weather_check(geometry, exclusions, as_of):
    seen["weather"] = geometry
    return {"status": "ok"}


real_run, real_check = main.run_analysis, predict.weather_check
main.run_analysis, predict.weather_check = fake_run_analysis, fake_weather_check
try:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
        db_path = os.path.join(folder, "test.db")
        db = accounts.connect(db_path)
        token = accounts.sign_up(db, "multi_tester", "password-multi-123")
        user = accounts.user_for_token(db, token)

        def test_db():
            conn = accounts.connect(db_path)
            try:
                yield conn
            finally:
                conn.close()

        main.app.dependency_overrides[main.get_db] = test_db
        client = TestClient(main.app)
        auth = {"Authorization": f"Bearer {token}"}

        r = client.post("/api/analyze", json={"geometry": MULTI, "start": "2026-08-01", "end": "2026-08-10",
                                              "save": False})
        check("16. /api/analyze accepts several pieces and analyzes them together",
              r.status_code == 200 and seen["analyze"] == MULTI and r.json()["grass_region"]["id"] == 3)
        r = client.post("/api/analyze", json={"geometry": overlap, "start": "2026-08-01", "end": "2026-08-10"})
        check("17. /api/analyze refuses overlapping pieces (400)", r.status_code == 400 and "overlap" in r.json()["detail"])
        r = client.post("/api/fields", json={"name": "Park fields", "geometry": MULTI, "exclude": [hole_b]}, headers=auth)
        saved = accounts.list_analyses(db, user["id"])
        check("18. Save to My Fields keeps all pieces under ONE field name",
              r.status_code == 200 and len(saved) == 1 and saved[0]["name"] == "Park fields"
              and saved[0]["geometry"] == MULTI and saved[0]["exclusions"] == [hole_b])
        check("19. the AI tools list it as one field",
              [f["name"] for f in predict.distinct_saved_fields(saved)] == ["Park fields"])
        r = client.post("/api/ai/weather-check", json={"geometry": MULTI, "exclude": [], "as_of": "2026-08-15"},
                        headers=auth)
        check("20. AI Weather Check accepts several pieces", r.status_code == 200 and seen["weather"] == MULTI)
        history = client.get("/api/history", headers=auth).json()["analyses"]
        check("21. History / Show on map gets the pieces back exactly", history[0]["geometry"] == MULTI)
        r = client.post("/api/analyze", json={"geometry": POLY_A, "start": "2026-08-01", "end": "2026-08-10",
                                              "save": False})
        check("22. a single shape still works exactly as before", r.status_code == 200 and seen["analyze"] == POLY_A)

        def fake_what_if(geometry, exclusions, as_of, scenario):
            seen["what_if"] = geometry
            return {"status": "ok"}

        def fake_ask(question, ctx, call=None, photo=None):
            seen["ask"] = (ctx.screen["geometry"], ctx.grass_region["id"])
            return {"status": "ok", "answer": "fake"}

        real_what_if, real_ask = predict.what_if, main.assistant.ask
        predict.what_if, main.assistant.ask = fake_what_if, fake_ask
        main.assistant.limiter = main.assistant.RateLimiter()
        try:
            r = client.post("/api/ai/what-if", json={"geometry": MULTI, "exclude": [], "as_of": "2026-08-15",
                                                     "dry_days": 3, "rain_mm": 5, "avg_high_c": 30}, headers=auth)
            check("23. What if? accepts several pieces", r.status_code == 200 and seen["what_if"] == MULTI)
            r = client.post("/api/ai/ask", json={"question": "How is my field?", "geometry": MULTI, "exclude": [],
                                                 "field": "screen", "as_of": "2026-08-15"}, headers=auth)
            check("24. Ask SpectralTurf AI gets all pieces (and Region 3) for the field on the map",
                  r.status_code == 200 and seen["ask"] == (MULTI, 3))
        finally:
            predict.what_if, main.assistant.ask = real_what_if, real_ask
        main.app.dependency_overrides.clear()
finally:
    main.run_analysis, predict.weather_check = real_run, real_check

# ---- 25. merged shapes from the website (frontend/scripts/test_field_shapes.mjs writes them) ----
cases_path = os.path.join(os.path.dirname(__file__), "field_shape_cases.json")
with open(cases_path, encoding="utf-8") as f:
    cases = json.load(f)
problems = [i for i, g in enumerate(cases) if refused(g) is not None]
check(f"25. all {len(cases)} fields merged by the website (random shapes) pass the backend check", problems == [])

print(f"\nAll {passed} checks passed.")
