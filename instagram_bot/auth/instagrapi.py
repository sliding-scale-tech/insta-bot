"""instagrapi authentication and session management."""

import logging
import os

from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    ClientThrottledError,
    DirectMessageRequestsDisabled,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    ReloginAttemptExceeded,
    TwoFactorRequired,
)
from instagrapi.mixins.challenge import ChallengeChoice
from instagrapi.utils import json_value

from instagram_bot.auth.sessions import has_saved_session, sync_cookie_files
from instagram_bot.config.settings import (
    HASHTAG_TO_SEARCH,
    SESSION_FILE,
    get_api_credentials,
)

logger = logging.getLogger(__name__)


def get_credentials() -> tuple[str, str]:
    return get_api_credentials()


def challenge_code_handler(username: str, choice: ChallengeChoice) -> str:
    channel = "SMS" if choice == ChallengeChoice.SMS else "email"
    print(f"\nInstagram sent a verification code to your {channel}.")
    return input(f"Enter the 6-digit code for @{username}: ").strip()


def handle_exception(client: Client, error: Exception) -> bool:
    if isinstance(error, BadPassword):
        client.logger.exception(error)
        if client.relogin_attempt > 0:
            raise ReloginAttemptExceeded(error) from error
        raise error
    if isinstance(error, LoginRequired):
        client.logger.exception(error)
        username, password = get_credentials()
        if username and password:
            client.relogin()
            return True
        raise error
    if isinstance(error, ChallengeRequired):
        api_path = json_value(client.last_json, "challenge", "api_path")
        if api_path != "/challenge/":
            client.challenge_resolve(client.last_json)
        return True
    if isinstance(error, FeedbackRequired):
        logger.warning("FeedbackRequired: %s", client.last_json.get("feedback_message", ""))
    if isinstance(error, (ClientThrottledError, PleaseWaitFewMinutes)):
        logger.warning("Rate limited: %s", error)
    if isinstance(error, DirectMessageRequestsDisabled):
        logger.warning("DM disabled: %s", error)
    raise error


def create_client() -> Client:
    client = Client()
    client.delay_range = [1, 3]
    client.challenge_code_handler = challenge_code_handler
    client.handle_exception = handle_exception
    proxy = os.getenv("PROXY", "").strip()
    if proxy:
        client.set_proxy(proxy)
    return client


def load_browser_cookies() -> dict | None:
    cookies = sync_cookie_files()
    return cookies if cookies.get("sessionid") else None


def try_json_session_import(client: Client) -> Client | None:
    cookies = load_browser_cookies()
    if not cookies:
        return None

    username, password = get_credentials()

    try:
        if os.path.exists(SESSION_FILE):
            client.set_settings(client.load_settings(SESSION_FILE))
        else:
            settings = client.get_settings()
            settings["cookies"] = cookies
            settings["authorization_data"] = {
                "ds_user_id": cookies.get("ds_user_id", ""),
                "sessionid": cookies["sessionid"],
                "should_use_header_over_cookies": True,
            }
            client.set_settings(settings)
            client.init()

        if username:
            client.username = username
        if password:
            client.password = password

        client.login_by_sessionid(cookies["sessionid"])
        cl_username = client.username or username
        print(f"Loaded session from JSON files as @{cl_username}")

        medias = client.hashtag_medias_recent(HASHTAG_TO_SEARCH, amount=1)
        if not medias:
            raise LoginRequired("Could not fetch hashtag with saved session")

        client.dump_settings(SESSION_FILE)
        return client
    except Exception as error:
        logger.info("JSON session import failed: %s", error)
        return None


def try_browser_session_import(client: Client) -> Client | None:
    return try_json_session_import(client)


def try_password_login(username: str, password: str) -> Client | None:
    client = create_client()

    if os.path.exists(SESSION_FILE):
        try:
            client.set_settings(client.load_settings(SESSION_FILE))
            client.login(username, password)
            client.get_timeline_feed()
            client.dump_settings(SESSION_FILE)
            return client
        except (BadPassword, LoginRequired, TwoFactorRequired, ChallengeRequired):
            pass

    try:
        client = create_client()
        client.login(username, password)
        client.get_timeline_feed()
        client.dump_settings(SESSION_FILE)
        return client
    except TwoFactorRequired:
        code = input("Enter 2FA code: ").strip()
        client.login(username, password, verification_code=code)
        client.get_timeline_feed()
        client.dump_settings(SESSION_FILE)
        return client
    except ChallengeRequired:
        client.challenge_resolve(client.last_json)
        client.get_timeline_feed()
        client.dump_settings(SESSION_FILE)
        return client
    except BadPassword:
        return None


def get_authenticated_client() -> Client:
    username, password = get_credentials()

    client = try_json_session_import(create_client())
    if client:
        return client

    if username and password:
        client = try_password_login(username, password)
        if client:
            return client

    if has_saved_session():
        raise SystemExit(
            "\nSaved JSON session found but instagrapi API rejected it.\n"
            "Run with browser mode:\n"
            "  USE_BROWSER=true python main.py\n"
        )

    raise SystemExit(
        "\nNo valid session found in JSON files.\n"
        "Run: python authenticate.py\n"
    )


def login_user() -> Client:
    client = get_authenticated_client()
    print(f"Session saved to {SESSION_FILE}")
    return client


def relogin_if_needed(client: Client) -> Client:
    username, password = get_credentials()
    try:
        client.get_timeline_feed()
        return client
    except LoginRequired:
        try:
            client.relogin()
            client.dump_settings(SESSION_FILE)
            return client
        except Exception:
            if username and password:
                return try_password_login(username, password) or get_authenticated_client()
            return get_authenticated_client()
