# Stage 9 (Photo AI): progress report

Written 2026-10-31 by Claude Code while Lavi was away. Plan: `docs/STAGE_9_PHOTO_AI.md`.
Details for each step: `ml/README.md`.

## Summary
- **Steps 1–5 are built, tested, and committed.** Step 6 (README, slides, demo) waits for
  real results.
- **No photos exist yet, so there is no trained model and no accuracy number.** Until
  `ml/train.py` is run on your photos, the app uses zero-shot CLIP and says
  **"zero-shot (not yet trained)"** in every answer.
- The satellite analysis was not changed, and `backend/.env` was not touched.
- **Nothing is pushed to GitHub yet.** All commits are local.

### Commits (newest last)
| Commit | What |
|---|---|
| `bbaec24` | Restore point: the working app before any photo-AI work (plus the stage rules in CLAUDE.md) |
| `63736eb` | Step 1: dataset folders, `photos.csv`, dataset checker |
| `db019b0` | Step 2: zero-shot CLIP baseline |
| `b989847` | Step 3: training + by-site evaluation |
| `72bc3c0` | Step 4: `POST /api/photo/analyze` |
| `d1c655b` | Step 5: "Check a spot with a photo" panel |

To go back to the app as it was before the photo AI: `git checkout bbaec24` (look around),
then `git checkout main` to return. Ask Claude before using anything like `git reset`.

## What was installed
These libraries went into `backend\venv`: torch 2.15 (CPU), transformers 5.22, scikit-learn 1.9,
joblib 1.6, python-multipart 0.0.33, httpx 0.28. The CLIP model (about 600 MB) is cached in
`C:\Users\grace\.cache\huggingface`. The list is in `ml/requirements.txt`, and
`python-multipart` was added to `backend/requirements.txt`.

**On a new computer:** after the usual backend setup, run
`pip install torch --index-url https://download.pytorch.org/whl/cpu`, then
`pip install -r ml/requirements.txt`.

## What was built, and how to test each part
Run everything from `D:\Lavi\SpectralTurf` with the venv active:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then
`backend\venv\Scripts\activate`.

**One time:** make the generated test images. The PNG files are git-ignored, so this is
needed again on a fresh copy:
```powershell
python backend/test_images/make_test_images.py
```

### Step 1: photo dataset
- **Files:**
  - `ml/data/{healthy,dry_stressed,worn_bare,non_turf}/`
  - `ml/photos.csv` (header only)
  - `ml/dataset.py` (shared reading and checks)
  - `ml/check_dataset.py`
  - `ml/README.md` (includes the photo-taking guide)
- **Privacy:** photo files in `ml/data` are **git-ignored**, because phone photos contain GPS
  location and the repo is public. Back them up privately.
- **Site names:** "Village Greens" and "village greens " count as the same site, so the
  by-site test can't be fooled by a spelling difference.
- **Test it:** `python ml/check_dataset.py`. **Success right now:** a table of zeros, a
  warning for each label about 0 sites, and "No problems found."

### Step 2: zero-shot baseline
- **Files:**
  - `ml/clip_model.py` (loads CLIP once; the class sentences are in `PROMPTS`)
  - `ml/zero_shot.py`
  - `ml/report.py`
- **Embeddings cache:** embeddings are saved in `ml/embeddings.npz` (git-ignored), so each
  photo is only processed once.
- **Test it:** `python ml/zero_shot.py`. **Success right now:** "No usable labeled photos yet".
  With photos, it prints accuracy, the number of uncertain photos, and a confusion matrix.

### Step 3: train and evaluate
- **Files:** `ml/train.py`, `ml/evaluate.py`.
- **How it trains:** CLIP embeddings are rescaled, then fed to logistic regression
  (`class_weight="balanced"`).
- **How it evaluates:** `evaluate.py` holds out **whole sites**: leave-one-site-out with 5 or
  fewer sites, otherwise 5 groups of sites. It compares trained vs. zero-shot on the same photos
  and prints precision/recall, confusion matrices, accuracy per site, and a cutoff table. It
  writes everything to `ml/results.md` with the date.
- **Saved model:** `train.py` saves `ml/model/turf_photo_clf.joblib`. It refuses if any label
  has no photos.
- **Test it:** `python ml/evaluate.py` and `python ml/train.py`. **Success right now:** both
  explain that there aren't enough photos, and neither crashes.

### Step 4: backend endpoint
- **Files:**
  - `backend/photo_ai.py`
  - `backend/main.py` (new endpoint at the bottom; the satellite code is unchanged)
  - `backend/test_photo_ai.py`
- **Response:** `POST /api/photo/analyze` returns `label`, `label_text`, `confidence`,
  `probabilities` (all 4), `uncertain`, `cutoff`, `method`, `photo_date`, `date_source`,
  `off_season`, `note`, `saved_for_training`.
- **Validation:** checks the file's real contents (jpg/png/webp only) and the 10 MB limit.
- **Privacy:** the photo is kept **in memory only**. I also raised the upload buffer size so
  big photos aren't put in a temporary file. It is saved to `ml/inbox/` only when
  "allow training" is ticked, and then **all EXIF, including GPS, is removed**.
