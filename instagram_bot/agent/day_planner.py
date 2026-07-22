"""Split one day's instruction into small, self-contained session goals.

The bot only ever sees ONE goal at a time, so each generated session goal must
carry its own niche/context. Related actions on the same post are kept together.
"""

import json
import random
import re

from instagram_bot.agent.prompt_store import render

MAX_SESSIONS = 12


def _break_bounds() -> tuple[int, int]:
    """Read fresh each call so a Settings-tab edit applies to the next plan
    without restarting the backend."""
    from instagram_bot.config import settings_store
    settings_store.refresh()
    lo = settings_store.get_int("PLAN_MIN_BREAK_MINUTES")
    hi = settings_store.get_int("PLAN_MAX_BREAK_MINUTES")
    return lo, max(hi, lo)


def _fallback_plan(day_goal: str) -> list[dict]:
    """Used when Gemini is unavailable or returns unusable JSON — run the whole
    thing as a single session rather than failing the day outright."""
    return [{"goal": day_goal.strip(), "break_minutes": 0}]


def _coerce(raw: str) -> list[dict]:
    """Parse the model's JSON array, tolerating markdown fences / stray prose."""
    text = (raw or "").strip()
    if "```" in text:
        # take the fenced block body
        parts = text.split("```")
        text = max(parts, key=len)
        text = re.sub(r"^\s*json", "", text, flags=re.I).strip()
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        text = match.group(0)
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("planner did not return a list")
    return data


def _sanitize(items: list[dict], caps: dict) -> list[dict]:
    min_break, max_break = _break_bounds()
    sessions: list[dict] = []
    for item in items[:MAX_SESSIONS]:
        if not isinstance(item, dict):
            continue
        goal = str(item.get("goal", "")).strip()
        if not goal:
            continue
        try:
            brk = int(item.get("break_minutes", 0))
        except (TypeError, ValueError):
            brk = random.randint(min_break, max_break)
        # Clamp to sane bounds so a bad model answer can't stall the day or spam.
        brk = max(0, min(brk, max_break * 2))
        sessions.append({"goal": goal, "break_minutes": brk})

    if not sessions:
        return []

    # The final session never needs a trailing break.
    sessions[-1]["break_minutes"] = 0
    return sessions


def default_daily_caps() -> dict:
    from instagram_bot.config import settings_store
    settings_store.refresh()
    return {
        "comments": settings_store.get_int("DAILY_CAP_COMMENTS"),
        "likes": settings_store.get_int("DAILY_CAP_LIKES"),
        "dms": settings_store.get_int("DAILY_CAP_DMS"),
        "follows": settings_store.get_int("DAILY_CAP_FOLLOWS"),
    }


def plan_day(day_goal: str, caps: dict | None = None, gemini=None) -> list[dict]:
    """Return [{goal, break_minutes}, ...] for the given day-long instruction."""
    caps = caps or default_daily_caps()
    caps_text = ", ".join(f"{k}: {v}" for k, v in caps.items())

    if gemini is None:
        try:
            from instagram_bot.agent.gemini_client import GeminiAgent
            gemini = GeminiAgent()
        except Exception as exc:
            print(f"  [planner] Gemini unavailable ({exc}) — single-session fallback")
            return _fallback_plan(day_goal)

    min_break, max_break = _break_bounds()
    prompt = render(
        "day_planner",
        day_goal=day_goal,
        min_break=min_break,
        max_break=max_break,
        caps=caps_text,
    )

    try:
        raw = gemini.complete_text(prompt, temperature=0.6)
        sessions = _sanitize(_coerce(raw), caps)
        if not sessions:
            raise ValueError("no usable sessions parsed")
        print(f"  [planner] Split day into {len(sessions)} session(s)")
        return sessions
    except Exception as exc:
        print(f"  [planner] Planning failed ({exc}) — single-session fallback")
        return _fallback_plan(day_goal)
