"""
test_predict.py - Offline checks for backend/predict.py (Stage 10). No network is used:
downloads are replaced by small MADE-UP inputs that only test the rules. Numbers from these
fake inputs mean nothing and are never reported.

Run from the backend folder:   python test_predict.py
"""

import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np

import accounts
import predict

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def square(west, south, size=0.002):
    ring = [[west, south], [west + size, south], [west + size, south + size], [west, south + size], [west, south]]
    return {"type": "Polygon", "coordinates": [ring]}


# ---- A fake model and fake downloads ----
class FakeModel:
    """Predicts previous NDVI + `change` (column 0 is prev_ndvi)."""
    change = 0.0

    def predict(self, X):
        return X[:, 0] + self.change


fake_model = FakeModel()
wide = {name: [-1e9, 1e9] for name in predict.train.MODEL_FEATURES}
fake_bundle = {"model": fake_model, "features": predict.train.MODEL_FEATURES, "typical_error": 0.05,
               "weather_cutoff": 0.10, "feature_ranges": wide}
predict.load_model = lambda: fake_bundle

ndvi_rows = []
weather = {(date(2025, 5, 1) + timedelta(days=k)).isoformat(): (1.0, 25.0, 4.0) for k in range(200)}
downloads = {"ndvi": 0, "weather": 0}


def fake_fetch_ndvi(geometry, start, end):
    downloads["ndvi"] += 1
    return [r for r in ndvi_rows if str(start) <= r["date"] <= str(end)]


def fake_fetch_weather(lon, lat, start, end):
    downloads["weather"] += 1
    return weather, "fake weather"


predict.fetch_ndvi = fake_fetch_ndvi
predict.fetch_weather = fake_fetch_weather
field = square(-104.88, 39.63)

# ---- Season ----
r = predict.weather_check(field, [], date(2025, 11, 15))
check("1. off-season (November) -> 'Off-season' message, no numbers, nothing downloaded",
      r["status"] == "off_season" and r["message"] == predict.OFF_SEASON and "actual_ndvi" not in r
      and downloads == {"ndvi": 0, "weather": 0})
check("2. April and October are in season; March is not",
      predict.in_season(date(2025, 4, 1)) and predict.in_season(date(2025, 10, 31))
      and not predict.in_season(date(2025, 3, 31)))

# ---- Not enough clear images ----
ndvi_rows[:] = [{"date": "2025-07-20", "ndvi_mean": 0.7, "clear_fraction": 1.0}]
r = predict.weather_check(field, [], date(2025, 7, 25))
check("3. fewer than 2 clear images -> insufficient evidence, no numbers",
      r["status"] == "insufficient_evidence" and "actual_ndvi" not in r)

# ---- Expected vs actual ----
ndvi_rows[:] = [{"date": "2025-07-10", "ndvi_mean": 0.70, "clear_fraction": 1.0},
                {"date": "2025-07-20", "ndvi_mean": 0.55, "clear_fraction": 1.0}]
fake_model.change = 0.0  # expects "same as last time" = 0.70; actual 0.55 is 0.15 below
r = predict.weather_check(field, [], date(2025, 7, 25))
check("4. actual far below expected (0.15 > cutoff 0.10) -> weather does NOT explain this",
      r["check"]["weather_explains"] is False and r["check"]["difference"] == -0.15
      and "inspect irrigation" in r["check"]["message"])
fake_model.change = -0.10  # the model expects a 0.10 drop from the weather -> expected 0.60
r = predict.weather_check(field, [], date(2025, 7, 25))
check("5. drop the model expected from the weather -> weather explains this",
      r["check"]["weather_explains"] is True and r["check"]["expected_ndvi"] == 0.6)
check("6. latest image and dates come from the real (here: fake) data",
      r["last_image_date"] == "2025-07-20" and r["previous_image_date"] == "2025-07-10" and r["actual_ndvi"] == 0.55)

