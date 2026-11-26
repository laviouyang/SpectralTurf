"""
assistant.py - Stage 10 Step 10: "Ask SpectralTurf", an AI assistant (agent) that answers
questions about the user's fields using Google Gemini with FUNCTION CALLING (tool use).

How it works (the "agent loop"):
  1. The user's question goes to Gemini together with a list of TOOLS it may call.
  2. Gemini answers either with text, or with "please call tool X with these inputs".
  3. Our code runs the tool (read-only, using the app's existing code) and sends the
     result back. Repeat (at most MAX_TOOL_ROUNDS times) until Gemini writes its answer.
  4. Before showing the answer, our code CHECKS it:
       - every number and date in it must appear in a tool result (no invented numbers),
       - no watering amounts / schedules and no "the cause is ..." claims.
     If the check fails, Gemini gets one chance to fix it; otherwise the answer is not shown.

Tools (all READ ONLY; a field is "screen" = the field drawn on the map, or "field-1",
"field-2", ... = the logged-in user's OWN saved fields):
  get_my_fields                    which fields the user can ask about
  get_latest_analysis(field)       the latest NDVI/NDMI analysis + inspection result (observation)
  get_expected_vs_observed(field)  Stage 10 AI weather check (observation vs AI estimate + forecast)
  get_ranking                      Step 8 My Fields ranking (logged-in users only)
  get_field_history(field)         saved analyses + clear satellite images of the last 60 days

Photos (added 2026-11-22): the user may attach ONE photo of the field. The server re-saves it as
a small JPEG (max 1024 px), which removes hidden data such as GPS location and camera details,
sends it with the question, and never stores it. A photo is NOT a measurement: the AI may only
describe what is plainly visible and must not name a disease, pest or cause from it.

Privacy: Gemini only ever sees field DATA (numbers, dates, labels like "field-1").
Never usernames, passwords, tokens, field names the user typed, or map coordinates.
The Gemini key is read from backend/.env here and never sent to the browser or logged.
"""

import base64
import io
import json
import os
import re
import time
from collections import defaultdict, deque
from datetime import date

import requests
from PIL import Image, ImageOps

import indices
import predict

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"  # gemini-2.5-flash is closed to new users (Nov 2026)

# Cost and abuse limits (project choices)
MAX_QUESTION_CHARS = 500     # longest question accepted
MESSAGES_PER_MINUTE = 5      # per logged-in user (or per visitor's address)
MESSAGES_PER_DAY = 300       # for the whole server (Gemini cost)
MAX_TOOL_ROUNDS = 6          # stops a runaway agent loop
GEMINI_TIMEOUT_S = 90

# Photo limits (project choices)
MAX_PHOTO_BYTES = 8 * 1024 * 1024      # uploaded file size
MAX_PHOTO_PIXELS = 50_000_000          # refuses absurd "image bombs"
PHOTO_SIDE = 1024                      # the photo Gemini sees is at most 1024 px wide/high
PHOTO_FORMATS = {"JPEG", "PNG", "WEBP"}

UI_LABEL = "AI-generated explanation based on SpectralTurf data. Confirm in person."
NOT_SET_UP = ("Ask SpectralTurf is not available right now: the server has no working Gemini key. "
              "Everything else in SpectralTurf still works.")
BLOCKED = ("Sorry, the AI's answer did not pass SpectralTurf's safety checks (numbers must come "
           "from SpectralTurf data; no watering advice or causes), so it is not shown. "
           "Try asking more simply, or use the panels above.")

