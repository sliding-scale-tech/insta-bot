"""Run the bot through Chrome when instagrapi API login is unavailable."""

import random
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

from instagram_bot.auth.browser import (
    dismiss_notifications_popup,
    ensure_instagram_ready,
    get_bot_context,
    has_session_cookie,
)
from instagram_bot.config.settings import (
    COMMENT_TEXT,
    HASHTAG_TO_SEARCH,
    MAX_COMMENTS,
)
from instagram_bot.utils.debug import save_debug


def wait_human(min_seconds: float = 2, max_seconds: float = 5) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    print(f"  ...waiting {delay:.1f}s")
    time.sleep(delay)


def go_to_hashtag_explore(page, hashtag: str) -> None:
    tag = hashtag.lstrip("#")
    print(f"Opening explore page for #{tag}...")
    page.goto(
        f"https://www.instagram.com/explore/tags/{tag}/",
        wait_until="domcontentloaded",
    )
    ensure_instagram_ready(page)
    wait_human(3, 6)


def open_first_post(page) -> str:
    print("Selecting the first post...")
    wait_human(2, 4)

    post_link = page.locator('article a[href*="/p/"], a[href*="/p/"]').first
    try:
        post_link.wait_for(state="attached", timeout=15000)
        href = post_link.get_attribute("href") or ""
    except PlaywrightTimeoutError:
        save_debug(page, "no_post_found")
        raise SystemExit("No post found for this hashtag.")

    post_url = href if href.startswith("http") else f"https://www.instagram.com{href}"
    print(f"Opening post: {post_url}")
    page.goto(post_url, wait_until="domcontentloaded")
    wait_human(3, 6)
    dismiss_notifications_popup(page)
    return post_url


def dismiss_repost_modal(page) -> bool:
    for selector in [
        'div[role="dialog"] svg[aria-label="Close"]',
        'div[role="dialog"] [aria-label="Close"]',
        'svg[aria-label="Close"]',
    ]:
        try:
            btn = page.locator(selector).first
            if btn.is_visible(timeout=1500):
                print("Closing repost popup...")
                btn.click(force=True)
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


def get_comment_textarea(page):
    for selector in [
        'textarea[placeholder*="Add a comment" i]',
        'textarea[aria-label*="Add a comment" i]',
        'form textarea',
        'section textarea',
    ]:
        loc = page.locator(selector)
        if loc.count() > 0:
            return loc.last
    return page.locator("textarea").last


def find_comment_post_button(page, textarea):
    textarea_box = textarea.bounding_box()
    if not textarea_box:
        return None

    candidates = page.locator('div[role="button"]:has-text("Post"), button:has-text("Post")')
    best = None
    best_score = float("inf")

    for i in range(candidates.count()):
        btn = candidates.nth(i)
        try:
            if not btn.is_visible():
                continue
            btn_box = btn.bounding_box()
            if not btn_box:
                continue

            y_diff = abs(btn_box["y"] - textarea_box["y"])
            x_diff = btn_box["x"] - textarea_box["x"]
            if y_diff > 60 or x_diff < 0:
                continue

            score = y_diff + x_diff
            if score < best_score:
                best_score = score
                best = btn
        except Exception:
            continue

    return best


def focus_comment_box(page) -> None:
    print("Opening comment box...")
    wait_human(1, 2)
    dismiss_repost_modal(page)

    textarea = get_comment_textarea(page)
    textarea.wait_for(state="visible", timeout=10000)
    textarea.scroll_into_view_if_needed()
    wait_human(0.5, 1)
    textarea.click(force=True)
    wait_human(0.8, 1.5)


def type_comment_like_human(page, text: str) -> None:
    print("Typing comment...")
    wait_human(1, 2)

    textarea = get_comment_textarea(page)
    textarea.wait_for(state="visible", timeout=10000)
    textarea.scroll_into_view_if_needed()
    wait_human(0.5, 1)
    textarea.click(force=True)
    wait_human(0.4, 0.8)

    textarea.fill("")
    wait_human(0.3, 0.6)

    for index, char in enumerate(text):
        page.keyboard.insert_text(char)
        time.sleep(random.uniform(0.08, 0.22))
        if index and index % random.randint(4, 9) == 0:
            wait_human(0.2, 0.5)

    wait_human(1, 2)
    typed = textarea.input_value()
    if not typed.strip():
        save_debug(page, "comment_not_typed")
        raise SystemExit("Comment text did not appear in the box.")


def submit_comment(page) -> None:
    print("Posting comment...")
    wait_human(1, 2)

    textarea = get_comment_textarea(page)
    textarea.click(force=True)
    wait_human(0.3, 0.6)

    post_btn = find_comment_post_button(page, textarea)
    if post_btn is not None:
        wait_human(0.5, 1)
        post_btn.click(force=True)
        wait_human(2, 4)
        dismiss_repost_modal(page)
        print("Comment posted.")
        return

    save_debug(page, "post_button_missing")
    textarea.press("Enter")
    wait_human(2, 4)
    dismiss_repost_modal(page)
    print("Comment submitted with Enter.")


def comment_on_current_post(page) -> None:
    try:
        dismiss_notifications_popup(page)
        dismiss_repost_modal(page)
        focus_comment_box(page)
        type_comment_like_human(page, COMMENT_TEXT)
        submit_comment(page)
    except Exception as error:
        save_debug(page, "comment_failed")
        raise SystemExit(f"Comment failed: {error}") from error


def run_browser_bot() -> None:
    # get_bot_context() already calls ensure_browser_session() internally —
    # calling it again here was redundant and could overlap a session check.
    with sync_playwright() as playwright:
        browser, context, page = get_bot_context(playwright)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit(
                "Saved JSON session expired or invalid.\n"
                "Run: python authenticate.py"
            )

        print("Using browser mode (Chrome)...\n")
        ensure_instagram_ready(page)

        # MAX_COMMENTS used to be treated as a boolean (>0 => exactly one comment,
        # regardless of value). This honors the configured count by re-opening the
        # hashtag feed's first post for each iteration.
        comment_count = 0
        post_url = ""
        seen_urls: set[str] = set()
        for _ in range(max(MAX_COMMENTS, 0)):
            go_to_hashtag_explore(page, HASHTAG_TO_SEARCH)
            post_url = open_first_post(page)
            if post_url in seen_urls:
                print("Same post came up again — nothing new to comment on.")
                break
            seen_urls.add(post_url)
            wait_human(2, 4)
            comment_on_current_post(page)
            comment_count += 1
            wait_human(3, 6)

        browser.close()

    print(f"\nDone. Post: {post_url}, Comments: {comment_count}")