# ---- Next-week risk ----
check("7. risk levels: drop >= cutoff High, >= typical error Medium, else Low",
      predict.risk_level(-0.12, fake_bundle) == "High" and predict.risk_level(-0.06, fake_bundle) == "Medium"
      and predict.risk_level(-0.01, fake_bundle) == "Low" and predict.risk_level(0.05, fake_bundle) == "Low")
fake_model.change = -0.15
r = predict.weather_check(field, [], date(2025, 7, 25))
check("8. next-week prediction is for 7 days after 'as of'",
      r["risk_next_week"]["target_date"] == "2025-08-01" and r["risk_next_week"]["level"] == "High")
fake_bundle["feature_ranges"] = {**wide, "days_since_prev": [1, 10]}  # 2025-08-01 is 12 days after the image
r = predict.weather_check(field, [], date(2025, 7, 25))
check("9. input outside the training range -> risk 'Unknown', NO number",
      r["risk_next_week"]["level"] == "Unknown" and "predicted_ndvi" not in r["risk_next_week"]
      and "days since the last clear image" in r["risk_next_week"]["message"])
fake_bundle["feature_ranges"] = wide
del weather["2025-07-15"]
r = predict.weather_check(field, [], date(2025, 7, 25))
check("10. a missing weather day -> not checked, never filled in",
      r["check"]["status"] == "insufficient_evidence")
weather["2025-07-15"] = (1.0, 25.0, 4.0)

# ---- Excluded areas become holes ----
inner = square(-104.8795, 39.6305, 0.0005)
shape, note = predict.field_geometry(field, [inner])
check("11. an exclusion inside the outline becomes a hole", len(shape["coordinates"]) == 2 and note is None)
shape, note = predict.field_geometry(field, [square(-104.8790, 39.6290, 0.003)])
check("12. an exclusion reaching outside -> not used, and the user is told",
      len(shape["coordinates"]) == 1 and "NOT used" in note)
shape, note = predict.field_geometry(field, [inner, square(-104.8793, 39.6307, 0.0005)])
check("13. overlapping exclusions -> not used, and the user is told", len(shape["coordinates"]) == 1 and note)

# ---- Step 8: My Fields ranking ----
with tempfile.TemporaryDirectory() as tmp:
    db = accounts.connect(Path(tmp) / "test.db")
    alice, bob = accounts.sign_up(db, "alice_1", "password123"), accounts.sign_up(db, "bob_1", "password123")
    alice_id, bob_id = accounts.user_for_token(db, alice)["id"], accounts.user_for_token(db, bob)["id"]
    fake_result = {"observation": {"date": "2025-07-20", "tile_cloud_cover": 0},
                   "pixels": {"valid_after_masking": 100, "valid_fraction": 1.0},
                   "ndvi": {"median": 0.7}, "ndmi": {"median": 0.2}, "status": "ok"}
    fields = {"A": square(-104.80, 39.60), "B": square(-104.81, 39.61), "C": square(-104.82, 39.62)}
    for name in ("A", "B", "C"):
        accounts.save_analysis(db, alice_id, name, fields[name], [], "2025-06-01", "2025-08-31", fake_result)
    accounts.save_analysis(db, alice_id, "A again", fields["A"], [], "2025-06-01", "2025-08-31", fake_result)
    accounts.save_analysis(db, bob_id, "Bob's field", square(-104.90, 39.70), [], "2025-06-01", "2025-08-31", fake_result)

    def fake_check(geometry, exclusions, as_of):
        name = {str(v): k for k, v in fields.items()}.get(str(geometry))
        if name == "C":
            raise predict.PredictError("Copernicus answered HTTP 500.")
        explains = name != "B"  # B: weather does NOT explain it -> should come first
        return {"status": "ok", "check": {"status": "ok", "weather_explains": explains,
                                          "difference": -0.2 if name == "B" else 0.0},
                "risk_next_week": {"level": "Low"}}

    ranked = predict.rank_my_fields(accounts.list_analyses(db, alice_id), date(2025, 7, 25), check=fake_check)
    names = [e["field"]["name"] for e in ranked["fields"]]
    check("14. ranking: 'weather does NOT explain' first, failed checks last (with their reason)",
          names[0] == "B" and names[-1] == "C" and ranked["fields"][-1]["result"]["status"] == "error")
    check("15. a field saved twice appears once (newest name kept)",
          len(names) == 3 and "A again" in names and "A" not in names)
    check("16. a user only ever sees their OWN fields", "Bob's field" not in names)
    bob_ranked = predict.rank_my_fields(accounts.list_analyses(db, bob_id), date(2025, 7, 25), check=fake_check)
    check("17. ...and Bob only sees his", [e["field"]["name"] for e in bob_ranked["fields"]] == ["Bob's field"])
    off = predict.rank_my_fields(accounts.list_analyses(db, alice_id), date(2025, 12, 1), check=fake_check)
    check("18. off-season ranking -> message, no checks", off["status"] == "off_season" and off["fields"] == [])
    before = db.execute("SELECT COUNT(*) FROM saved_analyses").fetchone()[0]
    predict.rank_my_fields(accounts.list_analyses(db, alice_id), date(2025, 7, 25), check=fake_check)
    check("19. ranking only READS the accounts database",
          db.execute("SELECT COUNT(*) FROM saved_analyses").fetchone()[0] == before)
    empty = predict.rank_my_fields([], date(2025, 7, 25), check=fake_check)
    check("20. no saved fields -> a helpful message", empty["status"] == "no_fields")
    db.close()