SYSTEM_PROMPT = """You are "Ask SpectralTurf", the assistant inside SpectralTurf AI, a student-built
app that uses Sentinel-2 satellite images and weather to suggest which grass sports fields may
warrant an in-person inspection.

Rules (always follow them):
1. Get facts ONLY by calling the tools. Every number and date you write must be copied exactly
   from a tool result. Never calculate, add, subtract, average, convert or round numbers yourself.
   Write dates as YYYY-MM-DD. A fraction (0 to 1) may be written as a percentage (0.25 = 25%).
2. Label every number as one of: "observation" (measured from a satellite image; always give the
   image date), "AI estimate" (what the model expected, or a cloudy-day estimate; not a
   measurement), "forecast" (next-week risk, uses forecast weather) or "scenario".
3. When you use an observation, also mention its data quality (clear fraction / cloud cover / warnings).
4. If a tool returns an error, insufficient evidence, off-season, or missing data, say
   "not enough data" and what is missing. Never guess.
5. Never give watering amounts, durations or schedules, and never tell the user to water more or
   less. Never diagnose disease, pests or drought, and never claim to know the cause of a change.
   You may suggest things to look at in person (for example sprinkler coverage, dry or discolored
   patches, worn areas), as things to check, not as causes.
6. SpectralTurf gives a prioritization signal, not a diagnosis. End with a short reminder to
   confirm in person.
7. You can only see the user's own saved fields ("field-1", "field-2", ...) and the field on
   screen ("screen"). Call fields by these ids. If the user is not logged in, only "screen" exists.
8. NDVI (greenness) uses 10 m pixels; NDMI (moisture) uses 20 m pixels, so never imply finer
   detail. Thresholds and rules in the app are project choices, not published standards.
9. Keep answers short (about 150 words or less), in plain language for a non-expert.
10. If the question is not about the user's fields or SpectralTurf, say you can only help with those.
11. If the user attaches a photo: it is their own photo, NOT a measurement, and you cannot know when
   or where it was taken. Describe only what is plainly visible (green, yellow or brown areas, bare or
   worn spots, standing water, lines) in plain words, and suggest where to look in person. Never name
   a disease, pest or cause from a photo, never estimate NDVI or any other number from it, and do not
   count things in it. Satellite numbers still come only from the tools.
12. If a tool result has "grass_region", mention the field's region (number and name) once, and say
   whether SpectralTurf is validated there. If it is not validated, say the baseline, color cutoff
   and AI model were made from Denver-area fields, so those results may not be accurate there."""


class AssistantError(Exception):
    """A problem the user should see as a friendly message (the rest of the app is fine)."""


class ToolDataError(Exception):
    """A tool could not get its data (e.g. the analysis download failed)."""


# ---------------------------------------------------------------------------
# Rate limits (in memory; reset when the server restarts)
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, per_minute=MESSAGES_PER_MINUTE, per_day=MESSAGES_PER_DAY):
        self.per_minute, self.per_day = per_minute, per_day
        self.recent = defaultdict(deque)  # who -> times of their recent questions
        self.day, self.day_count = None, 0

    def check(self, who, now=None):
        """Raises AssistantError if `who` asked too often. Otherwise counts this question."""
        now = time.time() if now is None else now
        times = self.recent[who]
        while times and now - times[0] >= 60:
            times.popleft()
        if len(times) >= self.per_minute:
            raise AssistantError(f"Please wait a minute: at most {self.per_minute} questions per minute.")
        today = date.today().isoformat()
        if self.day != today:
            self.day, self.day_count = today, 0
        if self.day_count >= self.per_day:
            raise AssistantError("Ask SpectralTurf has reached its daily limit. Please try again tomorrow.")
        times.append(now)
        self.day_count += 1


limiter = RateLimiter()


# ---------------------------------------------------------------------------
# The user's context: what this person is allowed to see
# ---------------------------------------------------------------------------

