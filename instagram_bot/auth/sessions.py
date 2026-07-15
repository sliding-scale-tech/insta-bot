"""Load Instagram sessions from saved JSON files."""

import json
import os
from urllib.parse import unquote

from instagram_bot.config.settings import BROWSER_COOKIES_FILE, BROWSER_STATE_FILE, SESSION_FILE


def cookies_from_state_file(path: str = BROWSER_STATE_FILE) -> dict:
    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as handle:
        state = json.load(handle)

    cookies = {}
    for cookie in state.get("cookies", []):
        domain = cookie.get("domain", "")
        if "instagram.com" not in domain:
            continue
        cookies[cookie["name"]] = unquote(str(cookie["value"]))

    return cookies


def cookies_from_cookies_file(path: str = BROWSER_COOKIES_FILE) -> dict:
    if not os.path.exists(path):
        return {}

    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        return {}

    return {key: unquote(str(value)) for key, value in data.items()}


def load_saved_cookies() -> dict:
    cookies = cookies_from_state_file()
    if cookies.get("sessionid"):
        return cookies

    cookies = cookies_from_cookies_file()
    if cookies.get("sessionid"):
        return cookies

    return {}


def has_saved_session() -> bool:
    cookies = load_saved_cookies()
    sessionid = cookies.get("sessionid", "")
    return bool(sessionid and len(sessionid) > 20)


def sync_cookie_files() -> dict:
    cookies = load_saved_cookies()
    if cookies:
        with open(BROWSER_COOKIES_FILE, "w", encoding="utf-8") as handle:
            json.dump(cookies, handle, indent=2)
    return cookies
