"""
test_assistant.py - Checks for the "Ask SpectralTurf" assistant (assistant.py + POST /api/ai/ask).

No internet, no Copernicus, no Gemini key needed: Gemini is replaced by a FAKE that plays back
prepared answers, and the satellite/weather lookups are replaced by fakes too. A temporary
accounts database is used, so your real accounts are never touched.

Run:   python test_assistant.py
"""

import copy
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


def square(x):
    return {"type": "Polygon", "coordinates": [[[x, 39.6], [x + 0.002, 39.6], [x + 0.002, 39.602],
                                                [x, 39.602], [x, 39.6]]]}


FIELD_A1, FIELD_A2, FIELD_B, SCREEN = square(-104.90), square(-104.80), square(-104.70), square(-104.88)
FAKE_RESULT = {
    "status": "ok", "observation": {"date": "2026-08-05", "tile_cloud_cover": 0.0},
    "pixels": {"valid_after_masking": 120, "valid_fraction": 1.0},
    "ndvi": {"median": 0.7}, "ndmi": {"median": 0.2}, "ngrdi": {"median": 0.2},
    "inspection": {"status": "may_warrant_inspection", "scope": "some_areas",
                   "headline": "Some areas may warrant inspection", "reason": "8% of pixels are yellow."},
    "warnings": [],
}

# ---- fakes for the satellite / weather lookups (no internet) ----
checked_geometries = []


def fake_weather_check(geometry, exclusions, as_of):
    checked_geometries.append(geometry)
    return {"as_of": as_of.isoformat(), "status": "ok", "last_image_date": "2026-08-05", "actual_ndvi": 0.7,
            "latest_clear_fraction": 1.0, "previous_image_date": "2026-07-25", "typical_error": 0.0611,
            "check": {"status": "ok", "expected_ndvi": 0.68, "difference": 0.02, "weather_explains": True,
                      "message": "Weather explains this."},
            "risk_next_week": {"target_date": "2026-08-22", "level": "Low", "predicted_ndvi": 0.69,
                               "predicted_change": -0.01}}


def fake_snapshot(geometry, exclusions, as_of):
    checked_geometries.append(geometry)
    return {"clear": [{"date": "2026-08-05", "ndvi_mean": 0.7, "clear_fraction": 1.0}], "weather": {},
            "geometry_note": None}


real_rank, real_weather_check = predict.rank_my_fields, predict.weather_check
predict.weather_check = fake_weather_check
predict.field_snapshot = fake_snapshot
predict.rank_my_fields = lambda saved, as_of: real_rank(saved, as_of, check=fake_weather_check)


class FakeGemini:
    """Plays back prepared Gemini messages and remembers everything it was sent."""

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


def run_tool(ctx, name, **args):
    return assistant.run_tool(name, args, ctx)