class Context:
    """Everything the tools may use for ONE question.
    saved:          accounts.list_analyses(db, user_id) for the logged-in user (their rows only),
                    or [] for a visitor. The tools never look anything up elsewhere.
    screen:         {"geometry", "exclusions", "start", "end", "max_cloud"} of the field on the map, or None.
    analyze_screen: function that runs the normal analysis for the field on screen (or None).
    as_of:          the date questions are answered for."""

    def __init__(self, logged_in, saved, screen, analyze_screen, as_of, focus=None):
        self.logged_in = logged_in
        # Version 2 (2026-11-25): the ONE field the user picked ("screen" or "field-N"), or None.
        # When set, the tools refuse every other field, so answers are about that field only.
        self.focus = focus
        # Added 2026-11-25: the grass region (regions.describe) of the field the questions are about.
        self.grass_region = None
        self.saved = saved if logged_in else []
        self.screen = screen
        self.analyze_screen = analyze_screen
        self.as_of = as_of
        # field-1, field-2, ... = one per saved field name, newest first (same as My Fields)
        self.fields = {f"field-{n}": f for n, f in enumerate(predict.distinct_saved_fields(self.saved), 1)}
        self.label_of_id = {f["id"]: label for label, f in self.fields.items()}

    def field_names(self):
        """label -> the name the user typed. Shown in the browser only, never sent to Gemini."""
        return {label: f["name"] for label, f in self.fields.items()}

    def find(self, field_id):
        """The field for a tool, ONLY from this user's own fields or the field on screen."""
        field_id = str(field_id or "").strip().lower()
        if self.focus and field_id != self.focus:
            raise ToolDataError(f"The user picked one field ('{self.focus}'). Only that field can be used.")
        if field_id == "screen":
            if not self.screen:
                raise ToolDataError("No field is drawn on the map.")
            return "screen", self.screen["geometry"], self.screen["exclusions"]
        if not self.logged_in:
            raise ToolDataError("Not logged in: only the field on screen ('screen') is available.")
        field = self.fields.get(field_id)
        if field is None:
            raise ToolDataError(f"There is no field '{field_id}' in your fields. "
                                f"Your fields: {', '.join(self.fields) or 'none saved yet'}.")
        return field_id, field["geometry"], field["exclusions"]

    def label_for_saved_id(self, saved_id):
        """Version 2: the 'field-N' label of one of THIS user's saved analyses (by its id), or None."""
        for s in self.saved:
            if s["id"] == saved_id:
                key = json.dumps([s["geometry"], s["exclusions"]], sort_keys=True)
                for label, f in self.fields.items():
                    if json.dumps([f["geometry"], f["exclusions"]], sort_keys=True) == key:
                        return label
        return None

    def saved_for(self, field_id):
        """This user's saved analyses of one field (same outline + exclusions), newest first."""
        field = self.fields.get(field_id)
        if field is None:
            return []
        key = json.dumps([field["geometry"], field["exclusions"]], sort_keys=True)
        return [s for s in self.saved if json.dumps([s["geometry"], s["exclusions"]], sort_keys=True) == key]


# ---------------------------------------------------------------------------
# Tools: each returns small JSON with only field data (no names, no coordinates)
# ---------------------------------------------------------------------------

def flag_rules():
    """How the inspection flags work, from the app's own settings (indices.py)."""
    return (f"A field 'may warrant inspection' if at least {indices.FLAG_MIN_FRACTION:.0%} of its checked "
            f"pixels (and at least {indices.FLAG_MIN_PIXELS}) are: NDVI {indices.LOW_NDVI_MARGIN} or more "
            f"below the field median, or below the healthy-turf baseline (NDVI < {indices.BASELINE_NDVI} or "
            f"NDMI < {indices.BASELINE_NDMI}), or yellower than NGRDI {indices.YELLOW_NGRDI}. If "
            f"{indices.WHOLE_FIELD_FRACTION:.0%} or more fail, 'most of this field'. These are project "
            "choices, not published standards.")


def analysis_facts(result):
    """The parts of a full analysis (main.run_analysis output) that matter for questions."""
    inspection = result.get("inspection") or {}
    pixels = result.get("pixels") or {}
    obs = result.get("observation") or {}
    facts = {
        "kind": "observation",
        "image_date": obs.get("date"),
        "tile_cloud_cover_percent": obs.get("tile_cloud_cover"),
        "clear_fraction_of_field": pixels.get("valid_fraction"),
        "clear_pixels": pixels.get("valid_after_masking"),
        "status": result.get("status"),
        "ndvi_median": (result.get("ndvi") or {}).get("median"),
        "ndmi_median": (result.get("ndmi") or {}).get("median"),
        "ngrdi_median": (result.get("ngrdi") or {}).get("median"),
        "inspection": {
            "status": inspection.get("status"),
            "scope": inspection.get("scope"),
            "headline": inspection.get("headline"),
            "reason": inspection.get("reason"),
            "low_fraction": inspection.get("low_fraction"),
            "yellow_fraction": (inspection.get("color") or {}).get("yellow_fraction"),
            "below_baseline_fraction": (inspection.get("baseline") or {}).get("below_fraction"),
        },
        "data_quality_warnings": result.get("warnings") or [],
        "excluded_areas": (result.get("excluded") or {}).get("areas", 0),
        "how_flags_work": flag_rules(),
    }
    if result.get("status") == "insufficient_evidence":
        facts["note"] = "Insufficient evidence: too few clear pixels. The numbers are not reliable."
        facts.pop("ndvi_median"), facts.pop("ndmi_median"), facts.pop("ngrdi_median")
    return facts


