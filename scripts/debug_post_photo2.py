"""Manually re-run the upload flow with polling on the dialog's actual text
content during the post-Share wait, so we see what Instagram is really showing
instead of a blind timeout."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("BOT_USER_ID", "user_3GoAZPGxKHCPHeqqOMZJxE9Ooy2")

from playwright.sync_api import sync_playwright
from instagram_bot.auth.browser import get_bot_context, ensure_instagram_ready
from instagram_bot.tools.actions import dismiss_all_popups
from instagram_bot.tools.context import ToolContext
from instagram_bot.db.convex_client import pending_media_posts, download_media_to_temp

OUT = Path(__file__).resolve().parents[1] / "debug_output" / "post_photo_manual2"
OUT.mkdir(parents=True, exist_ok=True)


def snap(page, name):
    page.screenshot(path=str(OUT / f"{name}.png"))
    print(f"  [snap] {name}  url={page.url}", flush=True)


with sync_playwright() as pw:
    browser, context, page = get_bot_context(pw)
    ensure_instagram_ready(page)
    ctx = ToolContext(page=page, gemini=None, goal="post photo")
    dismiss_all_popups(ctx)

    user_id = os.environ["BOT_USER_ID"]
    pending = pending_media_posts(user_id)
    print("pending:", [(p["_id"], p["original_name"]) for p in pending], flush=True)
    if not pending:
        raise SystemExit("nothing pending")

    queued = pending[0]
    caption = queued.get("caption", "")
    tmp = download_media_to_temp(queued["storage_id"], suffix=".jpeg")
    print("downloaded to", tmp, flush=True)
    from pathlib import Path as P
    p = P(tmp)

    # Step 1: Create button
    for sel in ['svg[aria-label="New post"]', 'svg[aria-label="Create"]', 'a[aria-label="New post"]']:
        el = page.locator(sel).first
        try:
            if el.is_visible(timeout=3000):
                parent = el.locator("xpath=ancestor::*[@role='button'][1] | ancestor::a[1]").first
                try:
                    parent.click(force=True, timeout=3000)
                except Exception:
                    el.click(force=True, timeout=3000)
                break
        except Exception:
            continue
    time.sleep(2)
    snap(page, "01_create_dialog")

    dialog = page.locator('div[role="dialog"]').first
    select_btn = None
    for sel in ['button:has-text("Select from computer")', 'div[role="button"]:has-text("Select from computer")']:
        el = dialog.locator(sel).first
        try:
            el.wait_for(state="visible", timeout=10000)
            select_btn = el
            break
        except Exception:
            continue
    if select_btn is None:
        raise SystemExit("no select button")

    file_chosen = False
    def _handle_chooser(chooser):
        global file_chosen
        chooser.set_files(str(p))
        file_chosen = True
    page.once("filechooser", _handle_chooser)
    select_btn.click(force=True)
    time.sleep(3)
    snap(page, "02_after_file_select")
    print("file_chosen:", file_chosen, flush=True)

    def click_next():
        for sel in ['div[role="button"]:has-text("Next")', 'button:has-text("Next")']:
            btn = dialog.locator(sel).first
            try:
                if btn.is_visible(timeout=4000):
                    btn.click(force=True)
                    time.sleep(2)
                    return True
            except Exception:
                continue
        return False

    print("next1:", click_next(), flush=True)
    snap(page, "03_after_next1")
    print("next2:", click_next(), flush=True)
    snap(page, "04_after_next2")

    if caption:
        for sel in ['div[aria-label*="caption" i][contenteditable="true"]',
                    'textarea[aria-label*="caption" i]', 'div[contenteditable="true"]']:
            inp = dialog.locator(sel).first
            try:
                if inp.is_visible(timeout=5000):
                    inp.click(force=True)
                    page.keyboard.type(caption, delay=20)
                    time.sleep(1)
                    break
            except Exception:
                continue
    snap(page, "05_after_caption")

    share_btn = None
    for sel in ['div[role="button"]:has-text("Share")', 'button:has-text("Share")']:
        btn = dialog.locator(sel).first
        try:
            if btn.is_visible(timeout=6000):
                share_btn = btn
                break
        except Exception:
            continue
    if share_btn is None:
        raise SystemExit("no share button")

    print("clicking Share...", flush=True)
    share_btn.click(force=True)

    for i in range(20):  # up to 100s, checking every 5s
        time.sleep(5)
        try:
            still_dialog = page.locator('div[role="dialog"]').count() > 0
            text = ""
            if still_dialog:
                try:
                    text = page.locator('div[role="dialog"]').first.inner_text(timeout=2000)
                except Exception:
                    text = "(could not read text)"
            print(f"  [+{(i+1)*5}s] dialog_present={still_dialog} text={text[:150]!r}", flush=True)
            snap(page, f"06_wait_{(i+1)*5}s")
            if not still_dialog:
                print("DIALOG CLOSED - upload likely completed", flush=True)
                break
        except Exception as e:
            print("poll error:", e, flush=True)

    browser.close()
