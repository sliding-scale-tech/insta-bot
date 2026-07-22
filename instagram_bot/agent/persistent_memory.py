"""Cross-session memory — Convex DB primary, local JSON fallback."""

import json
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from instagram_bot.config.settings import DATA_DIR

PERSISTENT_FILE = DATA_DIR / "commented_posts.json"

_convex_available: bool | None = None  # None = not yet checked


def _check_convex() -> bool:
    global _convex_available
    if _convex_available is not None:
        return _convex_available
    try:
        from instagram_bot.db.convex_client import get_all_commented_urls
        get_all_commented_urls()
        _convex_available = True
    except Exception:
        _convex_available = False
    return _convex_available


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


def _shortcode_from_url(url: str) -> str:
    for marker in ("/p/", "/reel/", "/reels/"):
        if marker in url:
            return url.split(marker, 1)[1].strip("/").split("/")[0]
    return url.split("/")[-1] or url


# ── Load ────────────────────────────────────────────────────────────────────

def load_commented_urls() -> set[str]:
    """Load all previously commented post URLs (normalized). Convex first, JSON fallback."""
    if _check_convex():
        try:
            from instagram_bot.db.convex_client import get_all_commented_urls
            urls = get_all_commented_urls()
            print(f"  [db] Loaded {len(urls)} commented URLs from Convex")
            return set(normalize_url(u) for u in urls)
        except Exception as e:
            print(f"  [db] Convex load failed, falling back to JSON: {e}")

    # JSON fallback
    if not PERSISTENT_FILE.exists():
        return set()
    try:
        data = json.loads(PERSISTENT_FILE.read_text(encoding="utf-8"))
        return set(normalize_url(u) for u in data.get("urls", []))
    except Exception:
        return set()


def load_dm_usernames() -> set[str]:
    """Load all usernames the bot has DM'd. Convex first."""
    if _check_convex():
        try:
            from instagram_bot.db.convex_client import get_all_dm_usernames
            names = get_all_dm_usernames()
            print(f"  [db] Loaded {len(names)} DM'd usernames from Convex")
            return set(n.lower() for n in names)
        except Exception as e:
            print(f"  [db] Convex dm_usernames failed: {e}")
    return set()


def load_followed_usernames() -> set[str]:
    """Load all usernames the bot has followed. Convex first."""
    if _check_convex():
        try:
            from instagram_bot.db.convex_client import get_all_followed_usernames
            names = get_all_followed_usernames()
            print(f"  [db] Loaded {len(names)} followed usernames from Convex")
            return set(n.lower() for n in names)
        except Exception as e:
            print(f"  [db] Convex followed_usernames failed: {e}")
    return set()


# ── Save ────────────────────────────────────────────────────────────────────

def save_commented_url(url: str, comment_snippet: str = "", username: str = "") -> None:
    """Save a newly commented URL. Writes to Convex and JSON backup."""
    normalized = normalize_url(url)
    shortcode = _shortcode_from_url(normalized)

    # Convex
    if _check_convex():
        try:
            from instagram_bot.db.convex_client import add_commented_post
            add_commented_post(normalized, shortcode, comment_snippet[:100], username)
        except Exception as e:
            print(f"  [db] Convex save failed: {e}")

    # JSON backup
    _save_commented_url_json(normalized, comment_snippet)


def _save_commented_url_json(normalized: str, comment_snippet: str) -> None:
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
    return normalize_url(url) in load_commented_urls()
