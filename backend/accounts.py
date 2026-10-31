"""
accounts.py - User accounts and saved field history for SpectralTurf AI.

Everything is stored in one small SQLite database file next to this code
(backend/spectralturf.db). SQLite is built into Python, so nothing extra is installed.
The file is listed in .gitignore, so accounts are never uploaded to GitHub.

How passwords are kept safe:
  - We NEVER store the password itself. We store a "hash": a scrambled fingerprint made
    with scrypt (built into Python's hashlib), plus a random "salt" per user.
  - At login we hash what was typed the same way and compare the two fingerprints.
  - scrypt is deliberately slow, so guessing millions of passwords would take very long.

How "staying logged in" works:
  - After login, the browser gets a long random "session token" (like a temporary key).
  - It sends that token with each request. We store only a SHA-256 hash of it, so even
    someone who copied the database file could not use the tokens in it.
  - Tokens expire after SESSION_DAYS, and logging out deletes them.

We only ask for a username and password - no email or real name - so the app collects
as little personal information as possible. (Downside: no "forgot password" email.)
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spectralturf.db")

# Project choices (not standards):
SESSION_DAYS = 30
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 200  # stops someone sending a huge "password" to slow the server
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,30}$")
MAX_SAVED_PER_USER = 500
MAX_NAME_LENGTH = 80

# scrypt settings (the commonly recommended interactive-login level).
SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


class AccountError(Exception):
    """A problem the user can fix (bad password, name taken, ...)."""


def now():
    return datetime.now(timezone.utc)


def connect(db_path=None):
    """Open the database and create the tables the first time."""
    db = sqlite3.connect(db_path or DB_PATH)
    db.row_factory = sqlite3.Row  # rows behave like dictionaries
    db.execute("PRAGMA foreign_keys = ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY,
            username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt          TEXT NOT NULL,
            created_at    TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL
        );
        -- One row per analysis a logged-in user ran. The numbers in "summary" come
        -- straight from the backend's own analysis, never from the browser.
        CREATE TABLE IF NOT EXISTS saved_analyses (
            id               INTEGER PRIMARY KEY,
            user_id          INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name             TEXT NOT NULL,
            geometry         TEXT NOT NULL,
            exclusions       TEXT NOT NULL,
            start_date       TEXT NOT NULL,
            end_date         TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            summary          TEXT NOT NULL,
            created_at       TEXT NOT NULL
        );
        """
    )
    return db


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------

def hash_password(password, salt_hex):
    return hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(salt_hex), **SCRYPT).hex()


def check_new_credentials(username, password):
    if not USERNAME_PATTERN.match(username):
        raise AccountError("Username must be 3-30 characters: letters, numbers, or _.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AccountError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise AccountError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")


# ---------------------------------------------------------------------------
# Sign up, log in, log out
# ---------------------------------------------------------------------------

def sign_up(db, username, password):
    """Create an account and return a session token (the new user is logged in)."""
    check_new_credentials(username, password)
    salt = secrets.token_hex(16)
    try:
        cursor = db.execute(
            "INSERT INTO users (username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, hash_password(password, salt), salt, now().isoformat()),
        )
    except sqlite3.IntegrityError:
        raise AccountError("That username is already taken.")
    db.commit()
    return new_session(db, cursor.lastrowid)


def log_in(db, username, password):
    """Return a session token if the username and password match."""
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if len(password) > MAX_PASSWORD_LENGTH:
        user = None
    # The same message for "no such user" and "wrong password", so the login form
    # doesn't reveal which usernames exist.
    if user is None or not hmac.compare_digest(
        hash_password(password, user["salt"]), user["password_hash"]
    ):
        raise AccountError("Wrong username or password.")
    return new_session(db, user["id"])


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_session(db, user_id):
    token = secrets.token_urlsafe(32)  # 256 random bits: impossible to guess
    expires = now() + timedelta(days=SESSION_DAYS)
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (now().isoformat(),))  # tidy up
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash(token), user_id, expires.isoformat()),
    )
    db.commit()
    return token


def user_for_token(db, token):
    """Return {id, username} for a valid, unexpired token, or None."""
    if not token:
        return None
    row = db.execute(
        "SELECT users.id, users.username, sessions.expires_at FROM sessions "
        "JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ?",
        (token_hash(token),),
    ).fetchone()
    if row is None or row["expires_at"] < now().isoformat():
        return None
    return {"id": row["id"], "username": row["username"]}


def log_out(db, token):
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    db.commit()


# ---------------------------------------------------------------------------
# Saved field history
# ---------------------------------------------------------------------------

def summary_of(result):
    """The small part of an analysis worth keeping (the map pictures are too big to store)."""
    inspection = result.get("inspection") or {}
    return {
        "status": result.get("status"),
        "tile_cloud_cover": result["observation"].get("tile_cloud_cover"),
        "valid_pixels": result["pixels"]["valid_after_masking"],
        "valid_fraction": result["pixels"]["valid_fraction"],
        "ndvi_median": result["ndvi"]["median"],
        "ndmi_median": result["ndmi"]["median"],
        "ngrdi_median": (result.get("ngrdi") or {}).get("median"),
        "inspection_status": inspection.get("status"),
        "inspection_scope": inspection.get("scope"),
        "inspection_headline": inspection.get("headline"),
        "warnings": len(result.get("warnings") or []),
    }


def save_analysis(db, user_id, name, geometry, exclusions, start, end, result):
    count = db.execute("SELECT COUNT(*) FROM saved_analyses WHERE user_id = ?", (user_id,)).fetchone()[0]
    if count >= MAX_SAVED_PER_USER:
        raise AccountError(f"History is full ({MAX_SAVED_PER_USER} analyses). Delete some old ones.")
    name = (name or "").strip()[:MAX_NAME_LENGTH] or "Untitled field"
    cursor = db.execute(
        "INSERT INTO saved_analyses (user_id, name, geometry, exclusions, start_date, end_date, "
        "observation_date, summary, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, name, json.dumps(geometry), json.dumps(list(exclusions)),
            str(start), str(end), result["observation"]["date"],
            json.dumps(summary_of(result)), now().isoformat(),
        ),
    )
    db.commit()
    return cursor.lastrowid


def list_analyses(db, user_id):
    """Newest first. Each user only ever sees their own rows."""
    rows = db.execute(
        "SELECT * FROM saved_analyses WHERE user_id = ? ORDER BY id DESC", (user_id,)
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "geometry": json.loads(row["geometry"]),
            "exclusions": json.loads(row["exclusions"]),
            "start": row["start_date"],
            "end": row["end_date"],
            "observation_date": row["observation_date"],
            "summary": json.loads(row["summary"]),
            "saved_at": row["created_at"],
        }
        for row in rows
    ]


def delete_analysis(db, user_id, analysis_id):
    """Returns True if a row was deleted. The user_id check stops deleting other people's rows."""
    cursor = db.execute(
        "DELETE FROM saved_analyses WHERE id = ? AND user_id = ?", (analysis_id, user_id)
    )
    db.commit()
    return cursor.rowcount > 0
