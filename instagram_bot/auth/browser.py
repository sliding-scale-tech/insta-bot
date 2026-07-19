"""Use the user's installed Chrome browser for Instagram login."""

import json
import os
import random
import socket
import subprocess
import time
from urllib.parse import unquote

from instagram_bot.auth.sessions import (
    has_saved_session,
    sync_cookie_files,
)
from instagram_bot.config.settings import (
    BROWSER_COOKIES_FILE,
    BROWSER_STATE_FILE,
    CHROME_DEBUG_PORT,
    CHROME_DEBUG_URL,
    CHROME_PROFILE_DIR,
    LOGIN_METHOD,
    get_credentials,
)

CHROME_PROFILE_DIR_STR = str(CHROME_PROFILE_DIR)

# Tracks the Chrome process we spawned for manual login (if any), so it can be
# torn down explicitly instead of being left running in the background — a
# lingering logged-in Chrome window plus a later Playwright-launched Chrome
# means two simultaneous sessions for the same account, which risks a ban.
_launched_chrome_process: subprocess.Popen | None = None


def get_chrome_executable() -> str | None:
    env_path = os.getenv("CHROME_PATH", "").strip()
    if env_path and os.path.exists(env_path):
        return env_path

    for path in [
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ]:
        if os.path.exists(path):
            return path
    return None


def is_debug_port_open(port: int = CHROME_DEBUG_PORT) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def get_profile_directory() -> str:
    if os.getenv("USE_MY_CHROME_PROFILE", "").lower() in {"1", "true", "yes"}:
        return os.path.join(os.environ["LOCALAPPDATA"], "Google", "Chrome", "User Data")
    return CHROME_PROFILE_DIR_STR


def launch_user_chrome(url: str = "https://www.instagram.com/accounts/login/") -> None:
    global _launched_chrome_process
    chrome = get_chrome_executable()
    if not chrome:
        raise SystemExit(
            "Google Chrome was not found.\n"
            "Install Chrome or set CHROME_PATH in your .env file."
        )

    profile_dir = get_profile_directory()
    if profile_dir.endswith("User Data"):
        print("\nUsing your main Chrome profile.")
        print("Close ALL Chrome windows first, then press Enter.")
        input()

    os.makedirs(profile_dir, exist_ok=True)

    _launched_chrome_process = subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={CHROME_DEBUG_PORT}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    for _ in range(30):
        if is_debug_port_open():
            return
        time.sleep(0.5)

    raise SystemExit(
        "Could not connect to Chrome.\n"
        "Close all Chrome windows and run authenticate.py again."
    )


def close_launched_chrome() -> None:
    """Terminate the Chrome instance launched by `launch_user_chrome`, if any.

    Closing a `connect_over_cdp` Browser handle only ends the CDP session — it
    does NOT stop the external Chrome process that was spawned for it. Left
    running, that Chrome keeps an authenticated Instagram tab open in the
    background, and a subsequent `get_bot_context` launch opens a second,
    independent Chrome logged into the same account at the same time.
    """
    global _launched_chrome_process
    proc = _launched_chrome_process
    _launched_chrome_process = None
    if proc is None or proc.poll() is not None:
        return
    try:
        proc.terminate()
    except Exception:
        pass
    for _ in range(20):
        if not is_debug_port_open():
            return
        time.sleep(0.5)
    try:
        proc.kill()
    except Exception:
        pass


def connect_user_chrome(playwright):
    if not is_debug_port_open():
        print("Opening your Chrome browser...")
        launch_user_chrome()

    try:
        return playwright.chromium.connect_over_cdp(CHROME_DEBUG_URL)
    except Exception as error:
        raise SystemExit(
            "Could not connect to Chrome.\n"
            "Close all Chrome windows and run authenticate.py again.\n"
            f"Details: {error}"
        ) from error


def get_browser_context(playwright):
    browser = connect_user_chrome(playwright)
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    return browser, context, page


def save_cookies_from_context(context) -> dict:
    cookies = context.cookies()
    cookie_map = {
        cookie["name"]: unquote(cookie["value"])
        for cookie in cookies
        if "instagram.com" in cookie.get("domain", "")
    }

    with open(BROWSER_COOKIES_FILE, "w", encoding="utf-8") as handle:
        json.dump(cookie_map, handle, indent=2)

    return cookie_map


_last_written_sessionid = ""


def has_session_cookie(context=None) -> bool:
    global _last_written_sessionid
    if has_saved_session():
        return True
    if context is None:
        return False

    # wait_for_login polls this once a second during manual login — read the live
    # cookies without touching disk, and only persist when the sessionid actually
    # changes, instead of rewriting browser_cookies.json on every poll tick.
    live_cookies = {
        cookie["name"]: unquote(str(cookie["value"]))
        for cookie in context.cookies()
        if "instagram.com" in cookie.get("domain", "")
    }
    sessionid = live_cookies.get("sessionid", "")
    valid = bool(sessionid and len(sessionid) > 20)
    if valid and sessionid != _last_written_sessionid:
        save_cookies_from_context(context)
        _last_written_sessionid = sessionid
    return valid


