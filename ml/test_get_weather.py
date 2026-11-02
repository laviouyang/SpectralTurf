"""
test_get_weather.py - Offline checks for ml/get_weather.py (no internet).

Uses a MADE-UP Open-Meteo answer, only as a test input (never saved as data).

Run from the project folder:   python ml/test_get_weather.py
"""

import json
import tempfile
from pathlib import Path

import get_weather as g

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


g.START, g.END = "2024-07-01", "2024-07-05"
fake = {"latitude": 39.61, "longitude": -104.85, "daily": {
    "time": ["2024-07-01", "2024-07-02", "2024-07-04", "2024-07-05"],  # 07-03 is missing
    "precipitation_sum": [0.0, 5.2, 0.0, None],                           # 07-05 rain missing
    "temperature_2m_max": [31.0, 25.5, 33.0, 30.0],
    "et0_fao_evapotranspiration": [6.8, 3.1, 7.4, 6.0],
}}
rows, missing = g.to_rows(fake)
check("1. one row for every day in the range, even missing ones", [r["date"] for r in rows] ==
      ["2024-07-01", "2024-07-02", "2024-07-03", "2024-07-04", "2024-07-05"])
check("2. missing days are reported", missing == ["2024-07-03", "2024-07-05"])
check("3. missing values stay empty (None), never made up",
      rows[2]["precipitation_sum"] is None and rows[4]["precipitation_sum"] is None)
check("4. real values are copied exactly", rows[1]["precipitation_sum"] == 5.2
      and rows[3]["et0_fao_evapotranspiration"] == 7.4)

with tempfile.TemporaryDirectory() as tmp:
    g.CACHE_DIR = Path(tmp)
    (Path(tmp) / "test_field.json").write_text(json.dumps(fake), encoding="utf-8")
    data, downloaded = g.download({"id": "test_field", "centroid": [-104.85, 39.61]})
    check("5. a cached field is read from disk, not downloaded again", data == fake and not downloaded)

check("6. the Open-Meteo credit is there", g.CREDIT == "Weather data by Open-Meteo.com")
print(f"\nAll {passed} get_weather tests passed.")
