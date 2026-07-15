"""Cross-session memory: stores commented post URLs in data/commented_posts.json."""

import json
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from instagram_bot.config.settings import DATA_DIR

PERSISTENT_FILE = DATA_DIR / "commented_posts.json"


def normalize_url(url: str) -> str:
    """Strip query params, fragments, and trailing slashes for dedup."""
    try:
        parsed = urlparse(url.strip())
        clean = urlunparse((
            parsed.scheme or "https",
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "", "", "",
        ))
        return clean
    except Exception:
        return url.strip().rstrip("/").lower()


def load_commented_urls() -> set[str]:
    """Load all previously commented post URLs (normalized)."""
    if not PERSISTENT_FILE.exists():
        return set()
    try:
        data = json.loads(PERSISTENT_FILE.read_text(encoding="utf-8"))
        return set(data.get("urls", []))
    except Exception:
        return set()


def save_commented_url(url: str, comment_snippet: str = "") -> None:
    """Append a newly commented URL to the persistent store."""
    normalized = normalize_url(url)
    data: dict = {"urls": [], "sessions": []}
    if PERSISTENT_FILE.exists():
        try:
            data = json.loads(PERSISTENT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if normalized not in data["urls"]:
        data["urls"].append(normalized)

    data.setdefault("sessions", []).append({
        "date": datetime.now().isoformat(),
        "url": normalized,
        "snippet": comment_snippet[:120],
    })

    PERSISTENT_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def has_commented_persistent(url: str) -> bool:
    """Check if URL was commented in a previous session."""
    return normalize_url(url) in load_commented_urls()
