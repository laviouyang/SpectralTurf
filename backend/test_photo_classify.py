"""
test_photo_classify.py - Checks for Stage 11 on the website (2026-11-26): "Check a photo"
(POST /api/photo/classify, photo_classifier.py) and the classify_photo tool of Ask SpectralTurf.

Uses the REAL shrunken model (photo_model/, committed) on made-up pictures, so no training photos
are needed. No internet: Gemini is replaced by a fake. A throwaway in-memory database is used.

Run:   python test_photo_classify.py
"""

import io
import json
import os
from datetime import date

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

import accounts
import assistant
import main
import photo_classifier as pc

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def picture(fmt="JPEG", size=(640, 480), color=(60, 140, 50), exif=None):
    rng = np.random.default_rng(0)
    pixels = np.clip(np.array(color) + rng.normal(0, 25, (size[1], size[0], 3)), 0, 255).astype("uint8")
    out = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.fromarray(pixels).save(out, fmt, **kwargs)
    return out.getvalue()


client = TestClient(main.app)
JPEG = {"Content-Type": "image/jpeg"}

# ---- 1. login required ----
r = client.post("/api/photo/classify", content=picture(), headers=JPEG)
check("1. visitors are refused (401 'Please log in first.')", r.status_code == 401)

main.app.dependency_overrides[main.required_user] = lambda: {"id": 1, "username": "photo_tester"}
main.app.dependency_overrides[main.get_db] = lambda: accounts.connect(":memory:")

# ---- 2-4. bad uploads ----
gif = io.BytesIO()
Image.new("RGB", (50, 50)).save(gif, "GIF")
r = client.post("/api/photo/classify", content=gif.getvalue(), headers={"Content-Type": "image/gif"})
check("2. wrong file type (GIF) -> 400 'JPEG, PNG or WebP'", r.status_code == 400 and "JPEG, PNG or WebP" in r.json()["detail"])
r = client.post("/api/photo/classify", content=b"not a picture at all", headers=JPEG)
check("3. not a picture -> 400 friendly message", r.status_code == 400 and "could not be read" in r.json()["detail"])
r = client.post("/api/photo/classify", content=b"x" * (pc.MAX_PHOTO_BYTES + 1), headers=JPEG)
check("4. more than 10 MB -> 413 'too big'", r.status_code == 413 and "too big" in r.json()["detail"])
try:
    pc.classify(b"x" * (pc.MAX_PHOTO_BYTES + 1))
    refused = False
except pc.PhotoError as e:
    refused = e.status == 413
check("5. ...also refused inside photo_classifier (not only by the Content-Length header)", refused)
big_png = io.BytesIO()
Image.new("RGB", (2400, 1800), (60, 140, 50)).save(big_png, "PNG")  # plain color = a small file, many pixels
r = client.post("/api/photo/classify", content=big_png.getvalue(), headers={"Content-Type": "image/png"})
check("6. PNG over 4 megapixels -> 413 (memory limit for the small server)", r.status_code == 413 and "megapixels" in r.json()["detail"])

# ---- 7-10. a real photo through the real model ----
gps = Image.Exif()
gps[0x8825] = {2: (39.0, 38.0, 0.0), 4: (104.0, 52.0, 0.0)}  # GPSInfo: latitude / longitude
gps[0x010F] = "PhoneMaker"
photo = picture(exif=gps)
check("7. (the test photo really has EXIF/GPS data)", Image.open(io.BytesIO(photo)).getexif().get(0x8825) is not None)
cleaned = pc.clean_photo(photo)
check("8. the re-saved copy has no EXIF/GPS data", not cleaned.getexif() and "exif" not in cleaned.info)
files_before = sorted(os.listdir("."))
r = client.post("/api/photo/classify", content=photo, headers=JPEG)
result = r.json()
check("9. a real JPEG -> 200 with all 6 categories", r.status_code == 200 and len(result["classes"]) == 6)
check("10. the percentages add up to exactly 100", sum(c["percent"] for c in result["classes"]) == 100)
top = max(result["classes"], key=lambda c: c["percent"])
check("11. the top category is the biggest percentage", result["top_class"]["percent"] == top["percent"])
check("12. every answer says 'Not a diagnosis — confirm with an expert.'", pc.NOT_A_DIAGNOSIS in result["notes"])
check("13. the photo is never stored (no new files in backend/)", sorted(os.listdir(".")) == files_before)
check("14. 'How accurate is this?' uses the real test results saved with the model",
      result["accuracy"]["test_photos"] == 379 and 0 < result["accuracy"]["accuracy_percent"] <= 100)
for fmt in ("PNG", "WEBP"):
    r = client.post("/api/photo/classify", content=picture(fmt), headers={"Content-Type": f"image/{fmt.lower()}"})
    check(f"15. {fmt} works too", r.status_code == 200 and sum(c["percent"] for c in r.json()["classes"]) == 100)

# ---- 16-20. rounding, Uncertain, dormancy note (no model needed) ----
info = {"classes": ["healthy", "drought", "fungal_disease", "insect_damage", "wear", "dormant"],
        "uncertain_cutoff": 0.75, "uncertain_label": "Uncertain — inspect in person"}
rng = np.random.default_rng(2026)
sums = {sum(pc.percentages(p)) for p in rng.dirichlet(np.ones(6) * 0.3, 2000)}
check("16. percentages add up to 100 for 2,000 random results", sums == {100})
low = pc.result_from_probabilities([0.60, 0.30, 0.04, 0.03, 0.02, 0.01], info, date(2026, 7, 1))
check("17. below the 75% cutoff -> 'Uncertain — inspect in person'",
      low["uncertain"] and low["answer"] == "Uncertain — inspect in person")