# ---- The endpoint: not logged in ----
from fastapi.testclient import TestClient  # noqa: E402
import main  # noqa: E402

client = TestClient(main.app)
response = client.post("/api/ai/my-fields", json={"as_of": "2025-07-25"})
check("21. /api/ai/my-fields without logging in -> 401 with the 'Log in' message",
      response.status_code == 401 and "Log in and analyze fields" in response.json()["detail"])
response = client.post("/api/ai/my-fields", json={"as_of": (date.today() + timedelta(days=3)).isoformat()},
                       headers={"Authorization": "Bearer not-a-real-token"})
check("22. a fake token is treated as logged out", response.status_code == 401)

# ---- Step 9: What if? ----
real = {(date(2025, 6, 1) + timedelta(days=k)).isoformat(): (5.0, 20.0, 3.0) for k in range(60)}
made_up = predict.scenario_weather(real, date(2025, 7, 1), {"dry_days": 4, "rain_mm": 20, "avg_high_c": 30})
scenario_days = [made_up[(date(2025, 7, 1) + timedelta(days=k)).isoformat()] for k in range(14)]
check("23. scenario: last 4 of 14 days dry, 20 mm spread over the other 10, high 30 °C every day",
      [d[0] for d in scenario_days] == [2.0] * 10 + [0.0] * 4 and all(d[1] == 30.0 for d in scenario_days))
check("24. scenario: weather BEFORE the latest image stays real; the real data is not changed",
      made_up["2025-06-30"] == (5.0, 20.0, 3.0) and real["2025-07-05"] == (5.0, 20.0, 3.0))
slope, intercept, r2 = predict.et0_from_temperature()
check("25. ET0 from temperature: fitted to the real training weather, hotter = more water demand",
      slope > 0 and 0 < r2 < 1 and scenario_days[0][2] == max(0.0, slope * 30 + intercept))
try:
    predict.scenario_weather(real, date(2025, 7, 1), {"dry_days": 14, "rain_mm": 5, "avg_high_c": 30})
    refused = False
except predict.PredictError:
    refused = True
check("26. 14 dry days + some rain is refused (impossible scenario)", refused)

ndvi_rows[:] = [{"date": "2025-07-20", "ndvi_mean": 0.70, "clear_fraction": 1.0}]
fake_model.change = -0.07
scenario = {"dry_days": 7, "rain_mm": 10, "avg_high_c": 30}
r = predict.what_if(field, [], date(2025, 7, 25), scenario)
check("27. what-if predicts 14 days after the latest image, with a risk level and the label",
      r["status"] == "ok" and r["target_date"] == "2025-08-03" and r["risk_level"] == "Medium"
      and r["label"] == "Scenario estimate from the AI model, not a forecast.")
