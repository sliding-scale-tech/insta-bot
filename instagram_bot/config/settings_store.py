"""Editable runtime settings, stored in Convex and edited from the dashboard.

The dashboard writes overrides to the Convex `settings` table; the backend
reads them here at the start of each session/day-plan. If a key is missing (or
Convex is unreachable) the built-in default from .env / settings.py is used, so
the bot always runs.

Unlike prompts (free text), these are typed — "int" values are validated and
clamped to sane bounds before use.
"""

from typing import Any

from instagram_bot.config import settings as _s

# key -> (label, description, type, default, min, max)
DEFAULTS: dict[str, dict[str, Any]] = {
    "MAX_COMMENTS_PER_SESSION": {
        "label": "Max comments per session",
        "description": "Hard cap on comments in a single bot run, regardless of what the goal asks for.",
        "type": "int", "default": _s.MAX_COMMENTS_PER_SESSION, "min": 0, "max": 50,
    },
    "MAX_LIKES_PER_SESSION": {
        "label": "Max likes per session",
        "description": "Hard cap on likes in a single bot run.",
        "type": "int", "default": _s.MAX_LIKES_PER_SESSION, "min": 0, "max": 200,
    },
    "MAX_FOLLOWS_PER_SESSION": {
        "label": "Max follows per session",
        "description": "Hard cap on follows in a single bot run.",
        "type": "int", "default": _s.MAX_FOLLOWS_PER_SESSION, "min": 0, "max": 50,
    },
    "MAX_DMS_PER_SESSION": {
        "label": "Max DMs per session",
        "description": "Hard cap on DMs sent in a single bot run.",
        "type": "int", "default": _s.MAX_DMS_PER_SESSION, "min": 0, "max": 50,
    },
    "MAX_REPLIES_PER_SESSION": {
        "label": "Max comment replies per session",
        "description": "Hard cap on replies to other people's comments in a single run.",
        "type": "int", "default": _s.MAX_REPLIES_PER_SESSION, "min": 0, "max": 50,
    },
    "SESSION_MINUTES": {
        "label": "Session length (minutes)",
        "description": "How long a single bot session runs before it ends on its own.",
        "type": "int", "default": _s.SESSION_MINUTES, "min": 1, "max": 180,
    },
    "HASHTAG_TO_SEARCH": {
        "label": "Fallback niche hashtag",
        "description": "Used only when a goal names no specific topic (e.g. \"like 5 posts\" with no niche).",
        "type": "str", "default": _s.HASHTAG_TO_SEARCH,
    },
    "PLAN_MIN_BREAK_MINUTES": {
        "label": "Day plan: minimum break (minutes)",
        "description": "Shortest randomized break the day-planner can put between sessions.",
        "type": "int", "default": 8, "min": 0, "max": 240,
    },
    "PLAN_MAX_BREAK_MINUTES": {
        "label": "Day plan: maximum break (minutes)",
        "description": "Longest randomized break the day-planner can put between sessions.",
        "type": "int", "default": 35, "min": 1, "max": 480,
    },
    "DAILY_CAP_COMMENTS": {
        "label": "Day plan: daily comment cap",
        "description": "Total comments allowed across an entire day plan (all sessions combined).",
        "type": "int", "default": 10, "min": 0, "max": 200,
    },
    "DAILY_CAP_LIKES": {
        "label": "Day plan: daily like cap",
        "description": "Total likes allowed across an entire day plan.",
        "type": "int", "default": 40, "min": 0, "max": 500,
    },
    "DAILY_CAP_DMS": {
        "label": "Day plan: daily DM cap",
        "description": "Total DMs allowed across an entire day plan.",
        "type": "int", "default": 5, "min": 0, "max": 100,
    },
    "DAILY_CAP_FOLLOWS": {
        "label": "Day plan: daily follow cap",
        "description": "Total follows allowed across an entire day plan.",
        "type": "int", "default": 10, "min": 0, "max": 200,
    },
}

_cache: dict[str, str] = {}
_loaded = False


def _load_overrides() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        from instagram_bot.db.convex_client import _client
        rows = _client().query("settings:listSettings", {})
        for row in rows or []:
            key, value = row.get("key"), row.get("value")
            if key is not None and value is not None:
                _cache[key] = value
        if _cache:
            print(f"  [settings] Loaded {len(_cache)} custom setting(s) from DB: {', '.join(_cache)}")
    except Exception as exc:
        print(f"  [settings] Using built-in defaults (DB unavailable: {exc})")


def refresh() -> None:
    """Force a re-read on next get() — call at the start of each session so a
    change made mid-day (without restarting the backend) still takes effect."""
    global _loaded
    _loaded = False
    _cache.clear()


def get_int(key: str) -> int:
    _load_overrides()
    meta = DEFAULTS.get(key, {})
    default = meta.get("default", 0)
    raw = _cache.get(key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    lo, hi = meta.get("min"), meta.get("max")
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def get_str(key: str) -> str:
    _load_overrides()
    meta = DEFAULTS.get(key, {})
    return _cache.get(key, meta.get("default", ""))


def defaults_payload() -> list[dict]:
    """Shape the dashboard uses to render the Settings tab: current effective
    value (override or default) alongside the metadata needed to edit it."""
    _load_overrides()
    out = []
    for key, meta in DEFAULTS.items():
        current = get_int(key) if meta["type"] == "int" else get_str(key)
        out.append({
            "key": key,
            "label": meta["label"],
            "description": meta["description"],
            "type": meta["type"],
            "default": meta["default"],
            "min": meta.get("min"),
            "max": meta.get("max"),
            "value": current,
            "is_custom": key in _cache,
        })
    return out
