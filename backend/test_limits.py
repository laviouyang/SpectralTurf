"""
test_limits.py - Tests for the public-website safety limits (limits.py) and the Render
settings (DATABASE_PATH, AI_CACHE_DIR). No internet: the satellite analysis and Gemini are faked,
and a temporary database is used (your real accounts file is never touched).

Run:  cd backend  ->  python test_limits.py
"""

import os
import subprocess
import sys
import tempfile
from datetime import date, timedelta

from fastapi.testclient import TestClient

import accounts
import assistant
import limits
import main

passed = failed = 0


def check(name, ok):
    global passed, failed
    print(("PASS  " if ok else "FAIL  ") + name)
    if ok:
        passed += 1
    else:
        failed += 1


FIELD = {"type": "Polygon", "coordinates": [[[-104.8800, 39.6340], [-104.8775, 39.6340],
                                             [-104.8775, 39.6362], [-104.8800, 39.6362],
                                             [-104.8800, 39.6340]]]}

saved_env = {k: os.environ.get(k) for k in ("USAGE_LIMITS", "RENDER", "TRUST_PROXY_HEADERS", "LIMITS_DB_PATH")}
saved_db_path, saved_limits = accounts.DB_PATH, dict(limits.DAILY_LIMITS)
saved_run, saved_ask = main.run_analysis, main.assistant.ask

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as folder:
    # ---- 1. Off on your own computer ----
    for k in ("USAGE_LIMITS", "RENDER", "TRUST_PROXY_HEADERS", "LIMITS_DB_PATH"):
        os.environ.pop(k, None)
    check("1. limits are OFF locally (no RENDER, no USAGE_LIMITS)", not limits.enabled())
    os.environ["RENDER"] = "true"
    check("2. limits turn ON automatically on Render", limits.enabled())
    os.environ["USAGE_LIMITS"] = "off"
    check("3. USAGE_LIMITS=off turns them off even on Render", not limits.enabled())
    os.environ.pop("RENDER")

    accounts.DB_PATH = os.path.join(folder, "accounts_test.db")
    check("4. the limits file sits next to the accounts database",
          limits.db_path() == os.path.join(folder, "usage_limits.db"))

    FAKE_RESULT = {"observation": {"date": "2026-08-05", "tile_cloud_cover": 0},  # no Copernicus
                   "pixels": {"valid_after_masking": 100, "valid_fraction": 1.0},
                   "ndvi": {"median": 0.7}, "ndmi": {"median": 0.2}, "status": "ok"}
    main.run_analysis = lambda *args, **kwargs: dict(FAKE_RESULT)
    main.assistant.ask = lambda *args, **kwargs: {"status": "ok", "answer": "Fake answer."}  # no Gemini
    client = TestClient(main.app)

    # Locally (limits off) everything works exactly as before, however often.
    codes = {client.post("/api/analyze", json={"geometry": FIELD}).status_code for _ in range(15)}
    check("5. limits off: 15 analyses in a row all work", codes == {200})

    os.environ["USAGE_LIMITS"] = "on"
    db = accounts.connect()
    token = accounts.sign_up(db, "Coach_A", "correct-password-1")
    token_b = accounts.sign_up(db, "coach_b", "correct-password-2")
    db.close()

    # ---- Login lockout ----
    def login(name, password, ip=None):
        headers = {"X-Forwarded-For": ip} if ip else {}
        return client.post("/api/auth/login", json={"username": name, "password": password}, headers=headers)

    codes = [login("Coach_A", "wrong").status_code for _ in range(4)]
    ok_login = login("Coach_A", "correct-password-1")
    codes_after = [login("coach_a", "wrong").status_code for _ in range(4)]
    check("6. a correct password resets the wrong-password count",
          codes == [401] * 4 and ok_login.status_code == 200 and codes_after == [401] * 4)
    login("COACH_A", "wrong")  # 5th wrong in a row (any capitalization)
    locked = login("Coach_A", "correct-password-1")
    check("7. 5 wrong passwords -> locked, even with the right password (429, friendly message)",
          locked.status_code == 429 and "wait 15 minutes" in locked.json()["detail"])
    check("8. other users are not locked", login("coach_b", "correct-password-2").status_code == 200)
    check("9. the lock ends after 15 minutes",
          limits.login_lock_message("Coach_A", "testclient") is not None
          and limits.login_lock_message("Coach_A", "testclient", now=__import__("time").time() + 901) is None)
    nobody = [login("no_such_user", "x").status_code for _ in range(6)]
    check("10. unknown usernames lock the same way (doesn't reveal which names exist)",
          nobody[:5] == [401] * 5 and nobody[5] == 429)
    for i in range(20):
        limits.login_failed(f"guess_{i}", "203.0.113.9")
    check("11. 20 wrong passwords from one address -> that address is locked for every username",
          "internet connection" in (limits.login_lock_message("coach_b", "203.0.113.9") or ""))

    # ---- Daily limits ----
    limits.DAILY_LIMITS.update({"analysis": (3, 2, 6), "chat": (2, 1, 100), "signup": (None, 2, 100)})
    visitor = [client.post("/api/analyze", json={"geometry": FIELD}).status_code for _ in range(3)]
    detail = client.post("/api/analyze", json={"geometry": FIELD}).json()["detail"]
    check("12. a visitor gets 2 analyses a day, then 429 with a friendly message",
          visitor == [200, 200, 429] and "today's limit of 2 new satellite analyses" in detail)
    auth = {"Authorization": f"Bearer {token}"}
    bad = client.post("/api/analyze", json={"geometry": {"type": "Point"}}, headers=auth)
    check("13. a rejected request (bad outline, 400) is not counted",
          bad.status_code == 400 and limits._count(limits.connect(), date.today().isoformat(), "analysis",
                                                   "total") == 2)
    user = [client.post("/api/analyze", json={"geometry": FIELD}, headers=auth).status_code for _ in range(4)]
    check("14. a logged-in user has their own, larger limit (3)", user == [200, 200, 200, 429])
    auth_b = {"Authorization": f"Bearer {token_b}"}
    other = [client.post("/api/analyze", json={"geometry": FIELD}, headers=auth_b).status_code for _ in range(2)]
    everyone = client.post("/api/analyze", json={"geometry": FIELD}, headers=auth_b)
    check("15. the whole-server limit (6) stops everyone, with its own message",
          other == [200, 429] and everyone.status_code == 429 and "for everyone" in everyone.json()["detail"])
    check("16. counts are saved in the file (survive a restart) and reset the next day",
          limits._count(limits.connect(), date.today().isoformat(), "analysis", "total") == 6
          and limits.check("analysis", "ip:testclient", False, today=date.today() + timedelta(days=1)) is None)

    chat = [client.post("/api/ai/ask", json={"question": "Hi"}).status_code for _ in range(2)]
    chat_user = [client.post("/api/ai/ask", json={"question": "Hi"}, headers=auth).status_code for _ in range(3)]
    # Visitors can't chat at all since 2026-11-25 (Version 2: login required) -> 401, not counted.
    check("17. chatbot messages have their own daily limit (user 2; visitors need to log in)",
          chat == [401, 401] and chat_user == [200, 200, 429])
    check("18. other pages are never limited (health)",
          all(client.get("/api/health").status_code == 200 for _ in range(30)))

    signups = [client.post("/api/auth/signup", json={"username": f"new_user_{i}", "password": "password-123"},
                           headers={"X-Forwarded-For": "192.0.2.50"}).status_code for i in range(3)]
    check("19. new accounts: 2 per address per day in this test, then 429", signups == [200, 200, 429])

    # ---- The visitor's address behind Render's proxy ----
    class FakeRequest:
        headers = {"x-forwarded-for": "198.51.100.7, 10.0.0.1"}
        client = type("C", (), {"host": "10.0.0.1"})()
    check("20. X-Forwarded-For is ignored unless TRUST_PROXY_HEADERS=1",
          limits.client_address(FakeRequest()) == "10.0.0.1")
    os.environ["TRUST_PROXY_HEADERS"] = "1"
    check("21. ... and used (first entry) when it is set, as on Render",
          limits.client_address(FakeRequest()) == "198.51.100.7")

    # ---- Render settings: where the files live ----
    here = os.path.dirname(os.path.abspath(__file__))
    env = dict(os.environ, DATABASE_PATH=os.path.join(folder, "disk", "db.sqlite"),
               AI_CACHE_DIR=os.path.join(folder, "disk", "cache"))
    out = subprocess.run([sys.executable, "-c", "import accounts, predict; print(accounts.DB_PATH); "
                          "print(predict.CACHE_DIR)"], cwd=here, env=env, capture_output=True, text=True)
    lines = out.stdout.split()
    check("22. DATABASE_PATH and AI_CACHE_DIR choose where the database and AI cache live",
          lines == [env["DATABASE_PATH"], env["AI_CACHE_DIR"]])
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_PATH", "AI_CACHE_DIR")}
    out = subprocess.run([sys.executable, "-c", "import accounts, predict; print(accounts.DB_PATH); "
                          "print(predict.CACHE_DIR)"], cwd=here, env=env, capture_output=True, text=True)
    check("23. not set -> the same local files as before",
          out.stdout.split() == [os.path.join(here, "spectralturf.db"), os.path.join(here, "ai_cache")])

# put everything back
accounts.DB_PATH = saved_db_path
limits.DAILY_LIMITS.clear()
limits.DAILY_LIMITS.update(saved_limits)
main.run_analysis, main.assistant.ask = saved_run, saved_ask
for k, v in saved_env.items():
    if v is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = v

print(f"\n{passed}/{passed + failed} passed")
sys.exit(1 if failed else 0)