def ensure_browser_session() -> str:
    sync_cookie_files()
    if has_saved_session() and os.path.exists(BROWSER_STATE_FILE):
        return BROWSER_STATE_FILE

    print("No valid login found in JSON files. Opening Chrome now...")
    browser_login(method=LOGIN_METHOD)
    return BROWSER_STATE_FILE


def get_bot_context(playwright):
    """Launch Chrome with saved session from browser_state.json."""
    state_file = ensure_browser_session()
    browser = playwright.chromium.launch(
        headless=False,
        channel="chrome",
        args=["--start-maximized"],
    )
    context = browser.new_context(
        storage_state=state_file,
        no_viewport=True,
    )
    page = context.new_page()
    page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    ensure_instagram_ready(page)
    return browser, context, page


def click_continue_if_present(page) -> bool:
    """Click Continue on Instagram's saved-profile screen."""
    username, _, _ = get_credentials()

    continue_selectors = [
        'button:has-text("Continue")',
        'div[role="button"]:has-text("Continue")',
    ]

    for selector in continue_selectors:
        try:
            button = page.locator(selector).first
            button.wait_for(state="visible", timeout=5000)
            print(f"Clicking Continue for @{username or 'saved profile'}...")
            time.sleep(random.uniform(1, 2))
            button.click(force=True, timeout=5000)
            time.sleep(random.uniform(2, 4))
            return True
        except Exception:
            continue

    return False


def handle_password_prompt(page) -> bool:
    """Fill the Meta Account password popup after Continue."""
    username, _, password = get_credentials()
    if not password:
        print(
            "No password found in .env.\n"
            "Add this line to your .env file:\n"
            "  password=your_instagram_password"
        )
        return False

    print(f"Using password from .env for @{username or 'your account'}...")
    time.sleep(random.uniform(1.5, 2.5))

    modal = None
    for selector in [
        'div[role="dialog"]:has-text("Log into your Meta Account")',
        'div[role="dialog"]:has-text("Meta Account")',
        'div[role="presentation"]:has-text("Meta Account")',
    ]:
        try:
            candidate = page.locator(selector).first
            candidate.wait_for(state="visible", timeout=8000)
            modal = candidate
            print("Meta Account login popup detected.")
            break
        except Exception:
            continue

    scope = modal if modal is not None else page

    pwd = None
    for selector in [
        'input[type="password"]',
        'input[placeholder="Password"]',
        'input[aria-label*="Password" i]',
        'input[name="pass"]',
    ]:
        try:
            field = scope.locator(selector).first
            field.wait_for(state="visible", timeout=8000)
            pwd = field
            break
        except Exception:
            continue

    if pwd is None:
        return False

    print("Entering password in Meta login popup...")
    time.sleep(random.uniform(0.8, 1.5))
    pwd.click(force=True)
    pwd.fill(password)
    time.sleep(random.uniform(0.5, 1))

    for selector in [
        'button:has-text("Log in")',
        'div[role="button"]:has-text("Log in")',
        'button[type="submit"]',
    ]:
        try:
            btn = scope.locator(selector).first
            if btn.is_visible(timeout=3000):
                btn.click(force=True, timeout=5000)
                time.sleep(random.uniform(3, 5))
                print("Password submitted.")
                return True
        except Exception:
            continue

    pwd.press("Enter")
    time.sleep(random.uniform(3, 5))
    print("Password submitted with Enter.")
    return True


def is_logged_in(page) -> bool:
    if "accounts/login" in page.url:
        return False
    for selector in [
        'svg[aria-label="Home"]',
        'a[href="/"] svg',
        'nav',
        'input[aria-label="Search input"]',
    ]:
        try:
            if page.locator(selector).first.is_visible(timeout=2000):
                return True
        except Exception:
            continue
    return False


def ensure_instagram_ready(page) -> None:
    """Handle cookies, Continue, password popup, and wait for home."""
    time.sleep(2)
    dismiss_popups(page)

    if click_continue_if_present(page):
        dismiss_popups(page)
        time.sleep(2)
        handle_password_prompt(page)

    if not is_logged_in(page):
        handle_password_prompt(page)

    dismiss_popups(page)

    for _ in range(3):
        if is_logged_in(page):
            break
        time.sleep(2)

    if is_logged_in(page):
        try:
            page.context.storage_state(path=BROWSER_STATE_FILE)
            save_cookies_from_context(page.context)
        except Exception:
            pass
    else:
        # has_saved_session()/has_session_cookie() only check that a sessionid
        # cookie is present and long enough — they can't tell an expired session
        # from a live one. This is the actual liveness check: if Instagram still
        # isn't showing us logged in after every recovery attempt above, the
        # session is dead. Fail loudly instead of silently browsing logged out.
        raise SystemExit(
            "Instagram session appears to be expired or invalid.\n"
            "Run: python authenticate.py"
        )