fake_bundle["feature_ranges"] = {**wide, "tmax_7": [0, 25]}
r = predict.what_if(field, [], date(2025, 7, 25), scenario)
check("28. scenario outside the training range -> warning and NO number",
      r["status"] == "outside_training" and "predicted_ndvi" not in r and "temperature" in r["message"])
fake_bundle["feature_ranges"] = wide
check("29. what-if off-season -> 'Off-season' message",
      predict.what_if(field, [], date(2025, 12, 1), scenario)["status"] == "off_season")
limits = predict.what_if_limits({"feature_ranges": {**wide, "rain_14": [0, 145.1], "tmax_7": [1.8, 36.8],
                                                     "tmax_14": [5.2, 35.3]}})
check("30. slider limits come from the training ranges", limits["rain_mm"] == [0, 145]
      and limits["avg_high_c"] == [6, 35] and limits["dry_days"] == [0, 14])
response = client.post("/api/ai/what-if", json={"dry_days": 3, "rain_mm": 0, "avg_high_c": 30,
                                               "include_my_fields": True})
check("31. what-if for My Fields without logging in -> 401", response.status_code == 401)
response = client.post("/api/ai/what-if", json={"dry_days": 14, "rain_mm": 5, "avg_high_c": 30})
check("32. what-if endpoint refuses 14 dry days + rain (400)", response.status_code == 400)

# ---- Version 3 model (2026-11-07): 7-20 days ahead, more inputs ----
from build_dataset_v3 import ALL_FEATURES  # noqa: E402


class FakeModelV3:
    """Predicts start NDVI + `change` (v3 models get every ALL_FEATURES column)."""
    change = 0.0

    def predict(self, X):
        return X[:, ALL_FEATURES.index("start_ndvi")] + self.change


fake_v3 = FakeModelV3()
wide_v3 = {name: [-1e9, 1e9] for name in ALL_FEATURES}
v3_bundle = {"version": 3, "model": fake_v3, "features": ALL_FEATURES,
             "used_features": [f for f in ALL_FEATURES if not f.startswith("own_")],
             "typical_error": 0.06, "weather_cutoff": 0.12, "feature_ranges": wide_v3,
             "weather_normal": {d: (1.0, 25.0, 4.0) for d in range(1, 367)}}
predict.load_model = lambda: v3_bundle
ndvi_rows[:] = [{"date": "2025-07-01", "ndvi_mean": 0.80, "ndvi_std": 0.05, "clear_fraction": 1.0},
                {"date": "2025-07-08", "ndvi_mean": 0.78, "ndvi_std": 0.05, "clear_fraction": 1.0},
                {"date": "2025-07-15", "ndvi_mean": 0.76, "ndvi_std": 0.05, "clear_fraction": 1.0},
                {"date": "2025-07-20", "ndvi_mean": 0.60, "ndvi_std": 0.05, "clear_fraction": 1.0}]
r = predict.weather_check(field, [], date(2025, 7, 25))
check("33. v3: the latest image is checked against the newest image 7-20 days earlier (not 5 days)",
      r["previous_image_date"] == "2025-07-08" and r["check"]["expected_ndvi"] == 0.78
      and r["check"]["weather_explains"] is False)
check("34. v3: next-week risk and cutoff use the version 3 model's own error",
      r["risk_next_week"]["level"] == "Low" and r["cutoff"] == 0.12)
ndvi_rows[:] = [{"date": "2025-07-15", "ndvi_mean": 0.76, "ndvi_std": 0.05, "clear_fraction": 1.0},
                {"date": "2025-07-20", "ndvi_mean": 0.60, "ndvi_std": 0.05, "clear_fraction": 1.0}]
r = predict.weather_check(field, [], date(2025, 7, 25))
check("35. v3: no image 7-20 days before the latest -> not checked, no expected number",
      r["check"]["status"] == "insufficient_evidence" and "expected_ndvi" not in r["check"])
