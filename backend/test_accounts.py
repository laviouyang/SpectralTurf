"""
test_accounts.py - Checks for accounts.py. Uses a temporary database file, so your
real accounts are never touched. No internet or Copernicus login needed.

Run:   python test_accounts.py
"""

import os
import tempfile

import accounts

FAKE_RESULT = {
    "status": "ok",
    "observation": {"date": "2026-08-05", "tile_cloud_cover": 0.0},
    "pixels": {"valid_after_masking": 120, "valid_fraction": 1.0},
    "ndvi": {"median": 0.7},
    "ndmi": {"median": 0.2},
    "ngrdi": {"median": 0.2},
    "inspection": {"status": "no_area_stands_out", "scope": None, "headline": "No area stands out"},
    "warnings": [],
}
SQUARE = {"type": "Polygon", "coordinates": [[[0, 0], [0, 1], [1, 1], [0, 0]]]}

passed = 0


def check(name, condition):
    global passed
    assert condition, name
    passed += 1
    print("PASS", name)


def raises_account_error(action):
    try:
        action()
    except accounts.AccountError:
        return True
    return False


with tempfile.TemporaryDirectory() as folder:
    db = accounts.connect(os.path.join(folder, "test.db"))

    token = accounts.sign_up(db, "lavi_test", "correct horse")
    check("1. sign up returns a token that identifies the user",
          accounts.user_for_token(db, token)["username"] == "lavi_test")

    stored = db.execute("SELECT password_hash FROM users").fetchone()[0]
    check("2. the password itself is not stored", "correct horse" not in stored)
    check("3. the token itself is not stored",
          db.execute("SELECT COUNT(*) FROM sessions WHERE token_hash = ?", (token,)).fetchone()[0] == 0)

    check("4. duplicate username (any capitals) is refused",
          raises_account_error(lambda: accounts.sign_up(db, "LAVI_test", "another pass")))
    check("5. short password is refused",
          raises_account_error(lambda: accounts.sign_up(db, "someone", "short")))
    check("6. bad username characters are refused",
          raises_account_error(lambda: accounts.sign_up(db, "a b<script>", "long enough")))

    check("7. wrong password is refused",
          raises_account_error(lambda: accounts.log_in(db, "lavi_test", "wrong horse")))
    check("8. unknown user is refused",
          raises_account_error(lambda: accounts.log_in(db, "nobody", "correct horse")))
    token2 = accounts.log_in(db, "lavi_test", "correct horse")
    check("9. correct password logs in", accounts.user_for_token(db, token2) is not None)

    accounts.log_out(db, token2)
    check("10. a logged-out token no longer works", accounts.user_for_token(db, token2) is None)
    check("11. a made-up token does not work", accounts.user_for_token(db, "made-up") is None)

    user = accounts.user_for_token(db, token)
    saved = accounts.save_analysis(db, user["id"], "  North field ", SQUARE, [], "2026-06-01",
                                   "2026-08-31", FAKE_RESULT)
    history = accounts.list_analyses(db, user["id"])
    check("12. a saved analysis comes back with its name, shape, and numbers",
          len(history) == 1 and history[0]["name"] == "North field"
          and history[0]["geometry"] == SQUARE and history[0]["summary"]["ndvi_median"] == 0.7
          and history[0]["observation_date"] == "2026-08-05")

    other = accounts.user_for_token(db, accounts.sign_up(db, "other_user", "password123"))
    check("13. another user cannot see it", accounts.list_analyses(db, other["id"]) == [])
    check("14. another user cannot delete it", not accounts.delete_analysis(db, other["id"], saved))
    check("15. the owner can delete it",
          accounts.delete_analysis(db, user["id"], saved) and accounts.list_analyses(db, user["id"]) == [])

    accounts.save_analysis(db, user["id"], "", SQUARE, [], "2026-06-01", "2026-08-31", FAKE_RESULT)
    check("16. an empty name becomes 'Untitled field'",
          accounts.list_analyses(db, user["id"])[0]["name"] == "Untitled field")
    db.close()

print(f"\nAll {passed} account tests passed.")
