"""Project paths, environment variables, and bot settings."""

import os
import shutil
from pathlib import Path

from dotenv import dotenv_values, load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DEBUG_DIR = PROJECT_ROOT / "debug_output"
CHROME_PROFILE_DIR = PROJECT_ROOT / "chrome_profile"
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH, override=True)

DATA_DIR.mkdir(exist_ok=True)
DEBUG_DIR.mkdir(exist_ok=True)
CHROME_PROFILE_DIR.mkdir(exist_ok=True)


def _env_int(key: str, default: int) -> int:
    """int(os.getenv(key, default)) crashes if the var is present but blank —
    os.getenv only falls back to `default` when the key is absent entirely."""
    raw = (os.getenv(key) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _resolve_path(env_key: str, default_name: str) -> str:
    value = os.getenv(env_key, "").strip()
    if value:
        path = Path(value)
        resolved = path if path.is_absolute() else PROJECT_ROOT / path
        return str(resolved)
    return str(DATA_DIR / default_name)


def _migrate_legacy_data_files() -> None:
    for name in ("browser_state.json", "browser_cookies.json", "session.json"):
        legacy = PROJECT_ROOT / name
        target = DATA_DIR / name
        if legacy.exists() and not target.exists():
            shutil.move(str(legacy), str(target))


_migrate_legacy_data_files()

SESSION_FILE = _resolve_path("SESSION_FILE", "session.json")
BROWSER_STATE_FILE = _resolve_path("BROWSER_STATE_FILE", "browser_state.json")
BROWSER_COOKIES_FILE = _resolve_path("BROWSER_COOKIES_FILE", "browser_cookies.json")

CHROME_DEBUG_PORT = _env_int("CHROME_DEBUG_PORT", 9222)
CHROME_DEBUG_URL = os.getenv("CHROME_DEBUG_URL", f"http://127.0.0.1:{CHROME_DEBUG_PORT}")

INSTAGRAM_USERNAME = (
    dotenv_values(ENV_PATH).get("username")
    or dotenv_values(ENV_PATH).get("IG_USERNAME")
    or os.getenv("IG_USERNAME", "")
    or os.getenv("username", "")
).strip().lower()

HASHTAG_TO_SEARCH = os.getenv("HASHTAG_TO_SEARCH", "realestate")
SEARCH_HASHTAGS = [
    tag.strip().lstrip("#")
    for tag in os.getenv("SEARCH_HASHTAGS", "realestate,realestateagent,homesforsale").split(",")
    if tag.strip()
]
AGENT_MISSION = os.getenv(
    "AGENT_MISSION",
    (
        "Find real estate professionals and investors on Instagram. "
        "Engage authentically: leave 2 genuine comments on posts, send 2 DMs to active real estate people "
        "who might benefit from automation/marketing tools, like every post you engage with, "
        "scroll naturally between posts, and reply to at least 1 comment that deserves a thoughtful response."
    ),
)
COMMENT_TEXT = os.getenv("COMMENT_TEXT", "Incredible work! Thanks for sharing this.")
DM_MESSAGE = os.getenv(
    "DM_MESSAGE",
    "Hey there! I saw your post under the hashtag and wanted to connect.",
)
MAX_COMMENTS = _env_int("MAX_COMMENTS", 1)
MAX_DMS = _env_int("MAX_DMS", 0)
LOGIN_METHOD = os.getenv("LOGIN_METHOD", "facebook")

# Gemini agent
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SESSION_MINUTES = _env_int("SESSION_MINUTES", 20)
MAX_COMMENTS_PER_SESSION = _env_int("MAX_COMMENTS_PER_SESSION", 2)
MAX_REPLIES_PER_SESSION = _env_int("MAX_REPLIES_PER_SESSION", 3)
MAX_LIKES_PER_SESSION = _env_int("MAX_LIKES_PER_SESSION", 12)
MAX_FOLLOWS_PER_SESSION = _env_int("MAX_FOLLOWS_PER_SESSION", 5)
MAX_DMS_PER_SESSION = _env_int("MAX_DMS_PER_SESSION", 2)
AGENT_PERSONA = os.getenv(
    "AGENT_PERSONA",
    "You are a knowledgeable real estate enthusiast who gives genuinely helpful, specific advice.",
)

_file_env = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}
GEMINI_API_KEY = (_file_env.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")).strip()

TOOL_CHECKS_DIR = DEBUG_DIR / "tool_checks"
TOOL_CHECKS_DIR.mkdir(exist_ok=True)


def get_credentials() -> tuple[str, str, str]:
    """Read credentials from .env file (avoids Windows env var conflicts)."""
    file_values = dotenv_values(ENV_PATH) if ENV_PATH.exists() else {}

    username = (
        file_values.get("username")
        or file_values.get("IG_USERNAME")
        or os.getenv("IG_USERNAME", "")
        or ""
    ).strip()

    email = (file_values.get("email") or os.getenv("email", "")).strip()
    password = (
        file_values.get("password")
        or file_values.get("IG_PASSWORD")
        or os.getenv("IG_PASSWORD", "")
        or ""
    ).strip()

    return username, email, password


def get_api_credentials() -> tuple[str, str]:
    username, _, password = get_credentials()
    return username, password
