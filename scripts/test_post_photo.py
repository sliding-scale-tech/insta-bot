"""Test the post_photo tool — opens the Create dialog and walks through the steps."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from instagram_bot.auth.browser import ensure_browser_session, get_bot_context, has_session_cookie
from instagram_bot.config.settings import ENV_PATH
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
from instagram_bot.utils.verify import ToolVerifier
load_dotenv(ENV_PATH, override=True)

def main():
    ensure_browser_session()
    verifier = ToolVerifier()
    with sync_playwright() as pw:
        browser, context, page = get_bot_context(pw)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit("No session. Run authenticate.py")
        ctx = ToolContext(page=page)

        print("\n=== TEST: post_photo ===")
        try:
            r = execute_tool(ctx, "post_photo", {
                "image_path": "media/test_post.jpg",
                "caption": "Beautiful cornflower blue — test post from bot 🏠 #realestate",
            })
            verifier.record(page, "post_photo", r.get("success", False), detail=r)
            print(f"  Result: {r}")
        except Exception as e:
            verifier.record(page, "post_photo", False, error=str(e))
            print(f"  ERROR: {e}")
            import traceback; traceback.print_exc()

        report = verifier.write_report()
        print(f"\nReport: {report}")
        browser.close()

if __name__ == "__main__":
    main()