high = pc.result_from_probabilities([0.05, 0.80, 0.05, 0.04, 0.03, 0.03], info, date(2026, 7, 1))
check("18. at/above the cutoff -> 'Looks most like: Drought stress (80%)'",
      not high["uncertain"] and high["answer"] == "Looks most like: Drought stress (80%)")
winter = pc.result_from_probabilities([0.05, 0.80, 0.05, 0.04, 0.03, 0.03], info, date(2026, 12, 5))
check("19. November-March adds 'Brown grass may be normal winter dormancy.'",
      pc.DORMANCY_NOTE in winter["notes"] and pc.DORMANCY_NOTE not in high["notes"])
check("20. ...for every month from November to March, and no other month",
      [m for m in range(1, 13) if pc.DORMANCY_NOTE in
       pc.result_from_probabilities([1, 0, 0, 0, 0, 0], info, date(2026, m, 1))["notes"]] == [1, 2, 3, 11, 12])


# ---- 21-29. Ask SpectralTurf: classify_photo tool, the photo never goes to Gemini ----
class FakeGemini:
    def __init__(self, *messages):
        self.messages, self.sent = list(messages), []

    def __call__(self, contents):
        self.sent.append(json.loads(json.dumps(contents)))
        return self.messages.pop(0)


def tool_call(name, **args):
    return {"role": "model", "parts": [{"functionCall": {"name": name, "args": args, "id": "c1"}}]}


def text(answer):
    return {"role": "model", "parts": [{"text": answer}]}


fungal = pc.result_from_probabilities([0.03, 0.02, 0.90, 0.03, 0.01, 0.01], info, date(2026, 7, 1))
ctx = assistant.Context(True, [], None, None, date(2026, 7, 1))
check("21. classify_photo without a photo -> 'No photo is attached' error",
      "No photo" in assistant.run_tool("classify_photo", {"photo": "attached"}, ctx)["error"])
ctx.photo_result = fungal
tool = assistant.run_tool("classify_photo", {"photo": "attached"}, ctx)
check("22. classify_photo gives only the result: percentages, top category, Uncertain",
      tool["top_category"] == "Fungal disease" and tool["top_percent"] == 90 and tool["uncertain"] is False
      and sum(tool["categories_percent"].values()) == 100)

good = "The photo looks most like Fungal disease (90%) - not a diagnosis, confirm with an expert. Check it in person."
fake = FakeGemini(tool_call("classify_photo", photo="attached"), text(good))
reply = assistant.ask("What does my photo show?", assistant.Context(True, [], None, None, date(2026, 7, 1)),
                      call=fake, photo=fungal)
check("23. approved wording ('looks most like ... not a diagnosis, confirm with an expert') passes",
      reply["status"] == "ok" and reply["answer"] == good and "classify_photo" in reply["tools_used"])
bare = text("The photo looks most like Fungal disease (90%). Check it in person.")
reply = assistant.ask("What does my photo show?", assistant.Context(True, [], None, None, date(2026, 7, 1)),
                      call=FakeGemini(tool_call("classify_photo"), bare, tool_call("classify_photo"), bare), photo=fungal)
check("24. a photo result WITHOUT 'not a diagnosis' / 'expert' is blocked", reply["status"] == "blocked")
named = text("The photo looks most like Fungal disease (90%), probably anthracnose - not a diagnosis, "
             "confirm with an expert.")
reply = assistant.ask("Which disease is it?", assistant.Context(True, [], None, None, date(2026, 7, 1)),
                      call=FakeGemini(tool_call("classify_photo"), named, tool_call("classify_photo"), named), photo=fungal)
check("25. naming a specific disease beyond our categories (anthracnose) is blocked", reply["status"] == "blocked")
check("26. ...and so are pest names (grubs)", assistant.SPECIFIC_NAME_RE.search("It may have grubs.") is not None)
made_up = text("The photo looks most like Fungal disease (95%) - not a diagnosis, confirm with an expert.")
reply = assistant.ask("What does my photo show?", assistant.Context(True, [], None, None, date(2026, 7, 1)),
                      call=FakeGemini(tool_call("classify_photo"), made_up, tool_call("classify_photo"), made_up),
                      photo=fungal)
check("27. a percentage that is not in the tool result (95% instead of 90%) is blocked", reply["status"] == "blocked")

# The endpoint: the real classifier runs on the chat photo; Gemini gets text only.
import base64  # noqa: E402
real_call = assistant.call_gemini
fake = FakeGemini(tool_call("classify_photo", photo="attached"),
                  text("The photo check is uncertain - not a diagnosis, confirm with an expert or inspect in person."))
assistant.call_gemini = fake
assistant.limiter = assistant.RateLimiter()
try:
    r = client.post("/api/ai/ask", json={"question": "What does my photo show?",
                                         "photo": base64.b64encode(photo).decode()})
finally:
    assistant.call_gemini = real_call
sent = json.dumps(fake.sent)
check("28. /api/ai/ask with a photo: Gemini never receives the photo (no image data sent)",
      r.status_code == 200 and "inlineData" not in sent and base64.b64encode(photo).decode()[:200] not in sent)
check("29. ...it receives our classifier's result through classify_photo instead",
      "categories_percent" in sent and r.json()["tools_used"] == ["classify_photo"])
r = client.post("/api/ai/ask", json={"question": "Hi", "photo": base64.b64encode(gif.getvalue()).decode()})
check("30. /api/ai/ask with a GIF -> 400 'JPEG, PNG or WebP'", r.status_code == 400 and "JPEG, PNG or WebP" in r.json()["detail"])

main.app.dependency_overrides.clear()
print(f"\nAll {passed} checks passed.")
