# Stage 11 — Turf-problem photo classifier (PLAN ONLY, nothing built yet)

Written 2026-11-25. Status: **plan + empty folders only**. No model, no code, no photos yet.

## 0. Rules for this stage

- **ADD-ON ONLY.** Everything SpectralTurf already does (analysis, inspection rule, AI Weather
  Check, What if?, Ask SpectralTurf, accounts, regions) must keep working exactly the same, and all
  existing tests must still pass. New code goes in new files (`photo_ai/` folder). Existing files
  may only get small additions (e.g. registering a new endpoint) — and only in a later step,
  after the student says so.
- **Honest numbers only.** Every accuracy number comes from the evaluation script run on test
  photos from sites the model never saw. Report weak results as weak.
- **Photos never go into git** until each license is checked (`photo_data/` is git-ignored except
  `README.md` and the `metadata.csv` template).

### ⚠ Decision needed before anything reaches the website

The project rules (`docs/PROJECT_SPEC.md`, CLAUDE.md) say the app must **NOT claim to diagnose
disease**, and Ask SpectralTurf is built to refuse naming a disease from a photo (prompt rule 11,
`DISEASE_RE`). A classifier with a `fungal_disease` / `insect_damage` label goes against that if
it is shown as a diagnosis. Stages 1–3 below are **research only** (a notebook and a results
report) and are fine. Before Step 4 (putting it in the app), the student must choose one of:

1. Keep it research-only (results in slides/README, not in the app), or
2. Show it in the app only as *"This photo looks most similar to photos labeled X. This is not a
   diagnosis — confirm with an expert (e.g. CSU Extension / a plant diagnostic clinic)."*, with
   the "Unsure" answer whenever confidence is below the cutoff, and update the spec rule on
   purpose.

Also: drought, dormant and some diseases can look almost the same in a photo (all brown/straw).
Expect these to be confused with each other; that is a real finding to report, not a failure.

## 1. Data (the student collects; nothing is pre-split)

Folders (already created, local only):

```
photo_data/healthy/  drought/  fungal_disease/  insect_damage/  wear/  dormant/
photo_data/metadata.csv   filename,label,site,date,source,license,credit,confirmed_by
photo_data/README.md      how to add photos + an example row
```

- The student puts every photo in its label folder and adds one `metadata.csv` row.
- **The code splits train/test BY SITE** (the `site` column): all photos from one place go to the
  same side. Otherwise the model can "recognise the place" (same fence, same light, same camera)
  instead of the problem, and the accuracy would look better than it really is.
- A check script (Step 1a) refuses to run if: a photo has no row, a row has no photo, a label
  doesn't match its folder, `site` or `license` is blank, or a disease/insect row has no
  `confirmed_by`. It also finds exact duplicate photos (same file hash) and near-duplicates
  (very similar CLIP embeddings), because the same picture in train and test inflates accuracy.

### How many photos per class

These are common rules of thumb for this kind of small project, not a published standard:

| | Per class | Sites per class | Why |
|---|---|---|---|
| **Minimum to try** | ~30–50 photos | ≥ 5 different sites | Enough for a CLIP + logistic regression baseline to give a rough number. Results will be noisy (one wrong test photo changes accuracy by several %). |
| **Good** | ~150–300 photos | ≥ 15–20 sites | Enough for fine-tuning in Step 2 to have a fair chance to beat the baseline, and for per-class numbers to mean something. |
| More is better | 500+ | many | Diminishing returns; more *different sites* help more than more photos of the same site. |

Keep classes roughly balanced (the smallest class at least about half of the largest). If one
class is far too small (likely `fungal_disease` / `insect_damage`, since they need an expert to
confirm), options are: report it as "not enough data", merge it into a broader class
(e.g. "problem — needs expert"), or drop it. Decide after counting, and say which in the report.

### Which public images can legally be used

| Source | OK? | Notes |
|---|---|---|
| **Your own photos** | ✅ best | You own them. Also the most honest: you know the site, date and (with a groundskeeper or extension agent) the real cause. Remove GPS from EXIF before sharing. |
| **CC0 / Public domain** | ✅ | No conditions. Still record source + credit. |
| **CC BY** (any version) | ✅ | Must give credit (name, license, link). Can be redistributed in a dataset. |
| **CC BY-SA** | ✅ with care | Credit + any shared/remixed dataset must use the same license. |
| **CC BY-NC / BY-NC-SA** | ⚠ | OK for a non-commercial school project; the published dataset must then also be non-commercial (and SA = same license). Mark it in `license`. |
| **CC BY-ND** | ⚠ | Can use as-is for training in most readings, but avoid for a published dataset (resizing/cropping can count as a change). Simplest: skip. |
| **US federal government work** (e.g. some USDA photos) | ✅ usually | Public domain in the US *if* made by a federal employee — check each photo's page, some are contractor/third-party photos. |
| **University extension photos** | ❌ unless permission | Usually copyrighted ("© University of …"). Email them and ask; record `permission (email date)` in `license`. |
| **Google Images, Pinterest, lawn-care company sites, forums** | ❌ | "All rights reserved" by default. Don't use, even if easy to download. |

Where to look for openly licensed photos: **Wikimedia Commons** (license on each file page),
**iNaturalist** (each photo has its own license; many are CC BY-NC — use its license filter),
**Openverse** (openverse.org, searches CC-licensed images), **Flickr** with the license filter.
Labels from these photos are usually *not* expert-confirmed: put `photo caption` or `self` in
`confirmed_by`, and never use them for `fungal_disease` / `insect_damage` without a reliable
confirmation (e.g. the caption is from an extension specialist).

## 2. Step 1 — Baseline: CLIP embeddings + logistic regression (on this PC, CPU)