def saved_facts(item):
    """One saved analysis (summary only; the backend computed it when it was saved)."""
    s = item["summary"]
    if s.get("status") == "not_analyzed":  # Version 2: saved with "Save" only, no measurement
        return {"kind": "saved outline only", "status": "not_analyzed",
                "explanation": "This field was saved without an analysis, so there are no saved measurements. "
                        "Use the satellite history or the AI weather check for numbers."}
    facts = {
        "kind": "observation",
        "image_date": item["observation_date"],
        "date_range_searched": [item["start"], item["end"]],
        "tile_cloud_cover_percent": s.get("tile_cloud_cover"),
        "clear_fraction_of_field": s.get("valid_fraction"),
        "status": s.get("status"),
        "ndvi_median": s.get("ndvi_median"),
        "ndmi_median": s.get("ndmi_median"),
        "ngrdi_median": s.get("ngrdi_median"),
        "inspection_status": s.get("inspection_status"),
        "inspection_scope": s.get("inspection_scope"),
        "inspection_headline": s.get("inspection_headline"),
        "number_of_data_quality_warnings": s.get("warnings"),
    }
    if s.get("status") == "insufficient_evidence":
        for key in ("ndvi_median", "ndmi_median", "ngrdi_median"):
            facts.pop(key)
        facts["note"] = "Insufficient evidence: too few clear pixels."
    return facts


_screen_cache = {}  # analysis of the field on screen, so repeated questions don't re-download


def tool_get_my_fields(ctx, args):
    if ctx.focus:  # Version 2: the user picked one field; only that one is listed
        if ctx.focus == "screen":
            entry = {"field_id": "screen", "what": "the field drawn on the map now (not necessarily saved)"}
        else:
            saves = ctx.saved_for(ctx.focus)
            entry = {"field_id": ctx.focus, "saved_analyses": len(saves),
                     "latest_image_date": saves[0]["observation_date"] if saves else None,
                     "latest_inspection_headline": saves[0]["summary"].get("inspection_headline") if saves else None}
        return {"logged_in": ctx.logged_in, "fields": [entry],
                "note": "The user picked this one field. Answer only about it."}
    fields = [{"field_id": "screen", "what": "the field drawn on the map now (not necessarily saved)"}] \
        if ctx.screen else []
    if not ctx.logged_in:
        return {"logged_in": False, "fields": fields,
                "note": "Not logged in: only the field on screen can be used. Log in to use saved fields."}
    for label in ctx.fields:
        saves = ctx.saved_for(label)
        fields.append({"field_id": label, "saved_analyses": len(saves),
                       "latest_image_date": saves[0]["observation_date"] if saves else None,
                       "latest_inspection_headline": saves[0]["summary"].get("inspection_headline") if saves else None})
    return {"logged_in": True, "fields": fields,
            "note": None if ctx.fields else "No saved fields yet: analyze a field while logged in."}


def tool_get_latest_analysis(ctx, args):
    field_id, geometry, exclusions = ctx.find(args.get("field_id"))
    if field_id == "screen":
        if ctx.analyze_screen is None:
            raise ToolDataError("The field on screen has not been analyzed yet (click Analyze first).")
        key = json.dumps(ctx.screen, sort_keys=True, default=str)  # outline, exclusions and dates
        if key not in _screen_cache:
            if len(_screen_cache) > 50:
                _screen_cache.clear()
            _screen_cache[key] = analysis_facts(ctx.analyze_screen())
        return {"field_id": "screen", **_screen_cache[key]}
    saves = ctx.saved_for(field_id)
    return {"field_id": field_id, "source": "latest saved analysis", **saved_facts(saves[0]),
            "how_flags_work": flag_rules(),
            "note": "Saved analyses keep only a summary (which pixels were flagged is not stored)."}


def tool_get_expected_vs_observed(ctx, args):
    field_id, geometry, exclusions = ctx.find(args.get("field_id"))
    check = predict.weather_check(geometry, exclusions, ctx.as_of)
    return {"field_id": field_id, **check_facts(check)}


