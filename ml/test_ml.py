"""
test_ml.py - Checks for the photo-AI code in ml/. Builds a THROWAWAY dataset in a temporary
folder from generated test images (backend/test_images/), so ml/data is never touched.

These tests only check that the code runs and catches mistakes. Numbers from generated
images mean nothing and are never reported.

Run from the project folder:   python ml/test_ml.py
(add --with-model to also run the slower CLIP tests, which load the AI model)
"""

import shutil
import sys
import tempfile
from pathlib import Path

import dataset

TEST_IMAGES = Path(__file__).resolve().parent.parent / "backend" / "test_images"
HEADER = "filename,label,site,date,notes\n"

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def make_dataset(folder, csv_lines, files):
    """files: list of (label, filename, test image to copy)."""
    folder = Path(folder)
    for label in dataset.LABELS:
        (folder / "data" / label).mkdir(parents=True, exist_ok=True)
    for label, filename, source in files:
        shutil.copy(TEST_IMAGES / source, folder / "data" / label / filename)
    (folder / "photos.csv").write_text(HEADER + "".join(line + "\n" for line in csv_lines), encoding="utf-8")
    return folder


def step1_dataset_checks():
    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(tmp, [], [])
        rows, problems, warnings = dataset.check(root)
        check("1. empty dataset: no rows, no problems", rows == [] and problems == [])
        check("2. empty dataset: every label warned about too few sites", len(warnings) == 4)

    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(
            tmp,
            [
                "a.png,healthy,Field A,2026-11-01,",
                "b.png,healthy,field a ,2026-11-01,same site, different spelling",
                "c.png,healthy,Field B,2026-11-02,",
                "d.png,dry_stressed,Field A,2026-11-01,",
            ],
            [("healthy", "a.png", "TEST_IMAGE_green.png"), ("healthy", "b.png", "TEST_IMAGE_green.png"),
             ("healthy", "c.png", "TEST_IMAGE_green.png"), ("dry_stressed", "d.png", "TEST_IMAGE_straw.png")],
        )
        rows, problems, warnings = dataset.check(root)
        check("3. good rows are all usable", len(rows) == 4 and problems == [])
        check("4. 'Field A' and 'field a ' count as one site",
              len({r["site_key"] for r in rows if r["label"] == "healthy"}) == 2
              and any("ONE site" in w for w in warnings))

    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(
            tmp,
            [
                "a.png,healthy,Field A,2026-11-01,",
                "a.png,healthy,Field A,2026-11-01,listed twice",
                "b.png,helthy,Field A,2026-11-01,typo in label",
                "c.png,healthy,,2026-11-01,no site",
                "d.png,healthy,Field A,11/01/2026,wrong date format",
                "e.png,healthy,Field A,2026-11-01,file is in another folder",
                "missing.png,healthy,Field A,2026-11-01,no file",
                "broken.png,healthy,Field A,2026-11-01,not really an image",
            ],
            [("healthy", "a.png", "TEST_IMAGE_green.png"), ("worn_bare", "e.png", "TEST_IMAGE_soil.png"),
             ("non_turf", "extra.png", "TEST_IMAGE_gray.png")],
        )
        (root / "data" / "healthy" / "broken.png").write_text("this is not an image")
        rows, problems, warnings = dataset.check(root)
        text = "\n".join(problems)
        check("5. only the one good photo is usable", len(rows) == 1)
        check("6. duplicate row caught", "listed twice" in text)
        check("7. unknown label caught", "'helthy'" in text)
        check("8. empty site caught", "site is empty" in text)
        check("9. bad date caught", "11/01/2026" in text)
        check("10. file in the wrong label folder caught", "file is in data/worn_bare/" in text)
        check("11. missing file caught", "file not found at data/healthy/missing.png" in text)
        check("12. unreadable image caught", "can't be opened" in text)
        check("13. photo without a CSV row caught", "data/non_turf/extra.png has no row" in text)

    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(tmp, ["g.jpg,healthy,Field A,2026-11-01,"],
                            [("healthy", "g.jpg", "TEST_IMAGE_with_fake_gps.jpg")])
        rows, problems, warnings = dataset.check(root)
        check("14. photos with GPS location are pointed out", any("GPS" in w for w in warnings))


def fake_training_set(tmp):
    """2 generated images per label at each of 3 'sites'. Only for checking the code runs."""
    sources = {"healthy": "TEST_IMAGE_green.png", "dry_stressed": "TEST_IMAGE_straw.png",
               "worn_bare": "TEST_IMAGE_soil.png", "non_turf": "TEST_IMAGE_gray.png"}
    lines, files = [], []
    for site in ["Test Site 1", "Test Site 2", "Test Site 3"]:
        for label, source in sources.items():
            for n in range(2):
                name = f"TEST_{site[-1]}_{label}_{n}.png"
                lines.append(f"{name},{label},{site},2026-07-01,generated test image")
                files.append((label, name, source))
    return make_dataset(tmp, lines, files)


def run_quietly(function, *args):
    """Run a script's main() and capture what it prints. Numbers from generated
    images are meaningless, so the tests never show them."""
    import contextlib
    import io

    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        code = function(*args)
    return code, printed.getvalue()