ndvi_rows[:] = [{"date": "2025-07-20", "ndvi_mean": 0.70, "ndvi_std": 0.05, "clear_fraction": 1.0}]
fake_v3.change = -0.07
r = predict.what_if(field, [], date(2025, 7, 25), scenario)
check("36. v3 what-if: one recent image (no trend) is allowed; Medium risk from the v3 error",
      r["status"] == "ok" and r["predicted_change"] == -0.07 and r["risk_level"] == "Medium")
ndvi_rows[:] = [{"date": "2025-07-20", "ndvi_mean": 0.70, "clear_fraction": 1.0}]  # no pixel spread
r = predict.what_if(field, [], date(2025, 7, 25), scenario)
check("37. v3: a missing input the model always had (image quality) -> no number",
      r["status"] == "outside_training" and "image quality" in r["message"])
predict.load_model = lambda: fake_bundle

real_v3 = predict.joblib.load(predict.MODEL_V3_FILE)
check("38. the saved version 3 model loads in the backend and uses no earlier-year inputs",
      real_v3["version"] == 3 and not any(f.startswith("own_") for f in real_v3["used_features"])
      and 0 < real_v3["typical_error"] < 0.2)

# ---- What-if temperatures limited to what happened in that month (2026-11-07) ----
ranges = predict.month_high_ranges()
check("39. month ranges come from real 2019-2025 weather; August is warmer than April",
      set(range(4, 11)) <= set(ranges) and ranges[8][0] > ranges[4][1] - 5 and ranges[8][1] > ranges[4][1])
aug = predict.what_if_limits({"feature_ranges": {**wide, "rain_14": [0, 145.1], "tmax_7": [1.8, 36.8],
                                                  "tmax_14": [5.2, 35.3]}}, month=8)
check("40. limits with a month: temperature range = that month's real range, inside the training range",
      aug["month"] == "August" and aug["avg_high_c"][0] == predict.month_temperature_limit(8)[0]
      and aug["avg_high_c"][1] <= 35 and "Allowed in August" in aug["month_note"])
check("41. the heat note is always shown under the sliders",
      aug["heat_note"] == "Heat has little effect on watered fields in our data; dry spells matter more.")
low_aug = predict.month_temperature_limit(8)[0]
downloads.update(ndvi=0, weather=0)
r = predict.what_if(field, [], date(2025, 8, 10), {"dry_days": 7, "rain_mm": 10, "avg_high_c": low_aug - 1})
check("42. a temperature that never happened in that month -> no number, nothing downloaded",
      r["status"] == "outside_training" and "predicted_ndvi" not in r and "August" in r["message"]
      and downloads == {"ndvi": 0, "weather": 0})
ndvi_rows[:] = [{"date": "2025-08-05", "ndvi_mean": 0.70, "clear_fraction": 1.0}]
r = predict.what_if(field, [], date(2025, 8, 10), {"dry_days": 7, "rain_mm": 10, "avg_high_c": low_aug})
check("43. the lowest allowed August temperature still gets an estimate", r["status"] == "ok")
response = client.get("/api/ai/what-if/limits", params={"as_of": "2025-08-10"})
check("44. limits endpoint with as_of returns that month's range", response.status_code == 200
      and response.json()["month"] == "August")
response = client.get("/api/ai/what-if/limits")
check("45. limits endpoint without as_of still works as before", response.status_code == 200
      and "month" not in response.json() and response.json()["dry_days"] == [0, 14])

# ---- Steps 6-7: AI Weather Check endpoint + cloudy-day estimate (2026-11-07) ----
predict.load_model = lambda: v3_bundle
fake_v3.change = -0.03
ndvi_rows[:] = [{"date": "2025-07-01", "ndvi_mean": 0.80, "ndvi_std": 0.05, "clear_fraction": 1.0},
                {"date": "2025-07-10", "ndvi_mean": 0.78, "ndvi_std": 0.05, "clear_fraction": 1.0}]
r = predict.weather_check(field, [], date(2025, 7, 19))  # last clear image 9 days ago
est = r["cloudy_estimate"]
check("46. no clear image for 7+ days -> AI estimate labeled 'AI estimate, not a measurement'",
      est["label"] == "AI estimate, not a measurement" and est["status"] == "ok"
      and est["estimated_ndvi"] == 0.75 and est["estimate_date"] == "2025-07-19")
