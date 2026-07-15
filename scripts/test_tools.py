"""
Test each Instagram agent tool one-by-one.
Saves a screenshot + JSON for every step, then opens report.html.

Run: python scripts/test_tools.py
No Gemini API key required.
"""

import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from instagram_bot.auth.browser import (
    ensure_browser_session,
    ensure_instagram_ready,
    get_bot_context,
    has_session_cookie,
)
from instagram_bot.config.settings import COMMENT_TEXT, ENV_PATH, HASHTAG_TO_SEARCH
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
from instagram_bot.utils.verify import ToolVerifier

load_dotenv(ENV_PATH, override=True)


def run_check(verifier: ToolVerifier, ctx: ToolContext, name: str, fn) -> bool:
    try:
        detail = fn()
        verifier.record(ctx.page, name, True, detail=detail)
        return True
    except Exception as error:
        verifier.record(ctx.page, name, False, error=str(error))
        traceback.print_exc()
        return False


def main() -> None:
    print("Instagram Tool Verification")
    print("=" * 40)
    print("Each step saves a screenshot when checked.\n")

    ensure_browser_session()
    verifier = ToolVerifier()
    print(f"Output folder: {verifier.run_dir}\n")

    with sync_playwright() as playwright:
        browser, context, page = get_bot_context(playwright)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit("No valid session. Run: python authenticate.py")

        ctx = ToolContext(page=page)
        results: dict[str, bool] = {}

        # 1. Login / ready
        results["login_ready"] = run_check(
            verifier, ctx, "login_ready", lambda: {"url": page.url}
        )

        # 2. Dismiss popups
        results["dismiss_popups"] = run_check(
            verifier,
            ctx,
            "dismiss_popups",
            lambda: execute_tool(ctx, "dismiss_popups"),
        )

        # 3. Page state
        results["observe_page_state"] = run_check(
            verifier,
            ctx,
            "observe_page_state",
            lambda: execute_tool(ctx, "observe_page_state"),
        )

        # 4. Open hashtag
        tag = HASHTAG_TO_SEARCH.lstrip("#")
        results["open_hashtag"] = run_check(
            verifier,
            ctx,
            "open_hashtag",
            lambda: execute_tool(ctx, "open_hashtag", {"hashtag": tag}),
        )

        # 5. Observe feed
        results["observe_feed"] = run_check(
            verifier,
            ctx,
            "observe_feed",
            lambda: execute_tool(ctx, "observe_feed", {"limit": 6}),
        )

        # 6. Scroll
        results["scroll_down"] = run_check(
            verifier,
            ctx,
            "scroll_down",
            lambda: execute_tool(ctx, "scroll_down"),
        )

        # 7. Open first post
        results["open_post"] = run_check(
            verifier,
            ctx,
            "open_post",
            lambda: execute_tool(ctx, "open_post", {"index": 0}),
        )

        # 8. Read post
        post_detail = {}
        results["observe_current_post"] = run_check(
            verifier,
            ctx,
            "observe_current_post",
            lambda: execute_tool(ctx, "observe_current_post"),
        )

        # 9. Read comments
        comments_detail = {}
        try:
            comments_detail = execute_tool(ctx, "observe_comments", {"limit": 10})
            results["observe_comments"] = run_check(
                verifier,
                ctx,
                "observe_comments",
                lambda: comments_detail,
            )
        except Exception as error:
            results["observe_comments"] = run_check(
                verifier, ctx, "observe_comments", lambda: (_ for _ in ()).throw(error)
            )

        # 10. Comment on post
        test_comment = f"{COMMENT_TEXT} [tool-test]"
        results["comment_on_post"] = run_check(
            verifier,
            ctx,
            "comment_on_post",
            lambda: execute_tool(ctx, "comment_on_post", {"text": test_comment}),
        )

        # 11. Reply to comment (if any Reply buttons exist)
        reply_buttons = page.locator(
            'div[role="button"]:has-text("Reply"), span:has-text("Reply")'
        ).count()
        if reply_buttons > 0:
            results["reply_to_comment"] = run_check(
                verifier,
                ctx,
                "reply_to_comment",
                lambda: execute_tool(
                    ctx,
                    "reply_to_comment",
                    {
                        "text": "Thanks for sharing! [tool-test reply]",
                        "comment_index": 0,
                    },
                ),
            )
        else:
            verifier.record(
                page,
                "reply_to_comment",
                False,
                detail={"reply_buttons": 0},
                error="Skipped — no Reply buttons on this post",
            )
            results["reply_to_comment"] = False

        # 12. Go home
        results["go_home"] = run_check(
            verifier,
            ctx,
            "go_home",
            lambda: execute_tool(ctx, "go_home"),
        )

        browser.close()

    report = verifier.write_report()
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print("\n" + "=" * 40)
    print(f"SUMMARY: {passed}/{total} tools passed")
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\nOpen report in browser:\n  {report}")


if __name__ == "__main__":
    main()
