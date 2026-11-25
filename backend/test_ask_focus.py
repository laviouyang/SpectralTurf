"""
test_ask_focus.py - Checks for Version 2's "pick ONE field first" in Ask SpectralTurf
(Context(focus=...) in assistant.py, and the optional "field" in POST /api/ai/ask).

No internet, no Gemini key: Gemini and the satellite/weather lookups are fakes, and a
temporary accounts database is used, so real accounts are never touched.

Run:   python test_ask_focus.py
"""

import copy
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


def square(x):
    return {"type": "Polygon", "coordinates": [[[x, 39.6], [x + 0.002, 39.6], [x + 0.002, 39.602],
                                                [x, 39.602], [x, 39.6]]]}


FIELD_A1, FIELD_A2, FIELD_B, SCREEN = square(-104.90), square(-104.80), square(-104.70), square(-104.88)
FAKE_RESULT = {
    "status": "ok", "observation": {"date": "2026-08-05", "tile_cloud_cover": 0.0},
    "pixels": {"valid_after_masking": 120, "valid_fraction": 1.0},
    "ndvi": {"median": 0.7}, "ndmi": {"median": 0.2}, "ngrdi": {"median": 0.2},
    "inspection": {"status": "no_area_stands_out", "scope": None,
                   "headline": "No area stands out", "reason": "Nothing flagged."},
    "warnings": [],
}


def fake_snapshot(geometry, exclusions, as_of):
    return {"clear": [{"date": "2026-08-05", "ndvi_mean": 0.7, "clear_fraction": 1.0}], "weather": {},
            "geometry_note": None}


predict.field_snapshot = fake_snapshot


class FakeGemini:
    def __init__(self, *messages):
        self.messages = list(messages)
        self.sent = []

    def __call__(self, contents):
        self.sent.append(copy.deepcopy(contents))
        return self.messages.pop(0)


def tool_call(name, **args):
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args, "id": f"call-{name}"}}]}


def text(answer):
    return {"role": "model", "parts": [{"text": answer}]}


AS_OF = date(2026, 8, 15)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token_a = accounts.sign_up(db, "alice_user", "password-alice-123")
    token_b = accounts.sign_up(db, "bob_user", "password-bob-123")
    alice, bob = accounts.user_for_token(db, token_a), accounts.user_for_token(db, token_b)
    a1_old = accounts.save_analysis(db, alice["id"], "North", FIELD_A1, [], "2026-07-01", "2026-07-31", FAKE_RESULT)
    a2 = accounts.save_analysis(db, alice["id"], "South", FIELD_A2, [], "2026-08-01", "2026-08-31", FAKE_RESULT)
    a1_new = accounts.save_analysis(db, alice["id"], "North", FIELD_A1, [], "2026-08-01", "2026-08-31", FAKE_RESULT)
    b_row = accounts.save_analysis(db, bob["id"], "Bob Field", FIELD_B, [], "2026-08-01", "2026-08-31", FAKE_RESULT)
    saved_a = accounts.list_analyses(db, alice["id"])

    # ---- 1. Context with a picked field ----
    plain = assistant.Context(True, saved_a, None, None, AS_OF)
    check("1. every save of the same outline maps to the same field label",
          plain.label_for_saved_id(a1_old) == plain.label_for_saved_id(a1_new) is not None)
    check("2. another user's saved id is not found", plain.label_for_saved_id(b_row) is None)
    north = plain.label_for_saved_id(a1_new)
    south = plain.label_for_saved_id(a2)

    ctx = assistant.Context(True, saved_a, None, None, AS_OF, focus=north)
    listed = assistant.run_tool("get_my_fields", {}, ctx)
    check("3. get_my_fields lists only the picked field", [f["field_id"] for f in listed["fields"]] == [north])
    check("4. the picked field's saved history works",
          len(assistant.run_tool("get_field_history", {"field_id": north}, ctx)["saved_analyses"]) == 2)
    check("5. the other saved field is refused",
          "error" in assistant.run_tool("get_latest_analysis", {"field_id": south}, ctx))
    check("6. the ranking of several fields is refused", "error" in assistant.run_tool("get_ranking", {}, ctx))
    check("7. without a picked field nothing changed (both fields listed)",
          len(assistant.run_tool("get_my_fields", {}, plain)["fields"]) == 2)

    screen = {"geometry": SCREEN, "exclusions": [], "start": "2026-08-01", "end": "2026-08-31", "max_cloud": 30}
    ctx_s = assistant.Context(True, saved_a, screen, lambda: FAKE_RESULT, AS_OF, focus="screen")
    check("8. picked 'screen': the map field works, saved fields are refused",
          assistant.run_tool("get_latest_analysis", {"field_id": "screen"}, ctx_s)["ndvi_median"] == 0.7
          and "error" in assistant.run_tool("get_latest_analysis", {"field_id": north}, ctx_s))

    fake = FakeGemini(text("Not enough data."))
    assistant.ask("How is it?", ctx, call=fake)
    check("9. Gemini is told the user picked one field", f"picked ONE field ('{north}')" in fake.sent[0][0]["parts"][0]["text"])

    # ---- 2. The endpoint ----
    def test_db():
        conn = accounts.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[main.get_db] = test_db
    client = TestClient(main.app)
    assistant.limiter = assistant.RateLimiter(per_minute=100)
    real_call = assistant.call_gemini
    auth_a = {"Authorization": f"Bearer {token_a}"}

    fake = FakeGemini(tool_call("get_my_fields"), text("Your field is listed. Confirm in person."))
    assistant.call_gemini = fake
    r = client.post("/api/ai/ask", json={"question": "Which fields?", "as_of": "2026-08-15", "field": str(a2)},
                    headers=auth_a)
    result = fake.sent[1][-1]["parts"][0]["functionResponse"]["response"]["result"]
    check("10. endpoint: a saved field id -> only that field is visible",
          r.status_code == 200 and [f["field_id"] for f in result["fields"]] == [south])
    check("11. endpoint: another user's saved id -> 404",
          client.post("/api/ai/ask", json={"question": "Hi", "field": str(b_row)}, headers=auth_a).status_code == 404)
    check("12. endpoint: a saved field while logged out -> 401",
          client.post("/api/ai/ask", json={"question": "Hi", "field": str(a2)}).status_code == 401)
    check("13. endpoint: 'screen' without a field on the map -> 400",
          client.post("/api/ai/ask", json={"question": "Hi", "field": "screen"}, headers=auth_a).status_code == 400)
    check("14. endpoint: nonsense field -> 404",
          client.post("/api/ai/ask", json={"question": "Hi", "field": "abc"}, headers=auth_a).status_code == 404)
    assistant.call_gemini = lambda contents: text("Not enough data.")
    check("15. endpoint: requests without 'field' still work as before",
          client.post("/api/ai/ask", json={"question": "Hi", "as_of": "2026-08-15"}, headers=auth_a).status_code == 200)

    assistant.call_gemini = real_call
    main.app.dependency_overrides.clear()
    db.close()

print(f"\nAll {passed} checks passed.")
