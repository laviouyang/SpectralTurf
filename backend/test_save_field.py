"""
test_save_field.py - Checks for Version 2's separate "Save" button (POST /api/fields,
saved_fields.py): a field is saved to My Fields without an analysis, and no numbers are made up.

No internet; a temporary accounts database is used, so real accounts are never touched.

Run:   python test_save_field.py
"""

import json
import os
import tempfile
from datetime import date

from fastapi.testclient import TestClient

import accounts
import assistant
import main
import predict

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


FIELD = {"type": "Polygon", "coordinates": [[[-104.8790, 39.6355], [-104.8784, 39.6355], [-104.8784, 39.6360],
                                             [-104.8790, 39.6360], [-104.8790, 39.6355]]]}
HOLE = {"type": "Polygon", "coordinates": [[[-104.8789, 39.6356], [-104.8787, 39.6356], [-104.8787, 39.6357],
                                            [-104.8789, 39.6357], [-104.8789, 39.6356]]]}

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token = accounts.sign_up(db, "field_saver", "password-field-123")
    other = accounts.sign_up(db, "other_user", "password-other-123")
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

    r = client.post("/api/fields", json={"name": "North field", "geometry": FIELD, "exclude": [HOLE]}, headers=auth)
    saved = accounts.list_analyses(db, user["id"])
    check("1. Save: the field is in My Fields with its name, outline and excluded area",
          r.status_code == 200 and r.json()["saved_id"] == saved[0]["id"] and saved[0]["name"] == "North field"
          and saved[0]["geometry"] == FIELD and saved[0]["exclusions"] == [HOLE])
    check("2. no numbers or image date are stored (nothing was measured)",
          saved[0]["summary"] == {"status": "not_analyzed"} and saved[0]["observation_date"] == "")
    check("3. visitors can't save (401)",
          client.post("/api/fields", json={"name": "x", "geometry": FIELD}).status_code == 401)
    check("4. an empty name is refused (400)",
          client.post("/api/fields", json={"name": "  ", "geometry": FIELD}, headers=auth).status_code == 400)
    check("5. a bad outline is refused (400)",
          client.post("/api/fields", json={"name": "x", "geometry": {"type": "Point"}}, headers=auth).status_code == 400)
    check("6. another user does not see it",
          accounts.list_analyses(db, accounts.user_for_token(db, other)["id"]) == [])
    check("7. the AI tools see it as a field (My Fields ranking / AI checks use the outline)",
          [f["name"] for f in predict.distinct_saved_fields(saved)] == ["North field"])
    ctx = assistant.Context(True, saved, None, None, date(2026, 8, 15))
    facts = assistant.run_tool("get_latest_analysis", {"field_id": "field-1"}, ctx)
    check("8. Ask AI is told it was never analyzed, with no numbers",
          facts.get("status") == "not_analyzed" and "ndvi_median" not in json.dumps(facts))

    main.app.dependency_overrides.clear()
    db.close()

print(f"\nAll {passed} checks passed.")