AS_OF = date(2026, 8, 15)

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    db_path = os.path.join(folder, "test.db")
    db = accounts.connect(db_path)
    token_a = accounts.sign_up(db, "alice_secret_name", "password-alice-123")
    token_b = accounts.sign_up(db, "bob_user", "password-bob-123")
    alice, bob = accounts.user_for_token(db, token_a), accounts.user_for_token(db, token_b)
    accounts.save_analysis(db, alice["id"], "Smith Family Yard", FIELD_A1, [], "2026-08-01", "2026-08-31", FAKE_RESULT)
    accounts.save_analysis(db, alice["id"], "School North", FIELD_A2, [], "2026-08-01", "2026-08-31", FAKE_RESULT)
    b_row = accounts.save_analysis(db, bob["id"], "Bob Field", FIELD_B, [], "2026-08-01", "2026-08-31", FAKE_RESULT)

    def ctx_for(user, screen=None, analyze=None):
        saved = accounts.list_analyses(db, user["id"]) if user else []
        return assistant.Context(user is not None, saved, screen, analyze, AS_OF)

    # ---- 1. Tools only return the user's own data ----
    ctx_a = ctx_for(alice)
    mine = run_tool(ctx_a, "get_my_fields")
    check("1. get_my_fields lists exactly Alice's 2 fields",
          [f["field_id"] for f in mine["fields"]] == ["field-1", "field-2"])
    check("2. a field id she doesn't have gives an error, not someone else's data",
          "error" in run_tool(ctx_a, "get_latest_analysis", field_id="field-3"))
    check("3. Bob's database row id doesn't work for Alice",
          "error" in run_tool(ctx_a, "get_latest_analysis", field_id=str(b_row)))
    checked_geometries.clear()
    ranking = run_tool(ctx_a, "get_ranking")
    check("4. the ranking contains only Alice's fields (Bob's outline is never checked)",
          len(ranking["fields"]) == 2 and FIELD_B not in checked_geometries
          and {f["field_id"] for f in ranking["fields"]} == {"field-1", "field-2"})
    check("5. Bob sees only his own 1 field",
          [f["field_id"] for f in run_tool(ctx_for(bob), "get_my_fields")["fields"]] == ["field-1"])
    latest = run_tool(ctx_a, "get_latest_analysis", field_id="field-1")
    check("6. latest analysis is labeled 'observation' with its image date",
          latest["kind"] == "observation" and latest["image_date"] == "2026-08-05")
    evo = run_tool(ctx_a, "get_expected_vs_observed", field_id="field-2")
    check("7. expected vs observed labels observation / AI estimate / forecast",
          evo["observation"]["kind"] == "observation" and evo["ai_estimate"]["kind"].startswith("AI estimate")
          and evo["forecast"]["kind"] == "forecast")
    history = run_tool(ctx_a, "get_field_history", field_id="field-1")
    check("8. field history has the saved analysis and the clear images",
          len(history["saved_analyses"]) == 1 and history["clear_satellite_images_last_60_days"]["images"])
    everything = json.dumps([mine, ranking, latest, evo, history])
    check("9. no tool result contains names, usernames or coordinates",
          all(s not in everything for s in ("Smith Family Yard", "School North", "alice", "-104.9", "39.6")))

    # ---- 2. Visitors: only the field on screen ----
    screen = {"geometry": SCREEN, "exclusions": [], "start": "2026-08-01", "end": "2026-08-31", "max_cloud": 30}
    ctx_v = ctx_for(None, screen, lambda: FAKE_RESULT)
    check("10. visitor: get_my_fields shows only the screen field",
          [f["field_id"] for f in run_tool(ctx_v, "get_my_fields")["fields"]] == ["screen"])
    check("11. visitor: saved fields and the ranking are refused",
          "error" in run_tool(ctx_v, "get_latest_analysis", field_id="field-1")
          and "error" in run_tool(ctx_v, "get_ranking"))
    shown = run_tool(ctx_v, "get_latest_analysis", field_id="screen")
    check("12. visitor: the field on screen works (backend analysis)",
          shown["ndvi_median"] == 0.7 and shown["inspection"]["reason"] == "8% of pixels are yellow.")
    check("13. no field on screen -> error, not a guess",
          "error" in run_tool(ctx_for(None), "get_expected_vs_observed", field_id="screen"))

    # ---- 3. The agent loop with a fake Gemini ----
    fake = FakeGemini(tool_call("get_ranking"),
                      text("Inspect field-1 first. Observation 2026-08-05: NDVI 0.70, 100% clear. "
                           "AI estimate 0.68. Confirm in person."))
    reply = assistant.ask("Which field should I inspect first?", ctx_for(alice), call=fake)
    check("14. tool call -> tool result sent back -> answer shown",
          reply["status"] == "ok" and reply["tools_used"] == ["get_ranking"]
          and "functionResponse" in fake.sent[1][-1]["parts"][0])
    check("15. the function response keeps Gemini's call id",
          fake.sent[1][-1]["parts"][0]["functionResponse"]["id"] == "call-get_ranking")
    check("16. field names are shown to the user only through the legend",
          reply["field_names"] == {"field-1": "School North"})
    sent = json.dumps(fake.sent)
    check("17. nothing personal is sent to Gemini (username, password, field names, coordinates)",
          all(s not in sent for s in ("alice_secret_name", "password-alice", "School North",
                                      "Smith Family Yard", "-104.9", "39.6", token_a)))

    made_up = text("The field's NDVI is 0.93 and it will reach 0.95 on 2026-09-01.")
    reply = assistant.ask("How is field-1?", ctx_for(alice),
                          call=FakeGemini(tool_call("get_latest_analysis", field_id="field-1"), made_up, made_up))
    check("18. an answer with invented numbers/dates is NOT shown", reply["status"] == "blocked")
    reply = assistant.ask("How is field-1?", ctx_for(alice),
                          call=FakeGemini(tool_call("get_latest_analysis", field_id="field-1"), made_up,
                                          text("Observation 2026-08-05: NDVI 0.7. Confirm in person.")))
    check("19. Gemini gets one chance to fix it", reply["status"] == "ok")
    water = text("Water for 20 minutes every day.")
    reply = assistant.ask("How much should I water?", ctx_for(alice), call=FakeGemini(water, water))
    check("20. watering amounts / schedules are blocked", reply["status"] == "blocked")
    cause = text("The drop was caused by drought.")
    check("21. claiming a cause is blocked",
          assistant.ask("Why?", ctx_for(alice), call=FakeGemini(cause, cause))["status"] == "blocked")
    check("22. 'not enough data' without numbers is fine",
          assistant.ask("Why?", ctx_for(alice), call=FakeGemini(text("Not enough data.")))["status"] == "ok")
    loop = FakeGemini(*[tool_call("get_my_fields") for _ in range(assistant.MAX_TOOL_ROUNDS + 1)])
    try:
        assistant.ask("Loop forever", ctx_for(alice), call=loop)
        stopped = False
    except assistant.AssistantError:
        stopped = True
    check("23. a runaway tool loop is stopped", stopped)

    # ---- 4. Limits ----
    limiter = assistant.RateLimiter(per_minute=5, per_day=100)
    for _ in range(5):
        limiter.check("user:1", now=1000)
    try:
        limiter.check("user:1", now=1010)
        limited = False
    except assistant.AssistantError:
        limited = True
    check("24. the 6th question within a minute is refused", limited)
    limiter.check("user:2", now=1010)
    limiter.check("user:1", now=1061)
    check("25. other users are not affected, and it resets after a minute", True)
    try:
        assistant.ask("x" * (assistant.MAX_QUESTION_CHARS + 1), ctx_for(alice), call=FakeGemini())
        too_long = False
    except assistant.AssistantError:
        too_long = True
    check("26. too-long questions are refused before calling Gemini", too_long)

    # ---- 5. Missing / bad key: friendly message ----
    saved_key = os.environ.pop("GEMINI_API_KEY", None)
    try:
        assistant.call_gemini([])
        message = ""
    except assistant.AssistantError as e:
        message = str(e)
    check("27. missing key -> friendly message", message == assistant.NOT_SET_UP)

    class FakeResponse:
        def __init__(self, status, body):
            self.status_code, self._body, self.text = status, body, json.dumps(body)

        def json(self):
            return self._body

    real_post = assistant.requests.post
    os.environ["GEMINI_API_KEY"] = "not-a-real-key"
    for status, body, expected in [
        (400, {"error": {"message": "API key not valid. Please pass a valid API key."}}, assistant.NOT_SET_UP),
        (503, {"error": {"message": "high demand"}}, "busy"),
        (429, {"error": {"message": "quota"}}, "limit"),
    ]:
        assistant.requests.post = lambda *a, _s=status, _b=body, **k: FakeResponse(_s, _b)
        try:
            assistant.call_gemini([])
            message = ""
        except assistant.AssistantError as e:
            message = str(e)
        check(f"28. Gemini HTTP {status} -> friendly message", expected in message)
    assistant.requests.post = real_post
    os.environ.pop("GEMINI_API_KEY")

    # ---- 6. The endpoint (temporary database, still no key) ----
    def test_db():
        conn = accounts.connect(db_path)
        try:
            yield conn
        finally:
            conn.close()

    main.app.dependency_overrides[main.get_db] = test_db
    client = TestClient(main.app)
    assistant.limiter = assistant.RateLimiter()
    auth_a = {"Authorization": f"Bearer {token_a}"}  # login required since 2026-11-25 (Version 2)
    r = client.post("/api/ai/ask", json={"question": "Hi", "as_of": "2026-08-15"}, headers=auth_a)
    check("29. endpoint without a key: friendly 503", r.status_code == 503 and r.json()["detail"] == assistant.NOT_SET_UP)
    check("30. the rest of the app still works (health)", client.get("/api/health").json() == {"status": "ok"})
    predict.weather_check = real_weather_check  # the real one (off-season answers without downloading)
    r = client.post("/api/ai/weather-check", json={"geometry": SCREEN, "as_of": "2026-01-15"}, headers=auth_a)
    predict.weather_check = fake_weather_check
    check("31. the rest of the app still works (AI weather check)", r.status_code == 200
          and r.json()["status"] == "off_season")
    check("32. the rest of the app still works (analyze still validates input)",
          client.post("/api/analyze", json={"geometry": {"type": "Point"}}).status_code == 400)
    check("33. too-long question -> 400",
          client.post("/api/ai/ask", json={"question": "x" * 501}, headers=auth_a).status_code == 400)
    check("34. empty question -> 400",
          client.post("/api/ai/ask", json={"question": "  "}, headers=auth_a).status_code == 400)

    fake = FakeGemini(tool_call("get_my_fields"), text("You have field-1 and field-2. Confirm in person."))
    assistant.call_gemini = fake
    r = client.post("/api/ai/ask", json={"question": "What fields do I have?", "geometry": SCREEN,
                                         "as_of": "2026-08-15"}, headers={"Authorization": f"Bearer {token_a}"})
    result = fake.sent[1][-1]["parts"][0]["functionResponse"]["response"]["result"]
    check("35. logged in: the endpoint answers from Alice's own fields only",
          r.status_code == 200 and [f["field_id"] for f in result["fields"]] == ["screen", "field-1", "field-2"])
    check("36. the answer carries the 'Confirm in person' label",
          r.json()["label"] == "AI-generated explanation based on SpectralTurf AI data. Confirm in person.")
    assistant.limiter = assistant.RateLimiter(per_minute=2)
    assistant.call_gemini = lambda contents: text("Not enough data.")
    codes = [client.post("/api/ai/ask", json={"question": "Hi", "as_of": "2026-08-15"}, headers=auth_a).status_code
             for _ in range(3)]
    check("37. endpoint rate limit -> 429 with a message", codes == [200, 200, 429])
    main.app.dependency_overrides.clear()
    if saved_key is not None:
        os.environ["GEMINI_API_KEY"] = saved_key
    db.close()