def dismiss_notifications_popup(page) -> bool:
    """Dismiss 'Turn on Notifications' by clicking Not Now."""
    for selector in [
        'button:has-text("Not Now")',
        'div[role="button"]:has-text("Not Now")',
        'span:has-text("Not Now")',
    ]:
        try:
            btn = page.locator(selector).first
            btn.wait_for(state="visible", timeout=3000)
            print('Clicking "Not Now" on notifications popup...')
            time.sleep(random.uniform(0.5, 1))
            btn.click(force=True, timeout=3000)
            time.sleep(random.uniform(1, 2))
            return True
        except Exception:
            continue
    return False


def dismiss_popups(page) -> None:
    dismiss_cookie_banner(page)
    dismiss_notifications_popup(page)


def dismiss_cookie_banner(page) -> None:
    for selector in [
        "button:has-text('Allow all cookies')",
        "button:has-text('Accept all')",
        "button:has-text('Allow essential and optional cookies')",
    ]:
        try:
            page.locator(selector).first.click(timeout=2000)
            time.sleep(1)
            return
        except Exception:
            continue


def open_login_page(page, method: str = "manual") -> None:
    page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")
    time.sleep(2)
    dismiss_cookie_banner(page)

    email = os.getenv("email", "").strip()
    username, email_from_env, password = get_credentials()
    if not email:
        email = email_from_env

    if method == "facebook":
        print("\nIn Chrome: click 'Log in with Facebook' and finish login there.")
        for selector in [
            "button:has-text('Log in with Facebook')",
            "div[role='button']:has-text('Log in with Facebook')",
            "a:has-text('Log in with Facebook')",
        ]:
            try:
                page.locator(selector).first.click(timeout=3000)
                return
            except Exception:
                continue
        print("Click 'Log in with Facebook' on the page manually.")

    elif method == "email":
        login_value = email or username
        if not login_value:
            print("\nAdd your email to .env, then run again.")
            return

        print(f"\nFilling login field with: {login_value}")
        print("Enter your password in Chrome and click Log in.")
        try:
            page.locator('input[name="username"]').fill(login_value, timeout=5000)
            if password:
                page.locator('input[name="password"]').fill(password, timeout=5000)
                print("Password filled from .env. Click Log in in Chrome.")
        except Exception as error:
            print(f"Could not auto-fill login form: {error}")

    elif method == "username":
        if not username:
            print("\nAdd your username to .env, then run again.")
            return

        print(f"\nFilling username: {username}")
        try:
            page.locator('input[name="username"]').fill(username, timeout=5000)
            if password:
                page.locator('input[name="password"]').fill(password, timeout=5000)
                print("Password filled from .env. Click Log in in Chrome.")
        except Exception as error:
            print(f"Could not auto-fill login form: {error}")


def wait_for_login(context, page, timeout_seconds: int = 600) -> None:
    print("\nWaiting for you to finish login in Chrome...")
    print("This auto-detects when Instagram login is complete.\n")

    for second in range(timeout_seconds):
        if has_session_cookie(context):
            print("Login detected.")
            return

        if second and second % 15 == 0:
            print(f"Still waiting... ({second}s) Finish login in Chrome.")

        time.sleep(1)

    raise SystemExit(
        "Login timed out.\n"
        "Finish Facebook or email login in Chrome, then run authenticate.py again."
    )


def browser_login(method: str = "manual") -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise SystemExit("Install Playwright first:\n  pip install playwright") from error

    method = method.strip().lower()
    labels = {
        "facebook": "Facebook login",
        "email": "Email login",
        "username": "Username + password",
        "manual": "Manual login",
    }
    print(f"\nLogin method: {labels.get(method, method)}")
    print("Chrome will open on the Instagram login page.\n")

    try:
        with sync_playwright() as playwright:
            browser, context, page = get_browser_context(playwright)

            if has_session_cookie(context):
                print("You are already logged in from a previous session.")
                ensure_instagram_ready(page)
            else:
                open_login_page(page, method=method)
                wait_for_login(context, page)

            if not has_session_cookie(context):
                browser.close()
                raise SystemExit(
                    "Login not complete. No Instagram session cookie found.\n"
                    "Use Facebook or email login in Chrome, then run authenticate.py again."
                )

            context.storage_state(path=BROWSER_STATE_FILE)
            cookies = save_cookies_from_context(context)
            browser.close()
    finally:
        # Always tear down the Chrome we spawned for this login, even on error —
        # otherwise it lingers logged in while a later run launches a second,
        # independent Chrome for the same account.
        close_launched_chrome()

    print(f"\nLogin saved for @{cookies.get('ds_user_id', 'your account')}")
    print(f"Session file: {BROWSER_STATE_FILE}")
    print("Start the bot with: python main.py")
