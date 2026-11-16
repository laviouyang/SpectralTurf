"""
check_keys.py - Stage 10 Step 10, step A: a tiny check that the keys in backend/.env work.

  1. Copernicus (CDSE): asks for a login token (the same code the app uses).
  2. Gemini: sends "Say hello." and prints Gemini's short reply.

It NEVER prints a key or the Copernicus token; only "OK" or a short error.
Run from the backend folder:   python check_keys.py
"""

import os

import requests
from dotenv import load_dotenv

import sentinel

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"  # gemini-2.5-flash is closed to new users (Nov 2026)


def check_copernicus():
    try:
        sentinel.get_token()  # the token itself is never printed
        return "OK - logged in to Copernicus"
    except sentinel.SentinelError as e:
        return f"FAILED - {e}"


def check_gemini():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return "FAILED - GEMINI_API_KEY is missing from backend/.env"
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    try:
        # The key goes in a header (not the URL), so it can't end up in a logged web address.
        response = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key},
                                 json={"contents": [{"role": "user", "parts": [{"text": "Say hello."}]}]},
                                 timeout=60)
    except requests.RequestException as e:
        return f"FAILED - could not reach Gemini ({type(e).__name__})"
    if response.status_code != 200:
        try:  # Google's short error message (it never contains the key)
            message = response.json().get("error", {}).get("message", "")[:200]
        except ValueError:
            message = ""
        return f"FAILED - Gemini answered HTTP {response.status_code}: {message}"
    parts = response.json()["candidates"][0]["content"]["parts"]
    reply = " ".join(p.get("text", "") for p in parts).strip()
    return f"OK - {model} replied: {reply[:200]}"


if __name__ == "__main__":
    load_dotenv(".env")
    print("Copernicus:", check_copernicus())
    print("Gemini:    ", check_gemini())
