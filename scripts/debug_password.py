"""Debug password popup after Continue click."""

import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from browser_auth import get_bot_context
from env_utils import get_env_credentials

load_dotenv(override=True)
DEBUG = Path(__file__).parent / "debug_output"


def main():
    DEBUG.mkdir(exist_ok=True)
    _, _, password = get_env_credentials()

    with sync_playwright() as pw:
        browser, _, page = get_bot_context(pw)
        page.screenshot(path=str(DEBUG / "pw_00_start.png"), full_page=True)

        # Click Continue
        for sel in ['button:has-text("Continue")', 'div[role="button"]:has-text("Continue")']:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=3000):
                    print(f"Clicking {sel}")
                    btn.click()
                    time.sleep(3)
                    break
            except Exception as e:
                print(f"no {sel}: {e}")

        page.screenshot(path=str(DEBUG / "pw_01_after_continue.png"), full_page=True)
        (DEBUG / "pw_01_after_continue.html").write_text(page.content(), encoding="utf-8")
        print("URL:", page.url)

        # List inputs
        print("\nInputs on page:")
        for i in range(page.locator("input").count()):
            inp = page.locator("input").nth(i)
            try:
                print(
                    i,
                    "type=", inp.get_attribute("type"),
                    "name=", inp.get_attribute("name"),
                    "aria=", inp.get_attribute("aria-label"),
                    "visible=", inp.is_visible(),
                )
            except Exception as e:
                print(i, "err", e)

        # Try fill password
        pwd_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[aria-label*="Password"]',
            'input[placeholder*="Password"]',
        ]
        for sel in pwd_selectors:
            loc = page.locator(sel).first
            try:
                if loc.is_visible(timeout=2000):
                    print(f"\nFilling {sel}")
                    loc.fill(password)
                    time.sleep(1)
                    page.screenshot(path=str(DEBUG / "pw_02_filled.png"), full_page=True)

                    for login_sel in [
                        'button:has-text("Log in")',
                        'div[role="button"]:has-text("Log in")',
                        'button:has-text("Confirm")',
                        'button:has-text("Continue")',
                    ]:
                        try:
                            b = page.locator(login_sel).first
                            if b.is_visible(timeout=2000):
                                print(f"Clicking {login_sel}")
                                b.click()
                                time.sleep(5)
                                break
                        except Exception:
                            pass
                    break
            except Exception as e:
                print(f"skip {sel}: {e}")

        page.screenshot(path=str(DEBUG / "pw_03_final.png"), full_page=True)
        (DEBUG / "pw_03_final.html").write_text(page.content(), encoding="utf-8")
        print("Final URL:", page.url)

        # Check if logged in
        for sel in ['svg[aria-label="Home"]', 'a[href="/"]', 'nav']:
            try:
                if page.locator(sel).first.is_visible(timeout=3000):
                    print("Logged in indicator:", sel)
            except Exception:
                pass

        browser.close()


if __name__ == "__main__":
    main()
