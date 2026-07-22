"""
Test all new features added in the FUTURE_FEATURES pass.
Saves screenshots + JSON for every step to debug_output/.

Run: python scripts/test_new_features.py
No Gemini API key required for most tests.
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
    get_bot_context,
    has_session_cookie,
)
from instagram_bot.config.settings import ENV_PATH, HASHTAG_TO_SEARCH
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
from instagram_bot.utils.verify import ToolVerifier

load_dotenv(ENV_PATH, override=True)


def run_check(verifier: ToolVerifier, ctx: ToolContext, name: str, fn) -> dict:
    print(f"\n--- Testing: {name} ---")
    try:
        detail = fn()
        verifier.record(ctx.page, name, True, detail=detail)
        print(f"  PASS: {str(detail)[:200]}")
        return {"ok": True, "detail": detail}
    except Exception as error:
        verifier.record(ctx.page, name, False, error=str(error))
        print(f"  FAIL: {error}")
        traceback.print_exc()
        return {"ok": False, "error": str(error)}


def main() -> None:
    print("New Features Test Suite")
    print("=" * 50)

    ensure_browser_session()
    verifier = ToolVerifier()
    print(f"Output folder: {verifier.run_dir}\n")

    with sync_playwright() as playwright:
        browser, context, page = get_bot_context(playwright)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit("No valid session. Run: python authenticate.py")

        ctx = ToolContext(page=page)
        results = {}

        # ── 1. Basic page state (sanity) ──────────────────────────────────────
        results["observe_page_state"] = run_check(
            verifier, ctx, "observe_page_state",
            lambda: execute_tool(ctx, "observe_page_state")
        )

        # ── 2. Browse Explore page ────────────────────────────────────────────
        results["browse_explore"] = run_check(
            verifier, ctx, "browse_explore",
            lambda: execute_tool(ctx, "browse_explore")
        )

        # ── 3. Browse Reels feed ──────────────────────────────────────────────
        results["browse_reels_feed"] = run_check(
            verifier, ctx, "browse_reels_feed",
            lambda: execute_tool(ctx, "browse_reels_feed")
        )

        # ── 4. Open a reel from feed and test reel parsing ────────────────────
        print("\n--- Testing: open_reel_and_parse ---")
        reel_result = execute_tool(ctx, "browse_reels_feed")
        reels = reel_result.get("reels", [])
        if reels:
            first_reel_url = reels[0].get("url", "")
            if first_reel_url:
                results["open_reel"] = run_check(
                    verifier, ctx, "open_reel",
                    lambda: execute_tool(ctx, "open_post", {"url": first_reel_url})
                )
                results["observe_reel_post"] = run_check(
                    verifier, ctx, "observe_reel_post",
                    lambda: execute_tool(ctx, "observe_current_post")
                )
                execute_tool(ctx, "go_back")
        else:
            print("  SKIP: No reels found in feed")

        # ── 5. Read Notifications ─────────────────────────────────────────────
        results["read_notifications"] = run_check(
            verifier, ctx, "read_notifications",
            lambda: execute_tool(ctx, "read_notifications")
        )

        # ── 6. Search account ─────────────────────────────────────────────────
        results["search_account"] = run_check(
            verifier, ctx, "search_account",
            lambda: execute_tool(ctx, "search_account", {"query": "realestateagent"})
        )

        # ── 7. Go to hashtag, open a post, test save + observe_replies ────────
        tag = HASHTAG_TO_SEARCH.lstrip("#")
        results["open_hashtag"] = run_check(
            verifier, ctx, "open_hashtag",
            lambda: execute_tool(ctx, "open_hashtag", {"hashtag": tag})
        )

        results["observe_feed"] = run_check(
            verifier, ctx, "observe_feed",
            lambda: execute_tool(ctx, "observe_feed", {"limit": 6})
        )

        results["open_post"] = run_check(
            verifier, ctx, "open_post",
            lambda: execute_tool(ctx, "open_post", {"index": 0})
        )

        results["observe_current_post"] = run_check(
            verifier, ctx, "observe_current_post",
            lambda: execute_tool(ctx, "observe_current_post")
        )

        # 7a. Comment pagination (observe_comments with load-more loop)
        results["observe_comments_paginated"] = run_check(
            verifier, ctx, "observe_comments_paginated",
            lambda: execute_tool(ctx, "observe_comments", {"limit": 30})
        )

        # 7b. observe_replies on first comment
        results["observe_replies"] = run_check(
            verifier, ctx, "observe_replies",
            lambda: execute_tool(ctx, "observe_replies", {"comment_index": 0, "limit": 5})
        )

        # 7c. save_post (bookmark)
        results["save_post"] = run_check(
            verifier, ctx, "save_post",
            lambda: execute_tool(ctx, "save_post")
        )

        # 7d. Get the post author for further tests
        post_data = execute_tool(ctx, "observe_current_post")
        author = post_data.get("author", "")
        print(f"\n  Post author: {author}")

        execute_tool(ctx, "go_back")

        # ── 8. Get followers / following of the post author ───────────────────
        if author:
            results["get_followers"] = run_check(
                verifier, ctx, "get_followers",
                lambda: execute_tool(ctx, "get_followers", {"username": author, "limit": 10})
            )
            results["get_following"] = run_check(
                verifier, ctx, "get_following",
                lambda: execute_tool(ctx, "get_following", {"username": author, "limit": 10})
            )
            execute_tool(ctx, "go_back")

        # ── 9. Follow a hashtag ───────────────────────────────────────────────
        results["follow_hashtag"] = run_check(
            verifier, ctx, "follow_hashtag",
            lambda: execute_tool(ctx, "follow_hashtag", {"hashtag": tag})
        )

        # ── 10. Share post via DM (skip actual send — just test the flow) ─────
        # Navigate to a post to test share button discovery only
        results["open_post_for_share"] = run_check(
            verifier, ctx, "open_post_for_share",
            lambda: execute_tool(ctx, "open_post", {"index": 0})
        )
        # We skip actually sending so we don't DM someone during testing
        print("\n--- Skipping share_post_via_dm actual send (would DM a real user) ---")

        browser.close()

    report = verifier.write_report()
    passed = sum(1 for v in results.values() if v.get("ok"))
    total = len(results)

    print("\n" + "=" * 50)
    print(f"SUMMARY: {passed}/{total} tools passed")
    for name, r in results.items():
        status = "PASS" if r.get("ok") else "FAIL"
        print(f"  {status}  {name}")
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