# ---- 7. Photos (added 2026-11-22) ----
import base64
import io

from PIL import Image

big = Image.new("RGB", (3000, 2000), (60, 140, 50))
exif = Image.Exif()
exif[0x8825] = {1: "N", 2: (39.0, 38.0, 0.0)}  # a fake GPS location
buffer = io.BytesIO()
big.save(buffer, "JPEG", exif=exif.tobytes())
photo_b64 = base64.b64encode(buffer.getvalue()).decode()
cleaned = Image.open(io.BytesIO(base64.b64decode(assistant.clean_photo(photo_b64))))
check("38. a photo is shrunk to 1024 px and its hidden GPS/EXIF data is removed",
      max(cleaned.size) == 1024 and not cleaned.getexif())
check("39. a 'data:image/jpeg;base64,' prefix is accepted",
      assistant.clean_photo("data:image/jpeg;base64," + photo_b64))


def photo_error(data):
    try:
        assistant.clean_photo(data)
    except assistant.AssistantError as e:
        return str(e)
    return ""


gif = io.BytesIO()
Image.new("RGB", (10, 10)).save(gif, "GIF")
check("40. not a picture -> friendly error", "could not be read" in photo_error(base64.b64encode(b"hello").decode()))
check("41. other formats (GIF) are refused", "JPEG, PNG or WebP" in photo_error(base64.b64encode(gif.getvalue()).decode()))
check("42. too-big files are refused",
      "too big" in photo_error(base64.b64encode(b"x" * (assistant.MAX_PHOTO_BYTES + 1)).decode()))

