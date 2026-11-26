"""
limits.py - Safety limits for running SpectralTurf as a public website (added 2026-11-22).

Why: every new satellite analysis spends our free Copernicus quota, and every chat message
spends our Gemini quota. Without limits, one person (or a bot) could use them all up.

What is limited (all numbers are project choices, not standards; change them with the
environment variables named in brackets):
  - Wrong passwords: 5 wrong passwords for one username within 15 minutes locks that username
    for 15 minutes. 20 wrong passwords from one internet address within 15 minutes locks that
    address too. (The same rule applies to usernames that don't exist, so the lock message
    doesn't reveal which usernames exist.)
  - New accounts: 5 per internet address per day, 100 per day for the whole server.
  - Per day, per logged-in user / per visitor's internet address / for the whole server:
      new satellite analyses ("analysis")         30 / 10 / 300
      AI checks: weather check, What if?, My Fields ("ai_check")   200 / 100 / 2000
      chat messages to Ask SpectralTurf ("chat")   40 / 15 / 300
      photo checks, "Check a photo" ("photo"; login only)   50 / - / 1000   (added 2026-11-26)
    The AI checks also keep their own Copernicus budget (predict.DAILY_PU_BUDGET).
  - "Per day" means per calendar day on the server's clock (UTC on Render).

When are the limits on?
  Only when the app runs on Render (Render sets the RENDER variable automatically) or when
  USAGE_LIMITS=on. On your own computer nothing changes. USAGE_LIMITS=off turns them off.

The counts are kept in a small SQLite file next to the accounts database (usage_limits.db),
so they survive restarts. It stores only counts per day and failed-login times, keyed by
user id, lower-case username (failed logins only) or internet address.

Visitors are told apart by internet address. That is "best effort": people on the same
school Wi-Fi share one address, and a determined person can change theirs. The whole-server
limits are what really protect the quotas.
"""

import json
import os
import sqlite3
import threading
import time
from datetime import date

import accounts


def number(name, default):
    """A limit from an environment variable, or the default."""
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


# Per day: (each logged-in user, each visitor address, whole server)
DAILY_LIMITS = {
    "analysis": (number("LIMIT_ANALYSES_PER_USER", 30), number("LIMIT_ANALYSES_PER_VISITOR", 10),
                 number("LIMIT_ANALYSES_TOTAL", 300)),
    "ai_check": (number("LIMIT_AI_CHECKS_PER_USER", 200), number("LIMIT_AI_CHECKS_PER_VISITOR", 100),
                 number("LIMIT_AI_CHECKS_TOTAL", 2000)),
    "chat": (number("LIMIT_CHAT_PER_USER", 40), number("LIMIT_CHAT_PER_VISITOR", 15),
             number("LIMIT_CHAT_TOTAL", 300)),
    "signup": (None, number("LIMIT_SIGNUPS_PER_ADDRESS", 5), number("LIMIT_SIGNUPS_TOTAL", 100)),
    # Added 2026-11-26: "Check a photo" (login only; the visitor number never applies -> 401 first).
    "photo": (number("LIMIT_PHOTOS_PER_USER", 50), number("LIMIT_PHOTOS_PER_VISITOR", 10),
              number("LIMIT_PHOTOS_TOTAL", 1000)),
}

# Which website requests count as which kind.
KIND_OF_PATH = {
    "/api/analyze": "analysis",
    "/api/test/indices": "analysis",
    "/api/test/truecolor": "analysis",
    "/api/ai/weather-check": "ai_check",
    "/api/ai/what-if": "ai_check",
    "/api/ai/my-fields": "ai_check",
    "/api/ai/ask": "chat",
    "/api/auth/signup": "signup",
    "/api/photo/classify": "photo",  # added 2026-11-26
}

WHAT = {"analysis": "new satellite analyses", "ai_check": "AI checks (weather check, What if?, My Fields)",
        "chat": "Ask SpectralTurf questions", "signup": "new accounts", "photo": "photo checks"}

LOGIN_WINDOW_S = 15 * 60
MAX_FAILS_PER_USERNAME = 5
MAX_FAILS_PER_ADDRESS = 20


class LimitReached(Exception):
    """A friendly message for the user (the website shows it as-is)."""


def enabled():
    setting = os.getenv("USAGE_LIMITS", "").strip().lower()
    if setting in ("off", "0", "false", "no"):
        return False
    return setting in ("on", "1", "true", "yes") or bool(os.getenv("RENDER"))


def db_path():
    """LIMITS_DB_PATH, or usage_limits.db in the same folder as the accounts database
    (so on Render it lands on the persistent disk too)."""
    return os.getenv("LIMITS_DB_PATH") or os.path.join(
        os.path.dirname(os.path.abspath(accounts.DB_PATH)), "usage_limits.db")


