"""Quick spot-check for the two remaining outstanding issues."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from instagram_bot.auth.browser import ensure_browser_session, get_bot_context, has_session_cookie
from instagram_bot.config.settings import ENV_PATH, HASHTAG_TO_SEARCH
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
load_dotenv(ENV_PATH, override=True)

def main():
    ensure_browser_session()
    with sync_playwright() as pw:
        browser, context, page = get_bot_context(pw)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit("No session. Run authenticate.py")
        ctx = ToolContext(page=page)

        print("\n=== TEST: browse_reels_feed ===")
        r = execute_tool(ctx, "browse_reels_feed")
        print(f"  URL: {r.get('url')}")
        print(f"  page_type: {r.get('page_type')}")
        print(f"  reels count: {r.get('count')}")
        print(f"  first reel: {r.get('reels', [{}])[0] if r.get('reels') else 'NONE'}")

        print("\n=== TEST: follow_hashtag (expect graceful not-supported msg) ===")
        tag = HASHTAG_TO_SEARCH.lstrip("#")
        r2 = execute_tool(ctx, "follow_hashtag", {"hashtag": tag})
        print(f"  result: {r2}")

        print("\n=== TEST: search_account display_name quality ===")
        # Go home first so sidebar is available
        execute_tool(ctx, "go_home")
        r3 = execute_tool(ctx, "search_account", {"query": "realtor"})
        print(f"  count: {r3.get('count')}")
        for u in r3.get("results", [])[:3]:
            print(f"  - {u.get('username')} | display: {u.get('display_name', '')[:40]}")

        browser.close()

if __name__ == "__main__":
    main()
