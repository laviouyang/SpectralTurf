"""
make_test_images.py - Makes tiny GENERATED images for testing code only.

These are NOT photos of turf. They are flat colors with a little noise. They exist only so
the tests can check that uploads, file checks and the AI pipeline run without errors.
Never put them in ml/data, never train the real model on them, and never report any
accuracy number from them.

Run:   python backend/test_images/make_test_images.py
"""

from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent

COLORS = {
    "TEST_IMAGE_green.png": (60, 140, 50),
    "TEST_IMAGE_straw.png": (190, 170, 100),
    "TEST_IMAGE_soil.png": (120, 85, 55),
    "TEST_IMAGE_gray.png": (128, 128, 128),
}


def make(color, seed, size=64):
    rng = np.random.default_rng(seed)
    pixels = np.clip(np.array(color) + rng.normal(0, 18, (size, size, 3)), 0, 255)
    return Image.fromarray(pixels.astype(np.uint8))


def main():
    for seed, (name, color) in enumerate(COLORS.items()):
        make(color, seed).save(HERE / name)

    # A JPEG with a made-up GPS location in its EXIF (0.5 N, 0.5 E, in the ocean),
    # used to check that saved photos have their GPS data removed.
    img = make(COLORS["TEST_IMAGE_green.png"], 99)
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (0.0, 30.0, 0.0), 3: "E", 4: (0.0, 30.0, 0.0)}  # GPS block
    exif[0x0132] = "2026:01:15 12:00:00"  # DateTime: a winter date
    img.save(HERE / "TEST_IMAGE_with_fake_gps.jpg", exif=exif)
    print(f"Wrote {len(COLORS) + 1} generated test images to {HERE}")


if __name__ == "__main__":
    main()
