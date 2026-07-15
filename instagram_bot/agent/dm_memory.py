"""Persistent DM memory — tracks who we've already DMd across sessions."""

import json
from datetime import datetime

from instagram_bot.config.settings import DATA_DIR

DM_FILE = DATA_DIR / "dm_sent.json"


def load_dm_sent() -> set[str]:
    """Return set of usernames already DMd in any previous session."""
    if not DM_FILE.exists():
        return set()
    try:
        data = json.loads(DM_FILE.read_text(encoding="utf-8"))
        return set(u.lower().strip() for u in data.get("usernames", []))
    except Exception:
        return set()


def save_dm_sent(username: str, message_snippet: str = "") -> None:
    """Record a DM as sent — called after send_dm succeeds."""
    username = username.lower().strip()
    data: dict = {"usernames": [], "sessions": []}
    if DM_FILE.exists():
        try:
            data = json.loads(DM_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if username not in data["usernames"]:
        data["usernames"].append(username)

    data.setdefault("sessions", []).append({
        "date": datetime.now().isoformat(),
        "username": username,
        "snippet": message_snippet[:120],
    })

    DM_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def has_dm_sent(username: str) -> bool:
    return username.lower().strip() in load_dm_sent()
