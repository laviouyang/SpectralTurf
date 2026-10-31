# SpectralTurf photo AI (`ml/`)

The satellite shows **where** to look. The photo check helps explain **what is there**: a
photo of a flagged spot gets an AI **suggestion** (healthy, dry/stressed, worn/bare, or not
turf) with a confidence. It is never a diagnosis, so always confirm in person.

Plan: `docs/STAGE_9_PHOTO_AI.md`. Progress and test steps: `docs/STAGE_9_PROGRESS.md`.

All commands below run from the project folder `D:\Lavi\SpectralTurf` with the backend venv
active (`backend\venv\Scripts\activate`).

## Step 1: the photo dataset

### Classes
| Folder | Put photos here of... |
|---|---|
| `ml/data/healthy/` | green, dense turf |
| `ml/data/dry_stressed/` | thin, straw/yellow, dry-looking turf (still grass) |
| `ml/data/worn_bare/` | grass worn away, exposed soil from traffic (goal mouths, sidelines) |
| `ml/data/non_turf/` | dirt infield, track, pavement, artificial turf |

### Taking the photos
- **4+ different fields.** Goal: 30–50 photos per label, from at least 3 sites each.
  Spread every label across fields. The AI is tested on fields it has never seen, so a label
  photographed at only one field can't be tested fairly.
- Phone camera, about **1–2 m above the grass, pointing down**, in daylight.
- One spot per photo. If a photo mixes two classes (half green, half dirt), skip it or retake it.
- **Season matters.** In Nov–Mar, Colorado grass browns naturally (dormancy). Brown dormant
  turf is not the same as drought-stressed summer turf. Write the date of every photo, and add
  "dormant?" in the notes when you're unsure.
- iPhone: photos in HEIC format must be exported or shared as **JPG** (or set
  Settings → Camera → Formats → Most Compatible).

### Recording them in `ml/photos.csv`
One row per photo. Open it in Excel or Notepad, and keep the header line exactly as it is:

```
filename,label,site,date,notes
IMG_2041.jpg,healthy,Village Greens,2026-11-02,
IMG_2042.jpg,worn_bare,Village Greens,2026-11-02,goal mouth
```
- `filename`: the file's name inside its label folder.
- `label`: the folder it is in (`healthy`, `dry_stressed`, `worn_bare`, `non_turf`).
- `site`: which field. Always spell a field the same way (capital letters and spaces are ignored).
- `date`: the day the photo was taken, as YYYY-MM-DD.
- `notes`: optional.

(The two example rows above are only an illustration. `photos.csv` starts with the header only.)

### Checking the dataset
```powershell
python ml/check_dataset.py
```
It prints photos per label and per site, and lists anything to fix: missing rows, files in the
wrong folder, unreadable images, bad dates, and labels with fewer than 2 sites.
**Success:** a clean table and "No problems found."

### Privacy
Phone photos usually store the GPS location where they were taken. The photo files are
**git-ignored** and stay on this computer. Only `photos.csv` and the empty folders go to GitHub.
Back the photos up somewhere private (e.g. a USB stick).

## Step 2: zero-shot baseline (no training)

```powershell
python ml/zero_shot.py
```
CLIP compares every labeled photo to one sentence per class (in `ml/clip_model.py`,
`PROMPTS`) and picks the closest. It prints the **accuracy**, how many photos are below the
0.60 confidence cutoff, and a **confusion matrix** (rows = your label, columns = CLIP's
answer). Write the accuracy down: it is the baseline the trained model must beat.
A low number is fine and expected; CLIP was never shown our labels.

- The first run downloads the CLIP model once (about 600 MB).
- Each photo's embedding is saved in `ml/embeddings.npz` (git-ignored), so later runs are fast.

## Step 3: train our own classifier, and measure it honestly

```powershell
python ml/evaluate.py            # measure: accuracy on fields the model never saw
python ml/train.py               # build the app's model from all photos
python ml/train.py --cutoff 0.7  # (optional) after choosing a cutoff from evaluate.py
```
- **How it learns:** CLIP turns each photo into 512 numbers (its embedding). Logistic
  regression learns which patterns in those numbers go with each label.
- **Why test by site:** photos of the same field look alike, so testing on a field that was
  also in training would make the accuracy look better than it is. `evaluate.py` always holds
  out whole sites: each photo is predicted by a model that never saw its field.
- `evaluate.py` prints, and saves to `ml/results.md` with the date: trained vs. zero-shot
  accuracy on the same photos, precision/recall per label, confusion matrices, accuracy per
  site, and a table of how many photos fall below each possible "uncertain" cutoff.
  **Only report numbers from this file.**
- `train.py` saves `ml/model/turf_photo_clf.joblib`. Restart the backend afterwards and the
  photo check uses it instead of zero-shot.
- Accuracy on the photos the saved model was trained on is never shown; it would be meaningless.
- If `results.md` shows the model is very sure (above 0.9) yet often wrong, lower
  `REGULARIZATION_C` in `ml/train.py` (try 0.1) and run both scripts again.

## Tests
```powershell
python backend/test_images/make_test_images.py   # once: makes generated test images
python ml/test_ml.py                # quick checks
python ml/test_ml.py --with-model   # also the CLIP tests (slower, loads the model)
```
The tests use **generated** images (flat colors in `backend/test_images/`) inside a temporary
folder. They never touch `ml/data`, and any numbers they produce mean nothing.