check("47. the estimate shows the last clear image date and the typical error (±0.06)",
      est["last_clear_date"] == "2025-07-10" and est["days_without_clear_image"] == 9
      and est["typical_error"] == 0.06)
check("48. the measured values stay separate from the estimate (actual = last clear image)",
      r["actual_ndvi"] == 0.78 and r["last_image_date"] == "2025-07-10")
r = predict.weather_check(field, [], date(2025, 7, 15))  # 5 days: not cloudy enough
check("49. a clear image less than 7 days old -> no estimate", r["cloudy_estimate"] is None)
v3_bundle["feature_ranges"] = {**wide_v3, "days_ahead": [7, 20]}  # as in the real version 3 model
r = predict.weather_check(field, [], date(2025, 7, 31))  # 21 days: beyond what the model learned
check("50. last clear image more than 20 days ago -> no AI number, explained",
      r["cloudy_estimate"]["status"] == "outside_training" and "estimated_ndvi" not in r["cloudy_estimate"])
v3_bundle["feature_ranges"] = wide_v3
ndvi_rows[:] = [{"date": "2025-07-10", "ndvi_mean": 0.78, "ndvi_std": 0.05, "clear_fraction": 1.0}]
r = predict.weather_check(field, [], date(2025, 7, 19))
check("51. insufficient evidence: the message is unchanged; the estimate is only added beside it",
      r["status"] == "insufficient_evidence"
      and r["message"] == ("Insufficient evidence: fewer than 2 clear satellite images in the "
                           f"{predict.LOOKBACK_DAYS} days before 2025-07-19 (clouds or early season).")
      and r["cloudy_estimate"]["estimated_ndvi"] == 0.75 and "actual_ndvi" not in r)
ndvi_rows[:] = []
r = predict.weather_check(field, [], date(2025, 7, 19))
check("52. no clear image at all -> no estimate (nothing to start from)",
      r["status"] == "insufficient_evidence" and r["cloudy_estimate"] is None)
ndvi_rows[:] = [{"date": d, "ndvi_mean": 0.70, "ndvi_std": 0.05, "clear_fraction": 1.0}
                for d in ("2025-06-20", "2025-06-30", "2025-07-08")]
r = predict.weather_check(field, [], date(2025, 7, 20))
check("53. chart data: every clear image + the AI's expected value from an image 7-20 days earlier",
      [p["date"] for p in r["recent_images"]] == ["2025-06-20", "2025-06-30", "2025-07-08"]
      and [p["date"] for p in r["expected_series"]] == ["2025-06-30", "2025-07-08"]
      and r["expected_series"][0]["expected_ndvi"] == 0.67)
check("54. next week's forecast is shown next to the normal weather for those days",
      r["risk_next_week"]["normal_next_7_days"] == {"days": 7, "rain_mm": 7.0, "avg_high_c": 25.0})
predict.load_model = lambda: fake_bundle
r = predict.weather_check(field, [], date(2025, 7, 20))
check("55. older (version 2) model -> no cloudy estimate", r["cloudy_estimate"] is None)
response = client.post("/api/ai/weather-check", json={"geometry": field, "as_of": "2025-07-20"})
check("56. POST /api/ai/weather-check works without logging in", response.status_code == 200
      and response.json()["status"] == "ok")
response = client.post("/api/ai/weather-check", json={"geometry": field, "as_of": "2025-12-01"})
check("57. weather-check endpoint off-season -> 'Off-season' message",
      response.status_code == 200 and response.json()["message"] == predict.OFF_SEASON)
bad = {"type": "Polygon", "coordinates": [[[-104.88, 39.63], [-104.879, 39.63], [-104.88, 39.63]]]}
response = client.post("/api/ai/weather-check", json={"geometry": bad})
check("58. weather-check endpoint rejects a broken outline (400), like /api/analyze",
      response.status_code == 400)

print(f"\nAll {passed} predict tests passed.")
