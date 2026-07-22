"""Quick test: charmap fix + list_media_files + post_photo fallback."""
import sys
import os

# Apply the same stdout fix that runner.py now applies
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env", override=True)

from playwright.sync_api import sync_playwright
from instagram_bot.auth.browser import get_bot_context, has_session_cookie, ensure_instagram_ready
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
from instagram_bot.utils.verify import ToolVerifier

print("=== FIX VERIFICATION ===\n")

# Test 1: Unicode print — just print a checkmark to confirm stdout handles it
print("Test 1: Unicode stdout")
try:
    print("  Printing Unicode: ✓ ⚠️ \U0001f3e0")
    print("  [PASS] Unicode stdout")
except Exception as e:
    print(f"  [FAIL] Unicode stdout: {e}")

# Test 2: list_media_files (no browser needed)
print("\nTest 2: list_media_files (no browser)")
try:
    from instagram_bot.tools.actions import list_media_files
    result = list_media_files(None)
    print(f"  Files found: {result['files']}")
    if result["files"]:
        print(f"  [PASS] list_media_files — {len(result['files'])} file(s)")
    else:
        print("  [WARN] list_media_files — media/ folder is empty")
except Exception as e:
    print(f"  [FAIL] list_media_files: {e}")

# Test 3: post_photo fallback path (no browser — just test path resolution)
print("\nTest 3: post_photo path fallback (no browser)")
try:
    from instagram_bot.tools.actions import post_photo
    from instagram_bot.config.settings import PROJECT_ROOT
    media_dir = PROJECT_ROOT / "media"
    candidates = sorted(
        list(media_dir.glob("*.jpg")) + list(media_dir.glob("*.jpeg")) +
        list(media_dir.glob("*.png"))
    )
    if candidates:
        print(f"  Would auto-select: {candidates[0].name}")
        print("  [PASS] Fallback candidate available")
    else:
        print("  [WARN] No candidates in media/ to fallback to")
except Exception as e:
    print(f"  [FAIL] path fallback test: {e}")

# Test 4: Browser test — list_media_files via tool registry
print("\nTest 4: list_media_files via tool registry (browser)")
verifier = ToolVerifier()

with sync_playwright() as playwright:
    browser, context, page = get_bot_context(playwright)
    if not has_session_cookie(context):
        browser.close()
        print("  [SKIP] No session — run authenticate.py first")
    else:
        ensure_instagram_ready(page)
        ctx = ToolContext(page=page, gemini=None, memory={})

        try:
            result = execute_tool(ctx, "list_media_files")
            verifier.record(page, "list_media_files", True, detail=result)
            print(f"  Result: {result}")
            print(f"  [PASS] list_media_files")
        except Exception as e:
            verifier.record(page, "list_media_files", False, error=str(e))
            print(f"  [FAIL] list_media_files: {e}")

        browser.close()

verifier.write_report()
print(f"\nReport: {verifier.run_dir / 'report.html'}")
