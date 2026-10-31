# Stage 9 — AI Photo Check (for WAICY, due Nov 29, 2026)

> Put this file in `D:\Lavi\SpectralTurf\docs\`. Claude Code: read this file and CLAUDE.md
> before starting. Work ONE step at a time. After each step, stop, tell Lavi what changed,
> give the exact command to test it, and what success looks like. Keep code beginner-readable.

## The idea (one sentence)
The satellite shows **where** to look; the AI photo check helps explain **what is there**:
a crew member photographs a flagged spot, and an image model suggests whether it looks like
healthy turf, dry/stressed turf, worn/bare turf, or non-turf, with a confidence score.

## Why this design
- **Real AI, explainable:** CLIP (an open-source vision model from OpenAI) turns each photo
  into a list of numbers (an "embedding"). We first test CLIP with no training ("zero-shot"),
  then train our own small classifier (logistic regression) on top of the embeddings using
  Lavi's own labeled photos, and compare the two.
- **Free and local:** runs on CPU on Lavi's PC. No paid API, no new secret keys.
- **Measurable:** we report accuracy on photos the model never saw, from fields it never saw.

## Classes (keep it to 4)
| Label | What it means |
|---|---|
| `healthy` | Green, dense turf |
| `dry_stressed` | Thin, straw/yellow, dry-looking turf (still grass) |
| `worn_bare` | Grass worn away, exposed soil from traffic (goal mouths, sidelines) |
| `non_turf` | Dirt infield, track, pavement, artificial turf |

Any prediction under the confidence cutoff (start at 0.60, tune in Step 3) is shown as
**"Uncertain — inspect in person."**

---

## Non-negotiable rules for this stage (add these to CLAUDE.md)
- The photo AI gives a **suggestion with a confidence**, never a diagnosis. UI text must say so.
- Never invent accuracy numbers. Only report numbers printed by `evaluate.py`.
- Train/test split must be **by field/site**, not random by photo (photos of the same field
  in both sets would make accuracy look better than it is).
- Uploaded photos are **not saved** by default (matches the Take9 security answer).
  Only save if the user ticks "Allow this photo to improve the model," and strip GPS/EXIF first.
- Validate uploads: images only (jpg/png/webp), max 10 MB.
- Dormancy warning: in late fall/winter Colorado grass turns brown naturally. Record the date
  of every photo; the UI should note that brown turf in the off-season may be normal dormancy.

---

## Step 1 — Photo dataset setup
**Files:** `ml/data/<label>/` folders, `ml/photos.csv`, `ml/README.md`
- Create folders: `ml/data/healthy`, `ml/data/dry_stressed`, `ml/data/worn_bare`, `ml/data/non_turf`.
- `photos.csv` columns: `filename,label,site,date,notes`.
- Script `ml/check_dataset.py`: counts photos per label and per site, flags missing rows,
  unreadable images, and labels with fewer than 2 sites.
- **Lavi's job (the most important part):** take photos at 4+ different fields.
  Goal: 30–50 per label, from at least 3 sites each. Phone camera, ~1–2 m above the grass,
  pointing down, daylight. Label them yourself.
- **Success:** `python ml/check_dataset.py` prints a clean table with counts.

## Step 2 — Zero-shot baseline (no training)
**Files:** `ml/clip_model.py`, `ml/zero_shot.py`
- Install (CPU): `pip install torch --index-url https://download.pytorch.org/whl/cpu`
  then `pip install transformers pillow scikit-learn joblib`.
- Load `openai/clip-vit-base-patch32` with Hugging Face `transformers`.
- Compare each photo to text prompts such as "a photo of healthy green grass",
  "a photo of dry yellow stressed grass", "a photo of worn grass with bare soil",
  "a photo of a dirt infield or artificial turf". Pick the best match.
- Print accuracy + a confusion matrix.
- **Success:** a baseline accuracy number Lavi can write down (whatever it is — low is fine).

## Step 3 — Train our own classifier (the main AI result)
**Files:** `ml/train.py`, `ml/evaluate.py`, `ml/model/turf_photo_clf.joblib`
- Compute a CLIP image embedding for every photo (cache to `ml/embeddings.npz`).
- Train logistic regression on the embeddings.
- **Split by site** (`GroupKFold` or hold out whole sites) so test fields are unseen.
- `evaluate.py` prints: accuracy, per-class precision/recall, confusion matrix, and
  zero-shot vs. trained comparison. Saves results to `ml/results.md` with the date.
- Choose the "uncertain" confidence cutoff from the results; report how many photos
  fall below it.
- **Success:** trained model beats zero-shot on unseen sites, or we honestly report it didn't.

## Step 4 — Backend endpoint
**Files:** `backend/photo_ai.py`, update `backend/main.py`, `backend/test_photo_ai.py`
- `POST /api/photo/analyze` (multipart image) → JSON:
  `{label, confidence, probabilities: {...}, uncertain: bool, note}`.
- Load the model once at startup. Validate type/size. Do not write the photo to disk.
- Tests: wrong file type rejected, too-large file rejected, a sample image returns all 4
  probabilities summing to ~1.
- **Success:** works from http://localhost:8000/docs with a test photo.

## Step 5 — Frontend "Check a spot with a photo"
**Files:** new React component in the results panel
- Button opens the camera on phones (`<input type="file" accept="image/*" capture="environment">`).
- Shows: photo preview, top label, confidence bar, all 4 probabilities, and the text
  "AI suggestion — confirm in person." Shows "Uncertain — inspect in person" below cutoff.
- Off-season note when the date is Nov–Mar.
- **Success:** upload a photo → result appears in under ~5 seconds.

## Step 6 — Wrap-up for WAICY
- Update README: what the model is, how it was trained, dataset size, results from
  `ml/results.md`, limitations (small dataset, Colorado only, season effects, 4 classes).
- Add 2–3 slides: pipeline (satellite → flagged zone → photo → AI suggestion),
  results table (zero-shot vs. trained, on unseen sites), limitations.
- Record a demo: flagged field → walk to the spot → photo → AI result.

---

## Suggested schedule
| Dates | Step |
|---|---|
| Oct 31 – Nov 6 | Step 1 + start taking photos (weekends: visit fields) |
| Nov 7 – Nov 10 | Step 2 |
| Nov 11 – Nov 16 | Step 3 (keep adding photos) |
| Nov 17 – Nov 21 | Steps 4–5 |
| Nov 22 – Nov 28 | Step 6, buffer, submit |

## What Lavi should be able to explain to judges
1. What an embedding is (CLIP turns a photo into numbers that capture what it looks like).
2. Zero-shot vs. trained, and why the trained one should be better.
3. Why the split is by site, and what the accuracy number means.
4. Why the app says "suggestion" and "uncertain" instead of a diagnosis.