- **Photo date:** read from the photo when it has one, otherwise today. Nov–Mar adds the
  dormancy note.
- **Test it:**
  1. Start the backend as usual.
  2. Open http://localhost:8000/docs → **POST /api/photo/analyze** → Try it out → pick any
     photo → Execute.
  3. **Success:** a JSON answer with `"method": "zero-shot (not yet trained)"`.
  4. The first photo takes about 5 s while the model loads; later ones take about 0.3 s on
     this PC.

### Step 5: website panel
- **Files:**
  - `frontend/src/PhotoCheck.jsx` (shown in the results right under the inspection card)
  - `api.js` (`analyzePhoto`)
  - `App.css`
- **What it shows:** the take/choose-photo button (opens the back camera on phones), the
  "Allow this photo to improve the model" box (unticked by default), a preview, the top label
  with a confidence bar, all 4 probabilities, and "AI suggestion — confirm in person".
- **Uncertain answers:** below the cutoff it shows "Uncertain — inspect in person".
- **Off-season:** it shows an off-season note in Nov–Mar, and also when the photo's own date is
  in Nov–Mar.
- **Test it:**
  1. Start the backend and `npm.cmd run dev`.
  2. Analyze any field.
  3. In the results, click **Take or choose a photo**.
- **Success:** a result appears within a few seconds and says "AI suggestion — confirm in
  person". On your phone, use `npm.cmd run phone` (README "Opening it on your phone").

### All tests
```powershell
cd backend
python test_indices.py      # 29 satellite tests (unchanged)
python test_accounts.py     # 16 account tests
python test_photo_ai.py     # 21 photo endpoint tests (loads CLIP)
cd ..
python ml/test_ml.py --with-model   # 32 ml tests (loads CLIP)
```
All of these passed on 2026-10-31.

The tests use **generated** flat-color images only, inside temporary folders or
`backend/test_images/`. They never touch `ml/data`, `ml/inbox`, or `ml/model`; test 31 checks
the model folder. No accuracy number from them is reported anywhere.

## What's left for you
1. **Take the photos** (the most important part).
   - Follow the guide in `ml/README.md`.
   - Visit 4+ fields. Aim for 30–50 photos per label, with every label at 3+ sites.
   - Shoot from 1–2 m up, pointing down, in daylight.
   - iPhone: send the photos as JPG, not HEIC.
2. **Put each photo in its label folder** and add a row to `ml/photos.csv`. Then run
   `python ml/check_dataset.py` until it says "No problems found."
3. **Run the AI steps:**
   ```powershell
   python ml/zero_shot.py   # write down the baseline
   python ml/evaluate.py    # the real result -> ml/results.md
   python ml/train.py       # build the app's model (add --cutoff 0.7 etc. if the table suggests it)
   ```
   Then restart the backend. The photo panel will then say "trained classifier (...)" instead
   of zero-shot.
4. **Hand-test the website**, including on your phone.
5. **Step 6 (wrap-up for WAICY):**
   - Ask Claude to update the README with the real numbers from `ml/results.md`.
   - Make 2–3 slides.
   - Record the demo.
6. **Push to GitHub** when you're happy:
   - Run `git status` first. No photos, `.env`, `.db`, or `ml/inbox` files should be listed.
   - Then `git push`.

## Problems found, and things to know
- **Fixed in Step 3: every answer came out "Uncertain".**
  - CLIP's numbers are all tiny, and plain logistic regression kept every probability near 25%.
  - Rescaling the numbers first (StandardScaler) fixed it.
  - If the real `results.md` shows the model is very sure (above 90%) but often wrong, lower
    `REGULARIZATION_C` in `ml/train.py` (try 0.1) and re-run evaluate and train.
- **Fixed in Step 4: the photo check crashed inside the web server.**
  - The setting that tells PyTorch "we're only using the model, not training it" only applied
    to the thread that loaded the model, but the server answers on other threads.
  - It is now applied on every call.
- **The zero-shot confidence scale differs from the trained one.**
  - The same 0.60 cutoff can mean different things for the two methods.
  - `evaluate.py` prints a cutoff table for **both** methods. Choose the trained model's cutoff
    from its own table.
- **The cutoff is chosen from the same photos it is tested on**, so it fits them slightly better
  than it will fit new photos. `results.md` says so.
- **Phone camera vs. gallery.**
  - `capture="environment"` (from the plan) makes many Android phones open the camera
    directly, with no option to pick an existing photo from the gallery.
  - If you want gallery uploads on phones, Claude can remove that attribute. Desktop browsers
    are not affected.
- **The photo panel only appears after a satellite analysis**, inside the results, as the plan
  says. If you want it available on its own, that's a small change.
- **Internet at first use.** When the backend loads CLIP, the Hugging Face library checks
  online for updates and prints a harmless "unauthenticated requests" warning. It uses the
  cached model.
- **Disk space:** about 600 MB for the CLIP cache, plus about 1 GB of libraries in the venv.
- **Not tested:** a real phone (camera, upload size), real turf photos, and the trained-model
  path with real data. The trained-model path was only exercised in tests with a throwaway
  model trained on generated images in a temporary folder.
