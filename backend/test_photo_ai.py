"""
test_photo_ai.py - Checks for POST /api/photo/analyze, using GENERATED test images from
backend/test_images/ (flat colors, not turf photos). The AI's answers for these images mean
nothing; the tests only check the rules: file checks, probabilities, privacy, and wording.

Needs the photo AI libraries (see ml/README.md). Loads the CLIP model, so it takes a few seconds.

Run (in the backend folder):
    python test_images/make_test_images.py   (once)
    python test_photo_ai.py
"""

import io
import tempfile
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient
from PIL import Image

import main
import photo_ai

TEST_IMAGES = Path(__file__).resolve().parent / "test_images"
client = TestClient(main.app)
passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def upload(content, filename="photo.png", allow_training=False):
    return client.post(
        "/api/photo/analyze",
        files={"photo": (filename, content)},
        data={"allow_training": "true" if allow_training else "false"},
    )


def image_bytes(file_format, color=(60, 140, 50), size=(32, 32)):
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, file_format)
    return buffer.getvalue()


green = (TEST_IMAGES / "TEST_IMAGE_green.png").read_bytes()
gps_photo = (TEST_IMAGES / "TEST_IMAGE_with_fake_gps.jpg").read_bytes()

# Keep the real ml/inbox and ml/model out of the tests.
temp = tempfile.TemporaryDirectory()
photo_ai.INBOX_DIR = Path(temp.name) / "inbox"
photo_ai.MODEL_PATH = Path(temp.name) / "no_model_here.joblib"
photo_ai.model.cache_clear()

# ---- Upload checks (these never reach the AI) ----
response = upload(b"this is just text, not a photo", "notes.png")
check("1. a text file is rejected, even when named .png",
      response.status_code == 400 and "isn't a readable image" in response.json()["detail"])

response = upload(image_bytes("GIF"), "anim.gif")
check("2. a GIF is rejected (only jpg/png/webp)",
      response.status_code == 400 and "GIF" in response.json()["detail"])

response = upload(b"", "empty.jpg")
check("3. an empty file is rejected", response.status_code == 400)

too_big = image_bytes("PNG") + b"\0" * (photo_ai.MAX_BYTES + 10)
response = upload(too_big, "huge.png")
check("4. a file over 10 MB is rejected with 413", response.status_code == 413)

# ---- The AI answer (zero-shot, because no trained model exists here) ----
response = upload(green, "TEST_IMAGE_green.png")
body = response.json()
check("5. a PNG gets an answer", response.status_code == 200)
check("6. all 4 probabilities, adding up to about 1",
      set(body["probabilities"]) == set(photo_ai.LABELS)
      and abs(sum(body["probabilities"].values()) - 1) < 0.01)
check("7. label = the most likely class, confidence = its probability",
      body["label"] == max(body["probabilities"], key=body["probabilities"].get)
      and body["confidence"] == body["probabilities"][body["label"]])
check("8. without a trained model it says 'zero-shot (not yet trained)'",
      body["method"] == "zero-shot (not yet trained)")
check("9. 'uncertain' follows the cutoff", body["uncertain"] == (body["confidence"] < body["cutoff"]))
check("10. the note says it is a suggestion, not a diagnosis", "not a diagnosis" in body["note"])

for file_format in ["JPEG", "WEBP"]:
    response = upload(image_bytes(file_format), f"photo.{file_format.lower()}")
    check(f"11. a {file_format} is accepted", response.status_code == 200)

# ---- Dates and the dormancy note ----
body = upload(gps_photo, "TEST_IMAGE_with_fake_gps.jpg").json()
check("12. the date inside the photo is used (2026-01-15)",
      body["photo_date"] == "2026-01-15" and body["date_source"] == "photo")
check("13. a January photo gets the off-season dormancy note",
      body["off_season"] and "dormancy" in body["note"])
summer = photo_ai.analyze(green, today=__import__("datetime").date(2026, 7, 1))
check("14. a July photo gets no dormancy note", not summer["off_season"] and "dormancy" not in summer["note"])

# ---- Privacy: nothing kept unless allowed; GPS removed when kept ----
upload(gps_photo, "TEST_IMAGE_with_fake_gps.jpg", allow_training=False)
check("15. photos are NOT saved by default", not photo_ai.INBOX_DIR.exists())

body = upload(gps_photo, "TEST_IMAGE_with_fake_gps.jpg", allow_training=True).json()
saved = list(photo_ai.INBOX_DIR.glob("*.jpg"))
check("16. with permission, exactly one copy is saved", body["saved_for_training"] and len(saved) == 1)
with Image.open(saved[0]) as kept:
    exif = kept.getexif()
    check("17. the saved copy has no GPS or other EXIF metadata", len(exif) == 0 and not kept.info.get("exif"))
check("18. the saved file name keeps the photo's date", saved[0].name.startswith("2026-01-15_"))

# ---- With a trained model (a throwaway one, trained in a temp folder on test images) ----
import joblib  # noqa: E402

from train import make_classifier  # noqa: E402 (from ml/, via photo_ai's path setup)

embeddings = np.vstack([photo_ai.clip_model.embed_images([Image.open(TEST_IMAGES / name).convert("RGB")])
                        for name in ["TEST_IMAGE_green.png", "TEST_IMAGE_straw.png",
                                     "TEST_IMAGE_soil.png", "TEST_IMAGE_gray.png"]] * 2)
throwaway = make_classifier().fit(embeddings, photo_ai.LABELS * 2)
photo_ai.MODEL_PATH = Path(temp.name) / "throwaway_test_model.joblib"
joblib.dump({"classifier": throwaway, "cutoff": 0.6, "photos": 8, "sites": 1,
             "trained_on": "2026-10-31"}, photo_ai.MODEL_PATH)
photo_ai.model.cache_clear()
body = upload(green, "TEST_IMAGE_green.png").json()
check("19. when a trained model exists, it is used and named",
      body["method"].startswith("trained classifier") and abs(sum(body["probabilities"].values()) - 1) < 0.01)

# ---- The satellite part still works ----
check("20. the rest of the app still answers", client.get("/api/health").json() == {"status": "ok"})

photo_ai.model.cache_clear()
temp.cleanup()
print(f"\nAll {passed} photo AI tests passed.")