# Changed 2026-11-26 (student request): the photo is NO LONGER sent to Gemini. Only our photo
# classifier's RESULT is available, through the classify_photo tool (more in test_photo_classify.py).
import photo_classifier  # noqa: E402
fake_info = {"classes": ["healthy", "drought", "fungal_disease", "insect_damage", "wear", "dormant"],
             "uncertain_cutoff": 0.75, "uncertain_label": "Uncertain — inspect in person"}
photo_result = photo_classifier.result_from_probabilities([0.9, 0.05, 0.02, 0.01, 0.01, 0.01], fake_info,
                                                          today=date(2026, 7, 1))
visitor = assistant.Context(False, [], None, None, AS_OF)
fake = FakeGemini(text("I can't see photos. Check it in person."))
reply = assistant.ask("What is in my photo?", visitor, call=fake, photo=photo_result)
first = fake.sent[0][0]["parts"]
check("43. the photo is NOT sent to Gemini (text only); it is told to call classify_photo",
      len(first) == 1 and "inlineData" not in json.dumps(fake.sent) and reply["photo_used"]
      and "classify_photo" in first[0]["text"])
diagnosis = text("This looks like dollar spot.")
check("44. naming a disease from a photo is blocked",
      assistant.ask("What is it?", visitor, call=FakeGemini(diagnosis, diagnosis), photo=photo_result)["status"] == "blocked")
check("45. saying it CAN'T identify diseases is fine",
      assistant.ask("What is it?", visitor, photo=photo_result, call=FakeGemini(
          text("I can't identify diseases from a photo. Check the brown area in person.")))["status"] == "ok")
assistant.limiter = assistant.RateLimiter()
main.app.dependency_overrides[main.required_user] = lambda: {"id": 1, "username": "photo_tester"}  # login required since 2026-11-25 (Version 2)
main.app.dependency_overrides[main.get_db] = lambda: accounts.connect(":memory:")  # never the real database
r = TestClient(main.app).post("/api/ai/ask", json={"question": "Hi", "photo": base64.b64encode(b"nope").decode()})
main.app.dependency_overrides.clear()
check("46. endpoint: a bad photo -> 400 with a friendly message", r.status_code == 400 and "photo" in r.json()["detail"])

print(f"\nAll {passed} assistant tests passed.")
