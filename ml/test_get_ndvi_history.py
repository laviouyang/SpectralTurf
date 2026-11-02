"""
test_get_ndvi_history.py - Offline checks for ml/get_ndvi_history.py (no internet, no PU spent).

Uses a MADE-UP answer in the same format the Copernicus Statistical API returns. It is only a
test input: never saved as data, never used for training.

Run from the project folder:   python ml/test_get_ndvi_history.py
"""

import tempfile
from pathlib import Path

import get_ndvi_history as g

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def day(date, mean, clear, samples=100, nodata=0):
    stats = {"mean": mean, "stDev": 0.05, "sampleCount": samples, "noDataCount": nodata}
    return {"interval": {"from": f"{date}T00:00:00Z"},
            "outputs": {"ndvi": {"bands": {"B0": {"stats": stats}}},
                        "clear": {"bands": {"B0": {"stats": {"mean": clear, "sampleCount": samples,
                                                              "noDataCount": nodata}}}}}}


fake = {"processing_units": 1.5, "answer": {"data": [
    day("2024-06-01", 0.71, 1.0),
    day("2024-06-03", "NaN", 0.0),          # fully cloudy: no NDVI
    day("2024-06-06", 0.65, 0.5),           # half cloudy
    {"interval": {"from": "2024-06-08T00:00:00Z"}, "error": {"type": "EXECUTION_ERROR"}},
    day("2024-06-11", 0.69, 0.9, samples=120, nodata=20),
]}}
rows = g.rows_from_answer(fake)
check("1. one row per date, and dates Copernicus couldn't compute are skipped", len(rows) == 4)
check("2. a fully cloudy date has no NDVI (None), never a made-up number",
      rows[1]["ndvi_mean"] is None and rows[1]["clear_fraction"] == 0)
check("3. pixels inside the field = samples - no-data", rows[3]["pixels"] == 100)
usable = [r for r in rows if r["clear_fraction"] >= g.MIN_CLEAR_FRACTION and r["ndvi_mean"] is not None]
check("4. only dates at least 80% clear are usable", [r["date"] for r in usable] == ["2024-06-01", "2024-06-11"])

grass = [{"ndvi_mean": v} for v in [0.2, 0.3, 0.5, 0.6, 0.7, 0.72, 0.75, 0.7, 0.65, 0.4, 0.35, 0.3]]
plastic = [{"ndvi_mean": v} for v in [0.18, 0.2, 0.19, 0.21, 0.22, 0.2, 0.19, 0.18, 0.2, 0.21, 0.2]]
dry_park = [{"ndvi_mean": v} for v in [0.45, 0.4, 0.3, 0.2, 0.17, 0.16, 0.16, 0.18, 0.2, 0.22, 0.25]]
check("5. real grass is kept", g.field_status(grass) == "kept")
check("6. a field that never gets above 0.3 is dropped as likely artificial turf",
      g.field_status(plastic).startswith("dropped") and "artificial" in g.field_status(plastic))
check("7. unwatered park grass that is brown all summer but greens in spring is kept",
      g.field_status(dry_park) == "kept")
check("8. a field with fewer than 10 clear dates is dropped", "fewer than 10" in g.field_status(grass[:5]))

x, y = g.ten_meters_in_degrees(39.7)
check("9. pixel size is 10 m in both directions at Denver's latitude",
      abs(y * 111_320 - 10) < 1e-6 and abs(x * 111_320 * g.math.cos(g.math.radians(39.7)) - 10) < 1e-6)

# Cache and budget: nothing is downloaded when the answer is cached or the budget is used up.
with tempfile.TemporaryDirectory() as tmp:
    g.CACHE_DIR = Path(tmp)
    field = {"id": "test_field", "centroid": [-104.9, 39.7], "geometry": {}}
    (Path(tmp) / "test_field_2024.json").write_text(g.json.dumps(fake), encoding="utf-8")
    saved, pu = g.download_year(field, 2024, spent=0)
    check("10. a cached year is read from disk and costs 0 PU", pu == 0 and saved == fake)
    try:
        g.download_year(field, 2023, spent=g.PU_BUDGET_PER_RUN + 1)
        stopped = False
    except g.QuotaStop:
        stopped = True
    check("11. over the per-run PU budget, it stops instead of downloading", stopped)

print(f"\nAll {passed} get_ndvi_history tests passed.")
