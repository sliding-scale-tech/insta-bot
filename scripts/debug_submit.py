"""Test full comment submit after login."""

import random
import time

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from browser_auth import ensure_instagram_ready, get_bot_context
from browser_bot import COMMENT_TEXT, HASHTAG_TO_SEARCH, wait_human

load_dotenv(override=True)


def main():
    tag = HASHTAG_TO_SEARCH.lstrip("#")
    with sync_playwright() as pw:
        browser, _, page = get_bot_context(pw)
        ensure_instagram_ready(page)

        page.goto(f"https://www.instagram.com/p/DIB0Q0jAM_D/", wait_until="domcontentloaded")
        wait_human(3, 5)

        # Click comment icon
        icon = page.locator('svg[aria-label="Comment"]').first
        parent = icon.locator("xpath=ancestor::*[@role='button'][1]")
        if parent.count():
            parent.first.click(force=True)
        else:
            icon.click(force=True)
        wait_human(1, 2)

        textarea = page.locator("textarea").first
        textarea.scroll_into_view_if_needed()
        textarea.click(force=True)
        wait_human(0.5, 1)
        textarea.fill("")
        for ch in COMMENT_TEXT:
            page.keyboard.insert_text(ch)
            time.sleep(random.uniform(0.08, 0.18))
        wait_human(1, 2)

        val = textarea.input_value()
        print("Textarea value:", repr(val[:80]))

        post = page.locator('div[role="button"]:has-text("Post")').first
        print("Post visible:", post.is_visible())
        post.click(force=True)
        wait_human(3, 5)

        page.screenshot(path="debug_output/cm_05_posted.png", full_page=True)
        print("Done, url:", page.url)
        browser.close()


if __name__ == "__main__":
    main()
