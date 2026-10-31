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


if __name__ == "__main__":
    if not (TEST_IMAGES / "TEST_IMAGE_green.png").exists():
        sys.exit("Run first:  python backend/test_images/make_test_images.py")
    step1_dataset_checks()
    print(f"\nAll {passed} ml tests passed.")