def step2_zero_shot():
    import numpy as np

    import clip_model
    import zero_shot

    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(tmp, [], [])
        code, out = run_quietly(zero_shot.main, root)
        check("15. zero_shot.py with no photos explains instead of crashing",
              code == 0 and "No usable labeled photos" in out)

    vectors = clip_model.embed_images([dataset.open_image(TEST_IMAGES / "TEST_IMAGE_green.png")] * 3)
    check("16. CLIP turns each photo into 512 numbers of length 1",
          vectors.shape == (3, 512) and np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-4))
    probabilities = clip_model.zero_shot_probabilities(vectors)
    check("17. zero-shot gives 4 probabilities per photo that add up to 1",
          probabilities.shape == (3, 4) and np.allclose(probabilities.sum(axis=1), 1, atol=1e-5))

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_training_set(tmp)
        code, out = run_quietly(zero_shot.main, root)
        check("18. zero_shot.py runs and prints accuracy + confusion matrix",
              code == 0 and "Accuracy:" in out and "Confusion matrix" in out)
        check("19. embeddings are cached", (root / "embeddings.npz").exists())
        code, out = run_quietly(zero_shot.main, root)
        check("20. second run uses the cache", "Computing CLIP embeddings" not in out)


def step3_site_split():
    """The by-site rule, checked with random numbers in place of CLIP embeddings (no model)."""
    import numpy as np

    import evaluate
    import train

    rng = np.random.default_rng(0)
    sites = [f"site{i % 4}" for i in range(40)]
    labels = [dataset.LABELS[i % 4] for i in range(0, 80, 2)]
    embeddings = rng.normal(size=(40, 8))

    seen_in_training = []
    real_make_classifier = evaluate.make_classifier

    class Spy:
        """Pretends to be the classifier and remembers which rows it was trained on."""
        def __init__(self):
            self.inner = real_make_classifier()

        def fit(self, x, y):
            rows = {int(np.argmin(np.abs(embeddings - row).sum(axis=1))) for row in x}
            seen_in_training.append({sites[i] for i in rows})
            self.inner.fit(x, y)
            self.classes_ = self.inner.classes_
            return self

        def predict_proba(self, x):
            return self.inner.predict_proba(x)

    evaluate.make_classifier = Spy
    try:
        probabilities, skipped, _ = evaluate.held_out_site_predictions(embeddings, labels, sites)
    finally:
        evaluate.make_classifier = real_make_classifier
    check("21. one test model per site (leave-one-site-out with 4 sites)", len(seen_in_training) == 4)
    check("22. no test model ever trained on the site it was tested on",
          all(len(trained_sites) == 3 for trained_sites in seen_in_training))
    check("23. every photo gets exactly one prediction, as 4 probabilities adding to 1",
          not np.isnan(probabilities).any() and np.allclose(probabilities.sum(axis=1), 1))

    one_label_sites = ["a", "a", "b", "b", "c", "c"]
    one_label = ["healthy", "worn_bare", "healthy", "healthy", "healthy", "healthy"]
    probabilities, skipped, _ = evaluate.held_out_site_predictions(rng.normal(size=(6, 8)), one_label,
                                                                   one_label_sites)
    check("24. a site is skipped (not faked) when the other sites have only one label",
          ["a"] in skipped and np.isnan(probabilities[:2]).all())

    clf = train.make_classifier().fit(rng.normal(size=(6, 8)), ["healthy", "non_turf"] * 3)
    full = train.probabilities_in_label_order(clf, rng.normal(size=(2, 8)))
    check("25. labels the model never saw get probability 0, in the right column",
          full.shape == (2, 4) and (full[:, [1, 2]] == 0).all())


def step3_train_and_evaluate():
    import joblib

    import evaluate
    import train

    with tempfile.TemporaryDirectory() as tmp:
        root = make_dataset(tmp, ["a.png,healthy,Test Site 1,2026-07-01,"],
                            [("healthy", "a.png", "TEST_IMAGE_green.png")])
        code, out = run_quietly(train.main, root)
        check("26. train.py refuses when a label has no photos",
              code == 1 and "no usable photos" in out and not (root / train.MODEL_FILE).exists())
        code, out = run_quietly(evaluate.main, root)
        check("27. evaluate.py refuses with only 1 site", code == 1 and "need at least 2 sites" in out)

    with tempfile.TemporaryDirectory() as tmp:
        root = fake_training_set(tmp)
        code, out = run_quietly(train.main, root, 0.7)
        saved = joblib.load(root / train.MODEL_FILE)
        check("28. train.py saves a model with its cutoff and photo counts",
              code == 0 and saved["cutoff"] == 0.7 and saved["photos"] == 24 and saved["sites"] == 3)
        code, out = run_quietly(train.main, root, 1.5)
        check("29. an impossible cutoff is refused", code == 1)
        code, out = run_quietly(evaluate.main, root)
        results = (root / "results.md").read_text(encoding="utf-8")
        check("30. evaluate.py writes results.md comparing zero-shot and trained",
              code == 0 and "Zero-shot CLIP (no training):" in results
              and "Trained classifier:" in results and "leave-one-site-out" in results)
        rows, _, _ = dataset.check(root)
        import clip_model
        embeddings = clip_model.embed_dataset(rows, root / "embeddings.npz")
        probabilities, _, _ = evaluate.held_out_site_predictions(
            embeddings, [r["label"] for r in rows], [r["site_key"] for r in rows])
        check("31b. probabilities are not all stuck near 25% (the scaling bug found in Step 3)",
              (probabilities.max(axis=1) > 0.5).mean() > 0.5)
    check("31. the real model folder was not touched by the tests",
          not (dataset.ML_DIR / train.MODEL_FILE).exists())


if __name__ == "__main__":
    if not (TEST_IMAGES / "TEST_IMAGE_green.png").exists():
        sys.exit("Run first:  python backend/test_images/make_test_images.py")
    step1_dataset_checks()
    step3_site_split()
    if "--with-model" in sys.argv:
        step2_zero_shot()
        step3_train_and_evaluate()
    else:
        print("(Skipping the CLIP model tests. Add --with-model to run them.)")
    print(f"\nAll {passed} ml tests passed.")
