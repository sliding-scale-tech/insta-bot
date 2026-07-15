"""Timed Instagram agent session powered by Gemini."""

import json
import os
import subprocess
import time
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from instagram_bot.agent.gemini_client import GeminiAgent
from instagram_bot.agent.memory import SessionMemory
from instagram_bot.agent.persistent_memory import (
    load_commented_urls,
    normalize_url,
    save_commented_url,
)
from instagram_bot.agent.prompts import build_system_prompt
from instagram_bot.auth.browser import (
    ensure_browser_session,
    ensure_instagram_ready,
    get_bot_context,
    has_session_cookie,
)
from instagram_bot.config.settings import (
    AGENT_MISSION,
    ENV_PATH,
    HASHTAG_TO_SEARCH,
    MAX_COMMENTS_PER_SESSION,
    MAX_DMS_PER_SESSION,
    MAX_FOLLOWS_PER_SESSION,
    MAX_LIKES_PER_SESSION,
    MAX_REPLIES_PER_SESSION,
    SESSION_MINUTES,
)
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.registry import execute_tool
from instagram_bot.utils.verify import ToolVerifier

load_dotenv(ENV_PATH, override=True)

_PID_FILE = Path(__file__).resolve().parents[2] / "data" / "bot.pid"


def _kill_previous_session() -> None:
    """Kill any lingering bot browser process from a previous run."""
    if not _PID_FILE.exists():
        return
    try:
        pid = int(_PID_FILE.read_text().strip())
        if pid == os.getpid():
            return
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            time.sleep(1)
        except Exception:
            pass
        print(f"  [safety] Cleaned up previous bot session (PID {pid})")
    except Exception:
        pass
    finally:
        try:
            _PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass


def _write_pid() -> None:
    _PID_FILE.write_text(str(os.getpid()))


def _clear_pid() -> None:
    try:
        _PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass


def _dry_run_plan(step: int, memory: SessionMemory) -> list[dict]:
    tag = HASHTAG_TO_SEARCH.lstrip("#")
    plans = [
        [{"name": "dismiss_popups", "arguments": {}}],
        [{"name": "open_hashtag", "arguments": {"hashtag": tag}}],
        [{"name": "observe_feed", "arguments": {"limit": 6}}],
        [{"name": "scroll_down", "arguments": {}}],
        [{"name": "open_post", "arguments": {"index": 0}}],
        [{"name": "observe_current_post", "arguments": {}}],
        [{"name": "evaluate_current_post", "arguments": {}}],
        [{"name": "observe_comments", "arguments": {"limit": 10}}],
        [{"name": "wait", "arguments": {"seconds": 3}}],
    ]
    if memory.comments_count < MAX_COMMENTS_PER_SESSION:
        plans.append([{"name": "ai_comment_on_post", "arguments": {}}])
    plans.append([{"name": "end_session", "arguments": {}}])
    idx = min(step, len(plans) - 1)
    return plans[idx]


def run_agent_session(dry_run: bool = False, verify: bool = True, goal: str = "") -> None:
    _kill_previous_session()
    _write_pid()
    try:
        _run_agent_session_inner(dry_run=dry_run, verify=verify, goal=goal)
    finally:
        _clear_pid()


