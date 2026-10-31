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

## Tests
```powershell
python backend/test_images/make_test_images.py   # once: makes generated test images
python ml/test_ml.py
```
The tests use **generated** images (flat colors in `backend/test_images/`) inside a temporary
folder. They never touch `ml/data`, and any numbers they produce mean nothing.