New files (when we build it): `photo_ai/check_data.py`, `photo_ai/embed_clip.py`,
`photo_ai/train_baseline.py`, `photo_ai/evaluate.py`, `photo_ai/test_photo_ai.py`.

1. **Check** `metadata.csv` and the folders (rules above). Print photos per class and per site.
2. **Embed** every photo once with a pretrained CLIP image encoder (e.g. `openai/clip-vit-base-patch32`
   via Hugging Face `transformers`; CPU is fine for a few thousand photos, roughly a few photos per
   second). Save embeddings to `photo_ai/cache/` (git-ignored) so they are never recomputed.
   CLIP is used frozen — we don't change it, we only use the 512 numbers it gives for each photo.
3. **Split by site:** about 20% of sites → **test** (kept locked until the end). The rest →
   training, with **GroupKFold by site** (5 folds) to choose settings. Fixed random seed (2026).
   If a class has too few sites, the split script says so instead of silently making a bad split.
4. **Train** scikit-learn `LogisticRegression` (with `class_weight="balanced"`) on the embeddings.
   Only one setting is tuned (`C`, regularisation strength), chosen by cross-validation.
5. **Unsure cutoff:** if the top predicted probability is below a cutoff, the answer is **"Unsure"**.
   The cutoff is chosen on the cross-validation folds (e.g. the lowest cutoff where answered photos
   reach a target accuracy), **never on the test set**.
6. **Compare with simple baselines** so the number means something: "always guess the most common
   class" and CLIP zero-shot (text prompts like "a photo of drought-stressed lawn grass") with no
   training.

## 3. Step 2 — Fine-tune a small pretrained model (Google Colab notebook)

New file: `photo_ai/finetune_colab.ipynb` (runs on Colab's free GPU; photos uploaded to the
student's own Google Drive, not to a public place).

- Model: a small pretrained image model from Hugging Face, e.g. **EfficientNet-B0**
  (`google/efficientnet-b0`) or a small **ViT** (`google/vit-base-patch16-224`). Start from the
  pretrained weights, replace the last layer with 6 outputs.
- **Exactly the same site split** as Step 1 (the split is saved to `photo_ai/split.json` and loaded
  by the notebook), so the two results can be compared fairly.
- Simple training: resize to 224 px, light augmentation (flip, small crop/rotation, small
  brightness change — no color changes that could turn green into brown), a few epochs, early
  stopping on the validation sites. Fixed seed.
- Same Unsure-cutoff method and same evaluation script output as Step 1.
- Fine-tuning only "wins" if it beats Step 1 on the same test sites by more than the noise
  (bootstrap over test sites, like Stage 10). With small data, CLIP + logistic regression often
  does as well or better — that is a valid result.

## 4. What the evaluation reports (both steps) → `photo_ai/results.md`

- **Accuracy** on the test sites (all photos, Unsure counted as wrong) and **accuracy on answered
  photos** (Unsure left out).
- **Unsure rate**: % of test photos below the confidence cutoff, and the cutoff value.
- **Per-class results**: precision, recall, F1 and number of test photos for each class (scikit-learn
  `classification_report`). Balanced accuracy too, since classes may be uneven.
- **Confusion matrix** (`photo_ai/confusion_step1.png`, `confusion_step2.png`) — shows which
  problems get mixed up (expected: drought ↔ dormant ↔ disease).
- **95% ranges** by bootstrapping over test sites (not photos), as in Stage 10.
- Baselines: most-common-class, CLIP zero-shot.
- Data summary: photos and sites per class, license mix, how many disease/insect labels are
  expert-confirmed.
- Limitations: small data, sites may differ from where the app is used (e.g. mostly Colorado),
  photos from the web may be "textbook" cases, label noise.

## 5. Later steps (only after the student decides — see section 0)

- Step 3: Optional app panel / Ask SpectralTurf tool, worded as "looks most similar to", with
  Unsure and an expert-confirmation note. Never a treatment or watering instruction.
- Step 4: Publish the dataset (below), README + slides.

## 6. Publishing the dataset on Hugging Face (later; ask before publishing)

Publishing is outward-facing: Claude will only prepare files; the student uploads after checking.

1. **Only include photos whose license allows sharing** (own, CC0, CC BY, CC BY-SA, CC BY-NC if the
   whole dataset is NC). Leave out "permission by email" photos unless the permission covers
   re-sharing. Remove EXIF (especially GPS) — re-save each image.
2. **Layout** = Hugging Face "imagefolder" format: the label folders plus a `metadata.csv`.
   Hugging Face requires the first column to be called **`file_name`** (ours is `filename`), so an
   export script writes a renamed copy. Remove columns you don't want public (e.g. `confirmed_by`
   names of private people → use roles like "groundskeeper").
3. **Dataset card** (`README.md` at the top of the dataset): what it is, classes and counts, how
   labels were confirmed, the site-based split, known limitations, and the dataset license. With
   mixed licenses, use the most restrictive one that covers all photos (e.g. CC BY-NC-SA 4.0) and
   keep per-photo `license` + `credit` columns so every photographer is credited.
4. Create a free account at huggingface.co, then on this PC:
   `pip install huggingface_hub datasets` → `huggingface-cli login` (paste your own token yourself;
   never put it in the repo) → in Python:
   `load_dataset("imagefolder", data_dir="export/")` then `.push_to_hub("<your-username>/spectralturf-turf-photos")`.
   You can create it as **private** first, check it on the website, then make it public.

## 7. Timeline note

WAICY is due **2026-11-29** (4 days). Collecting enough photos — especially expert-confirmed
disease/insect photos — will probably take longer than that. Realistic option: mention Stage 11
in the WAICY submission as **planned future work** (with this plan), and build Steps 1–2 once
there are at least ~30–50 photos per class from ≥ 5 sites.
