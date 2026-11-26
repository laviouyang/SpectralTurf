"""
saved_fields.py - Version 2 (2026-11-25): save a field to "My Fields" WITHOUT running an analysis.

The student wanted two separate buttons: "Save" (just keep the outline under a name) and
"Analyze" (look at the satellite data, never saves). A saved field uses the same table as saved
analyses (accounts.py), so My Fields, the AI ranking, the AI checks and Ask AI all see it.

Honesty rule: no measurement was made, so we store NO numbers. The row has an empty image date
and the summary {"status": "not_analyzed"}. accounts.py itself is unchanged.
"""

import json

import accounts

NOT_ANALYZED = "not_analyzed"


def save_field(db, user_id, name, geometry, exclusions):
    """Save one outline (+ excluded areas) under a name for this user. Returns the new row id."""
    count = db.execute("SELECT COUNT(*) FROM saved_analyses WHERE user_id = ?", (user_id,)).fetchone()[0]
    if count >= accounts.MAX_SAVED_PER_USER:
        raise accounts.AccountError(
            f"My Fields is full ({accounts.MAX_SAVED_PER_USER} saved). Delete some old ones.")
    name = (name or "").strip()[:accounts.MAX_NAME_LENGTH]
    if not name:
        raise accounts.AccountError("Please type a name for the field.")
    cursor = db.execute(
        "INSERT INTO saved_analyses (user_id, name, geometry, exclusions, start_date, end_date, "
        "observation_date, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (user_id, name, json.dumps(geometry), json.dumps(list(exclusions)), "", "", "",
         json.dumps({"status": NOT_ANALYZED}), accounts.now().isoformat()),
    )
    db.commit()
    return cursor.lastrowid