def check_facts(check):
    """The AI weather check, with every number labeled observation / AI estimate / forecast."""
    out = {"as_of": check.get("as_of"), "status": check.get("status"), "message": check.get("message"),
           "accuracy_note": check.get("accuracy_note"), "typical_error": check.get("typical_error"),
           "clear_images_in_last_60_days": check.get("clear_dates_found"),
           "geometry_note": check.get("geometry_note")}
    if check.get("status") == "ok":
        c = check.get("check") or {}
        out["observation"] = {"kind": "observation", "image_date": check.get("last_image_date"),
                              "ndvi": check.get("actual_ndvi"),
                              "clear_fraction": check.get("latest_clear_fraction"),
                              "weather_last_14_days": check.get("weather_last_14_days")}
        out["ai_estimate"] = {"kind": "AI estimate (not a measurement)", "status": c.get("status"),
                              "what": "NDVI the AI expected on the observation's image date, predicted "
                                      "from the earlier image + real weather",
                              "expected_for_image_date": check.get("last_image_date"),
                              "predicted_from_image_date": check.get("previous_image_date"),
                              "expected_ndvi": c.get("expected_ndvi"),
                              "observed_minus_expected": c.get("difference"),
                              "weather_explains": c.get("weather_explains"), "message": c.get("message")}
        risk = check.get("risk_next_week") or {}
        out["forecast"] = {"kind": "forecast", "target_date": risk.get("target_date"),
                           "risk_level": risk.get("level"), "predicted_ndvi": risk.get("predicted_ndvi"),
                           "predicted_change": risk.get("predicted_change"), "message": risk.get("message"),
                           "weather_next_7_days": risk.get("weather_next_7_days"),
                           "normal_weather_next_7_days": risk.get("normal_next_7_days"),
                           "note": risk.get("note"),
                           "risk_rule": "High = expected drop at least 2x the typical error, Medium = at "
                                        "least 1x (project choices)."}
    cloudy = check.get("cloudy_estimate")
    if cloudy:
        out["cloudy_day_estimate"] = {"kind": "AI estimate, not a measurement", **{
            k: cloudy.get(k) for k in ("status", "estimate_date", "estimated_ndvi", "typical_error",
                                       "last_clear_date", "last_clear_ndvi", "days_without_clear_image",
                                       "message")}}
    return {k: v for k, v in out.items() if v is not None}


def tool_get_ranking(ctx, args):
    if ctx.focus:
        raise ToolDataError(f"The user picked one field ('{ctx.focus}'), so there is no ranking of "
                            "several fields. Use the other tools for this field.")
    if not ctx.logged_in:
        raise ToolDataError("Not logged in: the ranking needs saved fields. Only the field on screen "
                            "('screen') can be used; log in and analyze fields to rank them.")
    ranking = predict.rank_my_fields(ctx.saved, ctx.as_of)
    out = {"as_of": ranking.get("as_of"), "status": ranking.get("status"), "message": ranking.get("message"),
           "rule": ranking.get("rule"), "skipped": ranking.get("skipped"),
           "accuracy_note": ranking.get("accuracy_note"), "fields": []}
    for entry in ranking.get("fields", []):
        label = ctx.label_of_id.get(entry["field"]["id"])
        if label is None:  # never happens: the ranking is built from ctx.saved
            continue
        out["fields"].append({"rank": entry["rank"], "field_id": label, **check_facts(entry["result"])})
    return {k: v for k, v in out.items() if v is not None}


def tool_get_field_history(ctx, args):
    field_id, geometry, exclusions = ctx.find(args.get("field_id"))
    out = {"field_id": field_id}
    if field_id != "screen":
        out["saved_analyses"] = [saved_facts(s) for s in ctx.saved_for(field_id)[:20]]
    snap = predict.field_snapshot(geometry, exclusions, ctx.as_of)
    out["clear_satellite_images_last_60_days"] = {
        "kind": "observation", "up_to": ctx.as_of.isoformat(),
        "rule": "Only days with at least 80% of the field clear of clouds (a project choice).",
        "images": [{"image_date": r["date"], "ndvi_mean": r["ndvi_mean"], "clear_fraction": r["clear_fraction"]}
                   for r in snap["clear"]]}
    if snap.get("geometry_note"):
        out["geometry_note"] = snap["geometry_note"]
    return out


