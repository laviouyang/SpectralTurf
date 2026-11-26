"""
test_field_list.py - Checks for the field list rule (2026-11-26, student request): the field
drop-down, the My Fields ranking and the AI tools show ONE entry per saved field NAME (newest
save of that name), even when two names share the same outline.

The cases are in field_list_cases.json and are shared with the frontend test
(frontend/scripts/test_field_picker.mjs), so both sides must give the same answers.
No internet, no database: fake saves and a fake weather check are used.

Run:   python test_field_list.py
"""

import json
from datetime import date
from pathlib import Path

import assistant
import predict

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


data = json.loads((Path(__file__).parent / "field_list_cases.json").read_text(encoding="utf-8"))


def make_saved(rows):
    """Turn the short test rows into rows shaped like accounts.list_analyses output."""
    return [{"id": r["id"], "name": r["name"], "geometry": data["shapes"][r["shape"]],
             "exclusions": [], "start": "2026-08-01", "end": "2026-08-15",
             "observation_date": "2026-08-05", "summary": {}, "saved_at": "2026-08-15"}
            for r in rows]


# 1-7: the shared cases
for case in data["cases"]:
    ids = [f["id"] for f in predict.distinct_saved_fields(make_saved(case["saved"]))]
    check(f"distinct_saved_fields: {case['name']}", ids == case["expected_ids"])

# The real problem case: the same outline saved under two names.
saved = make_saved(data["cases"][0]["saved"])

# 8: My Fields ranking checks BOTH names
checked = []


def fake_check(geometry, exclusions, as_of):
    checked.append(geometry)
    return {"status": "error", "message": "fake"}


ranking = predict.rank_my_fields(saved, date(2026, 8, 15), check=fake_check)
check("My Fields ranking lists both names",
      sorted(e["field"]["name"] for e in ranking["fields"]) == ["North A", "North B"] and len(checked) == 2)

# 9: What-if for my fields runs for both names
ran = []
predict.what_if_my_fields(saved, date(2026, 8, 15), {}, run=lambda g, e, a, s: ran.append(g) or {"status": "error"})
check("What-if for My Fields runs for both names", len(ran) == 2)

# 10: Ask AI knows both fields (field-1 = newest)
ctx = assistant.Context(True, saved, None, None, date(2026, 8, 15))
check("Ask AI has field-1 and field-2, newest first",
      [f["id"] for f in ctx.fields.values()] == [2, 1] and list(ctx.fields) == ["field-1", "field-2"])

print(f"\nAll {passed} checks passed.")
