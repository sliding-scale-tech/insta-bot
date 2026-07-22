"""Debug Instagram flow — saves screenshots + HTML at each step."""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from instagram_bot.auth.browser import ensure_instagram_ready, get_bot_context
from instagram_bot.auth.sessions import sync_cookie_files
from instagram_bot.bots.browser import open_first_post, wait_human
from instagram_bot.config.settings import ENV_PATH, HASHTAG_TO_SEARCH

load_dotenv(ENV_PATH, override=True)

DEBUG_DIR = Path(__file__).parent / "debug_output"


def save_debug(page, label: str) -> None:
    DEBUG_DIR.mkdir(exist_ok=True)
    safe = label.replace(" ", "_").replace("/", "-")
    png = DEBUG_DIR / f"{safe}.png"
    html = DEBUG_DIR / f"{safe}.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    print(f"  [debug] saved {png.name} + {html.name}  url={page.url}")


def dump_comment_elements(page) -> None:
    print("\n--- Comment-related elements ---")
    for selector in [
        'textarea',
        'div[contenteditable="true"]',
        'span:has-text("Add a comment")',
        'svg[aria-label="Comment"]',
        'svg[aria-label*="Comment"]',
        'button:has-text("Post")',
        'div[role="button"]:has-text("Post")',
    ]:
        loc = page.locator(selector)
        count = loc.count()
        if count:
            print(f"  {selector!r}: {count} found")
            for i in range(min(count, 3)):
                el = loc.nth(i)
                try:
                    vis = el.is_visible()
                    txt = (el.inner_text(timeout=1000) or "")[:60]
                    print(f"    [{i}] visible={vis} text={txt!r}")
                except Exception as e:
                    print(f"    [{i}] error: {e}")


def main() -> None:
    sync_cookie_files()
    DEBUG_DIR.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser, context, page = get_bot_context(pw)
        save_debug(page, "01_after_load")

        print("\nGoing to explore...")
        page.goto(
            f"https://www.instagram.com/explore/tags/{HASHTAG_TO_SEARCH.lstrip('#')}/",
            wait_until="domcontentloaded",
        )
        wait_human(3, 5)
        ensure_instagram_ready(page)
        save_debug(page, "02_explore_hashtag")

        post_url = open_first_post(page)
        save_debug(page, "03_post_opened")
        dump_comment_elements(page)

        # Try clicking Comment icon
        for sel in [
            'svg[aria-label="Comment"]',
            'svg[aria-label="Comment"]',
            'span:has-text("Add a comment")',
            'div:has-text("Add a comment")',
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    print(f"\nClicking {sel!r}...")
                    el.click(timeout=3000)
                    time.sleep(2)
                    save_debug(page, f"04_after_click_{sel[:20]}")
                    dump_comment_elements(page)
            except Exception as e:
                print(f"  skip {sel!r}: {e}")

        save_debug(page, "05_final")
        print(f"\nPost URL: {post_url}")
        browser.close()


if __name__ == "__main__":
    main()