FIELD_PARAM = {"type": "object", "required": ["field_id"],
               "properties": {"field_id": {"type": "string",
                                           "description": "'screen' (the field on the map) or one of the "
                                                          "user's own fields, e.g. 'field-1'"}}}
TOOLS = {
    "get_my_fields": (tool_get_my_fields, "List the fields this user can ask about.", None),
    "get_latest_analysis": (tool_get_latest_analysis,
                            "Latest satellite analysis of a field: image date, data quality, NDVI/NDMI, "
                            "and whether it may warrant inspection (and why).", FIELD_PARAM),
    "get_expected_vs_observed": (tool_get_expected_vs_observed,
                                 "AI weather check: observed NDVI vs what the AI expected from weather, "
                                 "next-week risk forecast, and a cloudy-day AI estimate.", FIELD_PARAM),
    "get_ranking": (tool_get_ranking, "Rank the user's saved fields: which to inspect first "
                                      "(logged-in users only).", None),
    "get_field_history": (tool_get_field_history,
                          "History of a field: saved analyses and clear satellite images of the last 60 days.",
                          FIELD_PARAM),
}


def gemini_tools():
    declarations = []
    for name, (_, description, params) in TOOLS.items():
        d = {"name": name, "description": description}
        if params:
            d["parameters"] = params
        declarations.append(d)
    return [{"functionDeclarations": declarations}]


def run_tool(name, args, ctx):
    """Run one tool. Problems become {"error": ...} so Gemini can say 'not enough data'."""
    if name not in TOOLS:
        return {"error": f"Unknown tool '{name}'."}
    try:
        result = TOOLS[name][0](ctx, args or {})
    except (ToolDataError, predict.PredictError) as e:
        return {"error": str(e)}
    if ctx.grass_region and isinstance(result, dict):  # added 2026-11-25: region + validated or not
        result["grass_region"] = ctx.grass_region
    return result


# ---------------------------------------------------------------------------
# Talking to Gemini (REST; the key goes in a header, never in a URL or a log)
# ---------------------------------------------------------------------------