_lock = threading.Lock()  # one check-and-count at a time


def connect():
    db = sqlite3.connect(db_path(), timeout=10)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS daily_counts (
            day   TEXT NOT NULL,
            kind  TEXT NOT NULL,
            who   TEXT NOT NULL,   -- "user:<id>", "ip:<address>" or "total"
            count INTEGER NOT NULL,
            PRIMARY KEY (day, kind, who)
        );
        CREATE TABLE IF NOT EXISTS login_failures (
            who  TEXT NOT NULL,    -- "name:<lower-case username>" or "ip:<address>"
            time REAL NOT NULL
        );
        """
    )
    return db


def _count(db, day, kind, who):
    row = db.execute("SELECT count FROM daily_counts WHERE day = ? AND kind = ? AND who = ?",
                     (day, kind, who)).fetchone()
    return row[0] if row else 0


def check(kind, who, logged_in, today=None):
    """Raise LimitReached if this person (or the whole server) used up today's `kind`."""
    per_user, per_visitor, total = DAILY_LIMITS[kind]
    own_limit = per_user if logged_in else per_visitor
    day = (today or date.today()).isoformat()
    with _lock:
        db = connect()
        try:
            if _count(db, day, kind, "total") >= total:
                raise LimitReached(
                    f"SpectralTurf has reached today's limit of {total} {WHAT[kind]} for everyone "
                    "(this protects the free data quotas). Please try again tomorrow.")
            if own_limit is not None and _count(db, day, kind, who) >= own_limit:
                if kind == "signup":
                    raise LimitReached("Too many new accounts were made from this internet connection "
                                       "today. Please try again tomorrow.")
                extra = "" if logged_in else " Visitors get fewer than logged-in users."
                raise LimitReached(f"You've reached today's limit of {own_limit} {WHAT[kind]}. "
                                   f"It resets tomorrow.{extra} Saved results still work.")
        finally:
            db.close()


def record(kind, who, today=None):
    """Count one use for this person and for the whole server."""
    day = (today or date.today()).isoformat()
    with _lock:
        db = connect()
        try:
            for name in (who, "total"):
                db.execute("INSERT INTO daily_counts (day, kind, who, count) VALUES (?, ?, ?, 1) "
                           "ON CONFLICT (day, kind, who) DO UPDATE SET count = count + 1",
                           (day, kind, name))
            db.execute("DELETE FROM daily_counts WHERE day < ?", (date.fromordinal(
                date.fromisoformat(day).toordinal() - 7).isoformat(),))  # keep one week
            db.commit()
        finally:
            db.close()


def login_lock_message(username, address, now=None):
    """A message if this username or address is locked after wrong passwords, else None."""
    now = time.time() if now is None else now
    with _lock:
        db = connect()
        try:
            db.execute("DELETE FROM login_failures WHERE time < ?", (now - LOGIN_WINDOW_S,))
            db.commit()

            def fails(who):
                return db.execute("SELECT COUNT(*) FROM login_failures WHERE who = ?", (who,)).fetchone()[0]

            minutes = LOGIN_WINDOW_S // 60
            if fails(f"name:{username.strip().lower()}") >= MAX_FAILS_PER_USERNAME:
                return (f"Too many wrong passwords for this username. For safety, please wait "
                        f"{minutes} minutes and try again.")
            if fails(f"ip:{address}") >= MAX_FAILS_PER_ADDRESS:
                return (f"Too many wrong passwords from this internet connection. Please wait "
                        f"{minutes} minutes and try again.")
            return None
        finally:
            db.close()


def login_failed(username, address, now=None):
    now = time.time() if now is None else now
    with _lock:
        db = connect()
        try:
            db.executemany("INSERT INTO login_failures (who, time) VALUES (?, ?)",
                           [(f"name:{username.strip().lower()}", now), (f"ip:{address}", now)])
            db.commit()
        finally:
            db.close()


def login_succeeded(username):
    """A correct password clears that username's wrong-password count."""
    with _lock:
        db = connect()
        try:
            db.execute("DELETE FROM login_failures WHERE who = ?", (f"name:{username.strip().lower()}",))
            db.commit()
        finally:
            db.close()


def client_address(request):
    """The visitor's internet address. On Render the app sits behind Render's proxy, so the
    real address is the first entry of the X-Forwarded-For header (only trusted when
    TRUST_PROXY_HEADERS=1, which render.yaml sets; a visitor can fake it, so per-visitor
    limits are best effort)."""
    if os.getenv("TRUST_PROXY_HEADERS") == "1":
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    return request.client.host if request.client else "unknown"


def username_from(body_bytes):
    try:
        name = json.loads(body_bytes or b"{}").get("username", "")
        return name if isinstance(name, str) else ""
    except (ValueError, AttributeError):
        return ""
