"""
test_ai_login.py - Version 2 (2026-11-25): the AI endpoints need a login, like the website's
locked AI Check and Ask AI tabs. Visitors (no token, or a fake token) get 401.

No internet: off-season dates answer without downloading, and Gemini is replaced by a fake.
A temporary accounts database is used, so real accounts are never touched.

Run:   python test_ai_login.py
"""

import os
import tempfile

from fastapi.testclient import TestClient

import accounts
import assistant
import main

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


FIELD = {"type": "Polygon", "coordinates": [[[-104.8790, 39.6355], [-104.8784, 39.6355], [-104.8784, 39.6360],
                                             [-104.8790, 39.6360], [-104.8790, 39.6355]]]}
CALLS = {
    "/api/ai/weather-check": {"geometry": FIELD, "as_of": "2026-01-15"},
    "/api/ai/what-if": {"geometry": FIELD, "as_of": "2026-01-15", "dry_days": 7, "rain_mm": 10, "avg_high_c": 10},
    "/api/ai/ask": {"question": "How is my field?", "geometry": FIELD, "field": "screen", "as_of": "2026-08-15"},
}

asked = []
assistant.call_gemini = lambda contents: asked.append(1) or {"role": "model", "parts": [{"text": "Not enough data."}]}
assistant.limiter = assistant.RateLimiter(per_minute=100)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token = accounts.sign_up(db, "login_tester", "password-login-123")

    def test_db():
        conn = accounts.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[main.get_db] = test_db
    client = TestClient(main.app)

    n = 1
    for path, body in CALLS.items():
        r = client.post(path, json=body)
        check(f"{n}. {path} without a login -> 401 'Please log in first.'",
              r.status_code == 401 and r.json()["detail"] == "Please log in first.")
        n += 1
        r = client.post(path, json=body, headers={"Authorization": "Bearer not-a-real-token"})
        check(f"{n}. {path} with a fake token -> 401", r.status_code == 401)
        n += 1
    check(f"{n}. Gemini was never called for a visitor", asked == [])
    n += 1

    auth = {"Authorization": f"Bearer {token}"}
    r = client.post("/api/ai/weather-check", json=CALLS["/api/ai/weather-check"], headers=auth)
    check(f"{n}. logged in: weather-check works (off-season answer)", r.status_code == 200
          and r.json()["status"] == "off_season")
    n += 1
    r = client.post("/api/ai/what-if", json=CALLS["/api/ai/what-if"], headers=auth)
    check(f"{n}. logged in: what-if works (off-season answer)", r.status_code == 200
          and r.json()["current_field"]["status"] == "off_season")
    n += 1
    r = client.post("/api/ai/ask", json=CALLS["/api/ai/ask"], headers=auth)
    check(f"{n}. logged in: ask works", r.status_code == 200 and asked == [1])
    n += 1
    check(f"{n}. the What-if slider limits stay public (no personal data)",
          client.get("/api/ai/what-if/limits").status_code in (200, 503))
    n += 1
    check(f"{n}. analysis still works without a login (only the AI tools are locked)",
          client.post("/api/analyze", json={"geometry": {"type": "Point"}}).status_code == 400)

    main.app.dependency_overrides.clear()
    db.close()

print(f"\nAll {passed} checks passed.")