def call_gemini(contents):
    """One Gemini request. Returns the model's message ({"role": "model", "parts": [...]}).
    Tests replace this function with a fake, so they need no internet and no key."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise AssistantError(NOT_SET_UP)
    model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    body = {"systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents, "tools": gemini_tools(),
            # Short thinking: these questions only need tool lookups, and it is much faster.
            "generationConfig": {"thinkingConfig": {"thinkingLevel": "low"}}}
    try:
        response = requests.post(GEMINI_URL.format(model=model), headers={"x-goog-api-key": key},
                                 json=body, timeout=GEMINI_TIMEOUT_S)
    except requests.Timeout:
        raise AssistantError("Gemini took too long to answer. Please try again.")
    except requests.RequestException:
        raise AssistantError("Could not reach Gemini. Check the internet connection and try again.")
    if response.status_code in (400, 401, 403) and "key" in response.text.lower():
        raise AssistantError(NOT_SET_UP)
    if response.status_code == 429:
        raise AssistantError("Gemini's usage limit was reached. Please try again later.")
    if response.status_code >= 500:
        raise AssistantError("Gemini is busy right now. Please try again in a minute.")
    if response.status_code != 200:
        raise AssistantError(f"Gemini could not answer (HTTP {response.status_code}).")
    candidates = response.json().get("candidates") or []
    if not candidates or not candidates[0].get("content", {}).get("parts"):
        raise AssistantError("Gemini gave no answer to this question. Try asking it differently.")
    return candidates[0]["content"]


# ---------------------------------------------------------------------------
# Checking the answer in code (not just trusting the prompt)
# ---------------------------------------------------------------------------

DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
WATERING_RE = re.compile(
    r"\b(water|irrigat\w*|sprinkl\w*)\b[^.!?\n;]{0,60}?\b\d+(\.\d+)?\s*(mm|cm|in|inch(es)?|min(ute)?s?|"
    r"hours?|hrs?|gallons?|liters?|litres?|times)\b(?!\s*(of )?rain)"
    r"|\b\d+(\.\d+)?\s*(mm|cm|inch(es)?|min(ute)?s?|gallons?|liters?|litres?)\b[^.!?\n]{0,40}?\b(of )?(water|irrigation)\b"
    r"|\b(water|irrigate)\b[^.!?\n]{0,30}?\b(every (day|morning|evening|night|other day|week)|daily|twice a|"
    r"once a|times a (day|week))\b"
    r"|\b(water|irrigate) (more|less|longer|deeply)\b",
    re.IGNORECASE)
CAUSE_RE = re.compile(
    r"(?<!not )(?<!n't )(?<!no )\b(caused by|the cause (is|was)|is due to|was due to|because of (drought|disease|"
    r"fungus|fungi|insects|grubs|pests|heat|overwatering|underwatering))\b"
    r"|\b(has|have|is suffering from) (a )?(disease|fungus|fungal infection|grubs|pests|drought stress)\b",
    re.IGNORECASE)

# "This looks like dollar spot" = a diagnosis. Saying you CAN'T identify diseases is fine.
DISEASE_RE = re.compile(
    r"\b(looks like|appears to be|is likely|is probably|probably|likely|could be|might be|may be|"
    r"consistent with|signs of|symptoms of|suggests?)\b[^.!?\n]{0,25}?\b(brown patch|dollar spot|"
    r"necrotic ring spot|fairy ring|snow mold|pythium|leaf spot|rust disease|summer patch|"
    r"red thread|grubs?|chinch bugs?|billbugs?|fungus|fungal|disease|drought stress|heat stress)\b",
    re.IGNORECASE)


def numbers_in(text):
    return [float(x) for x in NUMBER_RE.findall(text)]


def unsupported_numbers(answer, sources):
    """Numbers / dates in the answer that do NOT appear in `sources` (tool results, the question,
    the rules). Rounding is allowed (0.6234 -> 0.62) and fractions may be shown as % (0.05 -> 5%)."""
    source_text = " ".join(sources)
    allowed_dates = set(DATE_RE.findall(source_text))
    allowed = numbers_in(source_text)
    bad = [d for d in DATE_RE.findall(answer) if d not in allowed_dates]
    rest = DATE_RE.sub(" ", answer)
    for m in NUMBER_RE.finditer(rest):
        token = m.group()
        value = float(token)
        decimals = len(token.split(".")[1]) if "." in token else 0
        percent = rest[m.end():m.end() + 2].lstrip().startswith("%")
        half = 0.5 * 10 ** -decimals + 1e-9  # rounding to the answer's decimals is fine
        ok = any(abs(a - value) <= half if decimals else a == value for a in allowed)
        if percent and not ok:  # 0.037 may be written as 3.7% or 4%
            ok = any(abs(a * 100 - value) <= half for a in allowed)
        if not ok:
            bad.append(token)
    return bad


def rule_problems(answer, sources):
    problems = []
    bad = unsupported_numbers(answer, sources)
    if bad:
        problems.append(f"these numbers/dates are not in any tool result: {', '.join(sorted(set(bad)))}")
    if WATERING_RE.search(answer):
        problems.append("it gives watering amounts, schedules or instructions")
    if CAUSE_RE.search(answer):
        problems.append("it claims to know a cause or diagnoses the grass")
    if DISEASE_RE.search(answer):
        problems.append("it suggests a disease, pest or stress diagnosis")
    return problems


def clean_photo(data_b64):
    """Check an uploaded photo and re-save it as a small JPEG for Gemini. Re-saving drops all
    hidden metadata (EXIF: GPS location, camera, time). Returns base64 JPEG text."""
    try:
        raw = base64.b64decode(data_b64.split(",", 1)[-1], validate=True)  # allows "data:...;base64,"
    except ValueError:
        raise AssistantError("The photo could not be read. Please choose a JPEG, PNG or WebP image.")
    if len(raw) > MAX_PHOTO_BYTES:
        raise AssistantError(f"The photo is too big (max {MAX_PHOTO_BYTES // (1024 * 1024)} MB).")
    try:
        image = Image.open(io.BytesIO(raw))
        if image.format not in PHOTO_FORMATS:
            raise AssistantError("Please choose a JPEG, PNG or WebP photo.")
        if image.width * image.height > MAX_PHOTO_PIXELS:
            raise AssistantError("The photo has too many pixels.")
        image = ImageOps.exif_transpose(image)  # keep it the right way up before metadata is dropped
        image = image.convert("RGB")
        image.thumbnail((PHOTO_SIDE, PHOTO_SIDE))
        out = io.BytesIO()
        image.save(out, "JPEG", quality=85)  # no exif= argument -> no metadata in the new file
    except AssistantError:
        raise
    except Exception:
        raise AssistantError("The photo could not be read. Please choose a JPEG, PNG or WebP image.")
    return base64.b64encode(out.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------

def agent_loop(contents, ctx, call, used):
    """Let Gemini call tools until it writes a text answer. Fills `used` with
    (tool name, result) pairs. Returns the answer text."""
    for _ in range(MAX_TOOL_ROUNDS + 1):
        message = call(contents)
        contents.append(message)  # sent back unchanged (Gemini 3 needs its "thought signatures")
        calls = [p["functionCall"] for p in message.get("parts", []) if "functionCall" in p]
        if not calls:
            return " ".join(p.get("text", "") for p in message.get("parts", [])
                            if not p.get("thought")).strip()
        replies = []
        for fc in calls:
            result = run_tool(fc.get("name"), fc.get("args"), ctx)
            used.append((fc.get("name"), result))
            reply = {"name": fc.get("name"), "response": {"result": result}}
            if fc.get("id"):
                reply["id"] = fc["id"]
            replies.append({"functionResponse": reply})
        contents.append({"role": "user", "parts": replies})
    raise AssistantError("The AI needed too many steps for this question. Try asking more simply.")


def ask(question, ctx, call=None, photo=None):
    """Answer one question (each question is answered on its own, no chat memory).
    photo: optional base64 JPEG from clean_photo()."""
    call = call or call_gemini
    question = (question or "").strip()
    if not question:
        raise AssistantError("Please type a question.")
    if len(question) > MAX_QUESTION_CHARS:
        raise AssistantError(f"Questions can be at most {MAX_QUESTION_CHARS} characters.")

    who = "logged in" if ctx.logged_in else "not logged in"
    screen = "a field is drawn on the map ('screen')" if ctx.screen else "no field is drawn on the map"
    attached = "; the user attached a photo (not a measurement, see rule 11)" if photo else ""
    picked = f"; the user picked ONE field ('{ctx.focus}'): answer only about that field" if ctx.focus else ""
    if ctx.grass_region:  # added 2026-11-25 (rule 12)
        picked += (f"; the field is in grass {ctx.grass_region['label']} "
                   f"({ctx.grass_region['status']})")
    intro = f"[Context: the user is {who}; {screen}{picked}; answer as of {ctx.as_of.isoformat()}{attached}.]\n"
    contents = [{"role": "user", "parts": [{"text": intro + question}]}]
    if photo:
        contents[0]["parts"].append({"inlineData": {"mimeType": "image/jpeg", "data": photo}})
    used = []
    answer = agent_loop(contents, ctx, call, used)

    sources = [json.dumps(result) for _, result in used] + [intro, question, SYSTEM_PROMPT]
    problems = rule_problems(answer, sources) if answer else ["the answer was empty"]
    if problems:  # one chance to fix it
        contents.append({"role": "user", "parts": [{"text":
            "Your answer broke SpectralTurf's rules: " + "; ".join(problems) + ". Rewrite it. Use only "
            "numbers and dates copied from tool results (call tools again if needed); if the data is "
            "missing, say 'not enough data'. No watering advice, no causes, no disease names."}]})
        answer = agent_loop(contents, ctx, call, used)
        sources = [json.dumps(result) for _, result in used] + [intro, question, SYSTEM_PROMPT]
        problems = rule_problems(answer, sources) if answer else ["the answer was empty"]
    tools_used = list(dict.fromkeys(name for name, _ in used))
    names = ctx.field_names()
    mentioned = {label: names[label] for label in names if re.search(rf"\b{label}\b", answer or "")}
    if problems:
        return {"status": "blocked", "answer": BLOCKED, "tools_used": tools_used, "field_names": {},
                "label": UI_LABEL}
    return {"status": "ok", "answer": answer, "tools_used": tools_used, "field_names": mentioned,
            "label": UI_LABEL, "photo_used": bool(photo)}
