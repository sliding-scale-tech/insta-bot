"""Debug comment UI after full login."""

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from instagram_bot.auth.browser import ensure_instagram_ready, get_bot_context
from instagram_bot.bots.browser import wait_human
from instagram_bot.config.settings import ENV_PATH, HASHTAG_TO_SEARCH

load_dotenv(ENV_PATH, override=True)
DEBUG = Path(__file__).parent / "debug_output"


def dump(page, label):
    DEBUG.mkdir(exist_ok=True)
    page.screenshot(path=str(DEBUG / f"cm_{label}.png"), full_page=True)
    (DEBUG / f"cm_{label}.html").write_text(page.content(), encoding="utf-8")
    print(f"[debug] {label} url={page.url}")


def main():
    tag = HASHTAG_TO_SEARCH.lstrip("#")
    with sync_playwright() as pw:
        browser, _, page = get_bot_context(pw)
        ensure_instagram_ready(page)

        page.goto(f"https://www.instagram.com/explore/tags/{tag}/", wait_until="domcontentloaded")
        wait_human(3, 5)
        ensure_instagram_ready(page)
        dump(page, "01_hashtag")

        link = page.locator('a[href*="/p/"]').first
        href = link.get_attribute("href")
        post_url = f"https://www.instagram.com{href}" if href and not href.startswith("http") else href
        page.goto(post_url, wait_until="domcontentloaded")
        wait_human(4, 6)
        dump(page, "02_post")

        selectors = [
            'svg[aria-label="Comment"]',
            'span:has-text("Add a comment")',
            'textarea',
            'div[contenteditable="true"]',
        ]
        for sel in selectors:
            loc = page.locator(sel)
            print(f"{sel}: count={loc.count()}")
            for i in range(min(loc.count(), 2)):
                el = loc.nth(i)
                try:
                    print(f"  [{i}] visible={el.is_visible()} box={el.bounding_box()}")
                except Exception as e:
                    print(f"  [{i}] err={e}")

        # click comment icon
        try:
            icon = page.locator('svg[aria-label="Comment"]').first
            parent = icon.locator("xpath=ancestor::*[@role='button' or @role='link'][1]")
            if parent.count():
                print("Clicking Comment icon parent...")
                parent.first.click(force=True)
            else:
                icon.click(force=True)
            time.sleep(2)
            dump(page, "03_after_comment_icon")
        except Exception as e:
            print("comment icon click failed:", e)

        try:
            page.locator('span:has-text("Add a comment")').first.click(force=True)
            time.sleep(2)
            dump(page, "04_after_add_comment")
        except Exception as e:
            print("add comment click failed:", e)

        browser.close()


if __name__ == "__main__":
    main()
