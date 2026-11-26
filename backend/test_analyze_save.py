"""
test_analyze_save.py - Checks for Version 2's "saving is a separate choice" (POST /api/analyze
with "save": true / false).

No internet: the satellite analysis is replaced by a fake result, and a temporary accounts
database is used, so real accounts are never touched.

Run:   python test_analyze_save.py
"""

import os
import tempfile

from fastapi.testclient import TestClient

import accounts
import main

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


FIELD = {"type": "Polygon", "coordinates": [[[-104.8790, 39.6355], [-104.8784, 39.6355], [-104.8784, 39.6360],
                                             [-104.8790, 39.6360], [-104.8790, 39.6355]]]}
FAKE_RESULT = {
    "status": "ok", "observation": {"date": "2026-08-05", "tile_cloud_cover": 0.0},
    "pixels": {"valid_after_masking": 30, "valid_fraction": 1.0},
    "ndvi": {"median": 0.75}, "ndmi": {"median": 0.24}, "ngrdi": {"median": 0.2},
    "inspection": {"status": "no_area_stands_out", "scope": None, "headline": "No area stands out",
                   "reason": "Nothing flagged."},
    "warnings": [],
}
main.run_analysis = lambda geometry, start, end, max_cloud, exclusions=(): dict(FAKE_RESULT)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token = accounts.sign_up(db, "save_tester", "password-save-123")
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
    body = {"geometry": FIELD, "start": "2026-08-01", "end": "2026-08-15", "name": "North field"}

    r = client.post("/api/analyze", json={**body, "save": False}, headers=auth)
    check("1. 'Analyze' (save false): result shown, nothing saved",
          r.status_code == 200 and "saved_id" not in r.json() and accounts.list_analyses(db, user["id"]) == [])
    r = client.post("/api/analyze", json={**body, "save": True}, headers=auth)
    saved = accounts.list_analyses(db, user["id"])
    check("2. 'Save & analyze' (save true): saved under the name",
          r.status_code == 200 and r.json()["saved_id"] == saved[0]["id"] and saved[0]["name"] == "North field")
    r = client.post("/api/analyze", json=body, headers=auth)
    check("3. old requests without 'save' still save (unchanged behavior)",
          "saved_id" in r.json() and len(accounts.list_analyses(db, user["id"])) == 2)
    r = client.post("/api/analyze", json={**body, "save": True})
    check("4. visitors are never saved, even with save true", r.status_code == 200 and "saved_id" not in r.json())

    main.app.dependency_overrides.clear()
    db.close()

print(f"\nAll {passed} checks passed.")