def _run_agent_session_inner(dry_run: bool = False, verify: bool = True, goal: str = "") -> None:
    ensure_browser_session()

    # Load persistent cross-session memory
    persistent_urls = load_commented_urls()
    print(f"Loaded {len(persistent_urls)} previously commented URLs from persistent memory")

    memory = SessionMemory()
    # Pre-populate session memory with persistent URLs so has_commented() works immediately
    memory.commented_posts = list(persistent_urls)

    verifier = ToolVerifier() if verify else None
    end_at = time.time() + SESSION_MINUTES * 60
    step = 0

    dry_run = dry_run or os.getenv("AGENT_DRY_RUN", "").lower() in {"1", "true", "yes"}

    agent = None
    if not dry_run:
        agent = GeminiAgent()

    display_goal = (goal.strip() if goal.strip() else AGENT_MISSION)[:80]
    print(f"Starting agent session ({SESSION_MINUTES} min)")
    print(f"Mode: {'dry-run' if dry_run else 'gemini'}")
    print(f"Goal: {display_goal}")
    print(f"Safety caps: {MAX_COMMENTS_PER_SESSION} comments | {MAX_LIKES_PER_SESSION} likes | "
          f"{MAX_FOLLOWS_PER_SESSION} follows | {MAX_DMS_PER_SESSION} DMs")
    if verifier:
        print(f"Screenshots: {verifier.run_dir}\n")

    with sync_playwright() as playwright:
        browser, context, page = get_bot_context(playwright)
        if not has_session_cookie(context):
            browser.close()
            raise SystemExit("No valid session. Run: python authenticate.py")

        ensure_instagram_ready(page)

        # After auth flows (Continue / password popup), Instagram may have navigated
        # to a new page. Re-acquire the live page from context.
        live_pages = [p for p in context.pages if not p.is_closed()]
        ig_pages = [p for p in live_pages if "instagram.com" in p.url]
        if ig_pages:
            page = ig_pages[-1]
        elif live_pages:
            page = live_pages[-1]
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        else:
            page = context.new_page()
            page.goto("https://www.instagram.com/", wait_until="domcontentloaded")

        # Re-bind ctx with the correct live page
        ctx = ToolContext(
            page=page,
            gemini=agent,
            memory={
                "commented_posts": memory.commented_posts,
                "replied_comments": memory.replied_comments,
                "liked_items": memory.liked_items,
                "skipped_posts": memory.skipped_posts,
                "followed_users": memory.followed_users,
                "dm_sent": memory.dm_sent,
                "persistent_commented_urls": [normalize_url(u) for u in persistent_urls],
            },
        )

        system = build_system_prompt()
        active_goal = goal.strip() if goal.strip() else AGENT_MISSION
        mission_kickoff = (
            f"START NOW.\n\n"
            f"USER'S GOAL FOR THIS SESSION:\n"
            f"  \"{active_goal}\"\n\n"
            f"FIRST: Think about which hashtag best fits this goal, then call open_hashtag with it.\n"
            f"It navigates to Recent posts automatically so you see fresh content.\n\n"
            f"Use your tools to achieve the goal above. Decide yourself:\n"
            f"  - Which hashtag to start with (and rotate if needed)\n"
            f"  - Which posts to open and engage with\n"
            f"  - Whether to comment, like, reply to comments, follow, or DM\n"
            f"  - How many of each action based on what the goal asks for\n"
            f"  - When to call end_session (when the goal is done)\n\n"
            f"ALWAYS:\n"
            f"  - call evaluate_current_post before commenting\n"
            f"  - call observe_current_post first to read the post\n"
            f"  - call open_profile before send_dm\n"
            f"  - use skip_post to record posts you decided not to engage with\n"
            f"  - switch hashtag after 3+ skips in a row\n\n"
            f"FOR DMs:\n"
            f"  - First DM: 1 sentence, ask a SPECIFIC question about their work (e.g. 'How long have you been focused on [area]?')\n"
            f"  - Never say 'Congrats', 'Great post', or 'I'd love to connect' — just a real curious question\n"
            f"  - To check replies: read_inbox() then ai_reply_to_dm(thread_index=0), ai_reply_to_dm(thread_index=1), etc.\n"
            f"  - ai_reply_to_dm auto-skips threads where you sent last — just call it for each thread"
        )
        if agent and not dry_run:
            agent._history.append(
                agent._types.Content(
                    role="user",
                    parts=[agent._types.Part(text=f"{system}\n\n{mission_kickoff}")],
                )
            )

        consecutive_skips = 0
        last_was_view = False  # True when last meaningful action was open_post or observe_current_post
        current_hashtag = ""  # track which hashtag we're on for rotation hints
        used_hashtags: list[str] = []

        while time.time() < end_at:
            # ── Safety exit: hard caps hit ──────────────────────────────────
            if (memory.comments_count >= MAX_COMMENTS_PER_SESSION
                    and memory.dms_count >= MAX_DMS_PER_SESSION
                    and memory.likes_count >= MAX_LIKES_PER_SESSION):
                print(f"\nAll safety caps reached — ending session")
                break

            state = execute_tool(ctx, "observe_page_state")
            remaining = int(end_at - time.time())
            on_post = state.get("page_type") == "post"

            # Build context snapshot for this step
            commented_urls_list = [normalize_url(u) for u in memory.commented_posts]
            skipped_urls_list = [normalize_url(u) for u in memory.skipped_posts]

            all_hashtags = [
                "realestateagent", "realtor", "realestateinvesting", "realestateinvestor",
                "homesforsale", "luxuryrealestate", "commercialrealestate", "realestatetips", "realtorlife",
            ]
            available_hashtags = [h for h in all_hashtags if h not in used_hashtags] or all_hashtags

            status_block = (
                f"YOUR GOAL: \"{active_goal}\"\n"
                f"comments_done: {memory.comments_count} (cap: {MAX_COMMENTS_PER_SESSION})\n"
                f"dms_done: {memory.dms_count} (cap: {MAX_DMS_PER_SESSION})\n"
                f"likes_done: {memory.likes_count} (cap: {MAX_LIKES_PER_SESSION})\n"
                f"follows_done: {memory.follows_count} (cap: {MAX_FOLLOWS_PER_SESSION})\n"
                f"replies_done: {memory.replies_count} (cap: {MAX_REPLIES_PER_SESSION})\n"
                f"commented_urls: {json.dumps(commented_urls_list)}\n"
                f"skipped_urls: {json.dumps(skipped_urls_list)}\n"
                f"consecutive_skips: {consecutive_skips}\n"
                f"current_hashtag: {current_hashtag or 'none'}\n"
                f"time_left: {remaining}s"
            )

            # Inject contextual hints
            hint = ""
            if consecutive_skips >= 3:
                avoid = f" (NOT '{current_hashtag}')" if current_hashtag else ""
                hint += (
                    f"\n\n⚠️ HASHTAG ROTATION: You've skipped {consecutive_skips} posts in a row — switch hashtag NOW{avoid}. "
                    f"Pick from: {', '.join(available_hashtags[:5])}"
                )
            if on_post and not memory.has_commented(page.url) and not memory.has_skipped(page.url):
                hint += (
                    "\n\nREMINDER: You are on a post. "
                    "Call evaluate_current_post first before engaging."
                )

            # Note: system prompt is in _history[0] — don't repeat it here to save tokens
            prompt = (
                f"=== SESSION STATUS ===\n{status_block}\n"
                f"=== CURRENT STATE ===\n{json.dumps(state)}\n"
                f"{hint}\n"
                f"What do you do next?"
            )

            if dry_run:
                tool_calls = _dry_run_plan(step, memory)
            else:
                tool_calls = agent.decide(prompt)
                if not tool_calls:
                    tool_calls = [{"name": "wait", "arguments": {"seconds": 4}}]

            ended = False
            for call in tool_calls:
                name = call["name"]
                args = call.get("arguments", {})

                if name == "end_session":
                    ended = True
                    break

                # ── Guards ──────────────────────────────────────────────────
                if name in ("comment_on_post", "ai_comment_on_post"):
                    if memory.comments_count >= MAX_COMMENTS_PER_SESSION:
                        print(f"  BLOCKED {name}: comment cap reached")
                        continue
                    if memory.has_commented(page.url):
                        print(f"  BLOCKED {name}: already commented on {page.url}")
                        continue

                if name == "reply_to_comment":
                    if memory.replies_count >= MAX_REPLIES_PER_SESSION:
                        continue

                if name in ("like_post", "like_comment", "like_reply"):
                    if memory.likes_count >= MAX_LIKES_PER_SESSION:
                        continue
                    like_key = f"{name}::{page.url}::{args.get('comment_index', '')}::{args.get('reply_index', '')}"
                    if memory.has_liked(like_key):
                        continue

                if name == "follow_user":
                    if memory.follows_count >= MAX_FOLLOWS_PER_SESSION:
                        continue
                    if memory.has_followed(args.get("username", "")):
                        continue

                if name == "send_dm":
                    if memory.dms_count >= MAX_DMS_PER_SESSION:
                        continue

                try:
                    result = execute_tool(ctx, name, args)
                    memory.record_action(name, result)

                    # ── Post-execution memory updates ───────────────────────
                    if name in ("comment_on_post", "ai_comment_on_post") and result.get("success"):
                        memory.comments_count += 1
                        consecutive_skips = 0
                        post_url = result.get("post_url", page.url)
                        if not memory.has_commented(post_url):
                            memory.commented_posts.append(post_url)
                        # Persist to disk
                        save_commented_url(post_url, result.get("comment", result.get("generated_by", ""))[:100])
                        for _idx in result.get("comments_liked", []):
                            memory.likes_count += 1
                        print(f"  ✓ Comment #{memory.comments_count}: {post_url}")

                    if name == "reply_to_comment" and result.get("success"):
                        memory.replies_count += 1

                    if name in ("like_post", "like_comment", "like_reply") and result.get("success"):
                        memory.likes_count += 1
                        key = f"{name}::{page.url}::{args.get('comment_index', '')}::{args.get('reply_index', '')}"
                        memory.liked_items.append(key)

                    if name == "follow_user" and result.get("success") and not result.get("already_following"):
                        memory.follows_count += 1
                        uname = args.get("username", "")
                        if uname:
                            memory.followed_users.append(uname)

                    if name == "send_dm":
                        if result.get("success"):
                            memory.dms_count += 1
                            consecutive_skips = 0
                        elif result.get("skipped"):
                            # Already DM'd — track current post URL so bot won't re-open it
                            skipped_url = page.url
                            if not memory.has_skipped(skipped_url):
                                memory.skipped_posts.append(skipped_url)
                            consecutive_skips += 1

                    if name == "open_hashtag" and result.get("success"):
                        tag = args.get("hashtag", "")
                        if tag and tag not in used_hashtags:
                            used_hashtags.append(tag)
                        current_hashtag = tag
                        consecutive_skips = 0  # fresh hashtag resets skip counter

                    if name == "skip_post":
                        skipped_url = result.get("url", page.url)
                        if not memory.has_skipped(skipped_url):
                            memory.skipped_posts.append(skipped_url)
                        consecutive_skips += 1
                        last_was_view = False

                    # Track go_back after viewing a post without acting = passive skip
                    if name in ("open_post", "observe_current_post"):
                        last_was_view = True
                    elif name == "go_back" and last_was_view:
                        consecutive_skips += 1
                        last_was_view = False
                    elif name in ("send_dm", "ai_comment_on_post", "comment_on_post",
                                  "like_post", "follow_user", "ai_reply_to_comment"):
                        last_was_view = False
                        if name not in ("send_dm",):  # send_dm handles its own reset
                            consecutive_skips = 0

                    if agent and not dry_run:
                        agent.report_tool_result(name, result)

                    if verifier:
                        verifier.record(page, name, True, detail=result)

                    result_str = json.dumps(result, ensure_ascii=True)[:140]
                    print(f"  -> {name}: {result_str}")

                except Exception as error:
                    if verifier:
                        verifier.record(page, name, False, error=str(error))
                    print(f"  -> {name} FAILED: {error}")
                    if agent and not dry_run:
                        agent.report_tool_result(name, {"error": str(error)})
                    try:
                        execute_tool(ctx, "dismiss_popups")
                    except Exception:
                        pass

            step += 1
            if ended:
                break

            # Safety cap — emergency brake only
            if step > 150:
                print("Safety cap hit (150 steps)")
                break

        browser.close()

    if verifier:
        verifier.write_report()

    summary = memory.summary()
    print(f"\n{'='*50}")
    print(f"Session complete:")
    print(f"  Goal:     {(active_goal if 'active_goal' in dir() else '')[:60]}")
    print(f"  Comments: {summary['comments']}/{MAX_COMMENTS_PER_SESSION}")
    print(f"  Likes:    {summary['likes']}/{MAX_LIKES_PER_SESSION}")
    print(f"  Follows:  {summary['follows']}/{MAX_FOLLOWS_PER_SESSION}")
    print(f"  DMs:      {summary['dms']}/{MAX_DMS_PER_SESSION}")
    print(f"  Skipped:  {summary['posts_skipped']} posts")
    print(f"  Steps:    {step}")
    print(f"{'='*50}")

    if agent and not dry_run:
        try:
            agent.tokens.save()
            agent.tokens.print_summary()
        except Exception as e:
            print(f"Token tracking save failed: {e}")
