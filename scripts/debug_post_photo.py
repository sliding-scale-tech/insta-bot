"""Direct, no-Gemini test of post_photo — drives the real browser/session exactly
like the agent would, but calls the tool function directly. Logs every network
response and console message during the run so the actual failure reason is
visible instead of guessing from a spinner screenshot."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("BOT_USER_ID", "user_3GoAZPGxKHCPHeqqOMZJxE9Ooy2")

from playwright.sync_api import sync_playwright
from instagram_bot.auth.browser import get_bot_context, ensure_instagram_ready
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools import actions

OUT = Path(__file__).resolve().parents[1] / "debug_output" / "post_photo_manual"
OUT.mkdir(parents=True, exist_ok=True)


def snap(page, name):
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    print(f"  [snap] {name} -> {path}  url={page.url}")


with sync_playwright() as pw:
    browser, context, page = get_bot_context(pw)
    ensure_instagram_ready(page)
    snap(page, "00_home")

    # Log every response related to posting/uploading, and any 4xx/5xx anywhere.
    def on_response(resp):
        url = resp.url
        interesting = any(k in url for k in ("configure", "upload", "rupload", "create", "media"))
        if interesting or resp.status >= 400:
            print(f"  [net] {resp.status} {resp.request.method} {url}")

    def on_console(msg):
        if msg.type in ("error", "warning"):
            print(f"  [console:{msg.type}] {msg.text[:200]}")

    page.on("response", on_response)
    page.on("console", on_console)

    ctx = ToolContext(page=page, gemini=None, goal="post photo")

    listed = actions.list_media_files(ctx)
    print("list_media_files:", listed)

    print("Calling post_photo()...")
    result = actions.post_photo(ctx, image_path="", caption="")
    print("post_photo result:", result)
    snap(page, "99_final")

    browser.close()
