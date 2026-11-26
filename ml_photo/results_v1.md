# Stage 11 photo classifier — results v1

Date: 2026-11-25. Made by `ml_photo/train_v1.py` (numbers below are copied from `results_v1.json`).
Image features: CLIP `openai/clip-vit-base-patch32` on CPU. **Research only: a prediction is not a diagnosis.**

## Data

| Class | Photos | Train | Test | Groups (sites / recordings / sources) |
|---|---|---|---|---|
| healthy | 700 | 542 | 158 | 12 |
| drought | 671 | 477 | 194 | 5 |
| fungal_disease | 37 | 29 | 8 | 28 |
| insect_damage | 59 | 44 | 15 | 16 |
| wear | 10 | 8 | 2 | 1 |
| dormant | 10 | 8 | 2 | 1 |

Split (from `ml_photo/check_dataset.py`, saved in `photo_data/split.csv`): train/test **by group**, so a
site, video recording or source article is never in both. Group = metadata `site` if known, else the
recording time in the file name, else the source article, else "unknown". Split methods used:

- dormant: WEAK: one group, split by file order: 10 photos
- drought: by group: 671 photos
- fungal_disease: by group: 37 photos
- healthy: by group: 700 photos
- insect_damage: by group: 59 photos
- wear: WEAK: one group, split by file order: 10 photos

Prompts per class (zero-shot): healthy 2, drought 3, fungal_disease 40, insect_damage 8, wear 2, dormant 2.

## Test results (test photos only)

| | Accuracy | Balanced accuracy | Uncertain rate | Accuracy on answered photos | Accuracy, Uncertain counted wrong |
|---|---|---|---|---|---|
| Baseline: always "healthy" | 41.7% | 16.7% | — | — | — |
| Zero-shot CLIP (no training) | 2.9% | 19.0% | 97.4% (369/379) | 40.0% | 1.1% |
| CLIP + logistic regression | 90.0% | 69.3% | 27.4% (104/379) | 97.1% | 70.4% |

"Accuracy" and "Balanced accuracy" = without the Uncertain option (every photo gets a class).
Balanced accuracy = the average of the per-class recalls, so the big classes do not hide the small ones.

### Zero-shot CLIP — per class (without Uncertain)

| Class | Test photos | Precision | Recall | Recall with Uncertain (answered and right) |
|---|---|---|---|---|
| healthy | 158 | 0.0% | 0.0% | 0.0% |
| drought | 194 | 33.3% | 0.5% | 0.0% |
| fungal_disease | 8 | 2.1% | 100.0% | 50.0% |
| insect_damage | 15 | 100.0% | 13.3% | 0.0% |
| wear | 2 | 0.0% | 0.0% | 0.0% |
| dormant | 2 | 0.0% | 0.0% | 0.0% |

Confusion matrix: `ml_photo/confusion_zeroshot_v1.png` (rows = true class, columns = predicted).

| true \ predicted | healthy | drought | fungal_disease | insect_damage | wear | dormant |
|---|---|---|---|---|---|---|
| healthy | 0 | 0 | 157 | 0 | 1 | 0 |
| drought | 0 | 1 | 193 | 0 | 0 | 0 |
| fungal_disease | 0 | 0 | 8 | 0 | 0 | 0 |
| insect_damage | 0 | 2 | 11 | 2 | 0 | 0 |
| wear | 0 | 0 | 2 | 0 | 0 | 0 |
| dormant | 0 | 0 | 2 | 0 | 0 | 0 |

### CLIP + logistic regression — per class (without Uncertain)

| Class | Test photos | Precision | Recall | Recall with Uncertain (answered and right) |
|---|---|---|---|---|
| healthy | 158 | 99.2% | 80.4% | 48.7% |
| drought | 194 | 85.7% | 99.0% | 88.7% |
| fungal_disease | 8 | 80.0% | 100.0% | 50.0% |
| insect_damage | 15 | 100.0% | 86.7% | 86.7% |
| wear | 2 | 0.0% | 0.0% | 0.0% |
| dormant | 2 | 50.0% | 50.0% | 50.0% |

Confusion matrix: `ml_photo/confusion_logreg_v1.png` (rows = true class, columns = predicted).

| true \ predicted | healthy | drought | fungal_disease | insect_damage | wear | dormant |
|---|---|---|---|---|---|---|
| healthy | 127 | 31 | 0 | 0 | 0 | 0 |
| drought | 1 | 192 | 0 | 0 | 1 | 0 |
| fungal_disease | 0 | 0 | 8 | 0 | 0 | 0 |
| insect_damage | 0 | 1 | 0 | 13 | 1 | 0 |
| wear | 0 | 0 | 1 | 0 | 0 | 1 |
| dormant | 0 | 0 | 1 | 0 | 0 | 1 |

## How the Uncertain cutoff was chosen (training photos only)

Rule (project choice): the lowest cutoff in 0.3–0.95 whose accuracy on the photos it
still answers reaches 90%; if none does, the cutoff with the best answered accuracy.
- Zero-shot: cutoff **0.95** (target reached on training photos: False).
- Logistic regression: cutoff **0.75**, chosen on 5-fold cross-validation predictions of the
  training photos (target reached: True). Regularisation C = 10, chosen by
  cross-validated balanced accuracy: C=0.01: 0.804, C=0.1: 0.833, C=1: 0.836, C=10: 0.849, C=100: 0.843.
  CV folds keep groups together, except wear and dormant (one group each), whose photos are their own folds.

## Limitations (read before quoting any number)

- **Each class comes from a different kind of picture.** healthy and drought are frames from the same
  robot-camera video recordings (one day, 2022-10-18, no metadata row); fungal_disease and insect_damage
  are photos from extension / company articles; wear and dormant are 10 web photos each with no source.
  So a model can score well by recognising **where a photo came from** (camera, framing, article style)
  instead of the turf problem. A high score here does NOT show the model would work on a new phone photo.
- **insect_damage is mostly not turf damage**: by the student's choice it holds every picture from the
  insect PDFs (insect close-ups, weeds, cereal-crop diseases, a tree, thatch, wasp nests). The model
  learns "pictures from these articles", not "insect damage on a lawn". The prompts describe turf damage,
  so zero-shot is expected to miss most of these.
- **wear and dormant**: 10 photos each from one unknown source, split by file order (2 test photos each).
  Their test scores rest on 2 photos and the test photos may come from the same place as training.
- **Labels are not expert-confirmed** (captions or folder names only). Disease photos are mostly golf
  greens and fairways, not sports fields; 4 fungal photos are warm-season-grass diseases not found in
  Colorado.
- **Video frames** in healthy/drought are many near-identical views from a few recordings, so the
  test set is smaller than the photo count suggests; each recording counts more like one sample.
- **Licenses not checked** (permission "not asked"; 1,390 photos have no metadata row). The model and
  embeddings are kept out of git; nothing here may be published until licenses are checked.
- Cutoff rule, target 90%, C grid and 5 folds are project choices, not published standards.
- Nothing was tuned on the test photos; v1 is the first and only test run of this setup.

