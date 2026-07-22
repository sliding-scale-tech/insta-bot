"""Perception tools — read page state without acting."""

from instagram_bot.agent.persistent_memory import normalize_url
from instagram_bot.config.settings import AGENT_MISSION, INSTAGRAM_USERNAME
from instagram_bot.perception.page_parser import (
    parse_comments,
    parse_current_post,
    parse_feed_posts,
    parse_page_state,
    parse_replies,
)
from instagram_bot.tools.context import ToolContext


def observe_page_state(ctx: ToolContext) -> dict:
    return parse_page_state(ctx.page)


def observe_feed(ctx: ToolContext, limit: int = 6) -> dict:
    posts = parse_feed_posts(ctx.page, limit=limit)
    return {"posts": posts, "count": len(posts), **parse_page_state(ctx.page)}


def observe_current_post(ctx: ToolContext) -> dict:
    post = parse_current_post(ctx.page)
    # Trim what actually gets sent back into Gemini's history — the parser can
    # return up to 800 chars of caption, more than the model needs to decide.
    if post.get("caption"):
        post["caption"] = post["caption"][:500]
    return post


def observe_replies(ctx: ToolContext, comment_index: int = 0, limit: int = 10) -> dict:
    """Expand and read replies for a specific comment by index."""
    replies = parse_replies(ctx.page, comment_index=comment_index, limit=limit)
    return {"comment_index": comment_index, "replies": replies, "count": len(replies), **parse_page_state(ctx.page)}


def observe_comments(ctx: ToolContext, limit: int = 10) -> dict:
    comments = parse_comments(ctx.page, limit=limit)
    return {"comments": comments, "count": len(comments), **parse_page_state(ctx.page)}


def _own_comment_in_dom(page, username: str) -> bool:
    """Check if our own username appears as a commenter anywhere in the post DOM."""
    try:
        found = page.evaluate(
            """(username) => {
                const root = document.querySelector('div[role="dialog"]') || document.querySelector('article') || document.body;
                // Find all profile links: /username/ pattern
                const links = root.querySelectorAll('a[href^="/"]');
                for (const link of links) {
                    const href = (link.getAttribute('href') || '').replace(/\\//g, '').toLowerCase();
                    if (href === username.toLowerCase()) return true;
                }
                return false;
            }""",
            username,
        )
        return bool(found)
    except Exception:
        return False


def evaluate_current_post(ctx: ToolContext) -> dict:
    """
    AI evaluation: should we comment on this post?
    1. Check persistent + session memory (no API call if already commented).
    2. Call Gemini evaluate_post_for_comment() for the decision.
    3. Return structured result so the agent can decide next action.
    """
    page = ctx.page
    url = page.url
    normalized = normalize_url(url)

    # Gather all commented URLs (persistent + session)
    persistent_urls = list(ctx.memory.get("persistent_commented_urls", []))
    session_urls = [normalize_url(u) for u in ctx.memory.get("commented_posts", [])]
    all_commented = set(persistent_urls) | set(session_urls)

    if normalized in all_commented:
        return {
            "already_commented": True,
            "should_comment": False,
            "confidence": 1.0,
            "reason": "Already commented on this post (in session or persistent memory)",
            "skip_reason": "duplicate",
            "url": url,
        }

    # Check skipped posts
    skipped = [normalize_url(u) for u in ctx.memory.get("skipped_posts", [])]
    if normalized in skipped:
        return {
            "should_comment": False,
            "confidence": 0.9,
            "reason": "Already skipped this post this session",
            "skip_reason": "already_skipped",
            "url": url,
        }

    post = parse_current_post(page)
    caption = post.get("caption", "")
    author = post.get("author", "")
    comments = post.get("comments_visible", [])

    # Check if our own account has already commented on this post (DOM scan)
    if INSTAGRAM_USERNAME:
        already_in_dom = _own_comment_in_dom(page, INSTAGRAM_USERNAME)
        if already_in_dom:
            return {
                "already_commented": True,
                "should_comment": False,
                "confidence": 1.0,
                "reason": f"@{INSTAGRAM_USERNAME} has already commented on this post",
                "skip_reason": "own_comment_detected",
                "url": url,
            }

    if ctx.gemini is None:
        # Dry-run: keyword check derived from the session goal (falls back to the
        # configured mission when the goal names no specific topic).
        source = ctx.goal or AGENT_MISSION
        keywords = [
            w.strip("#.,!?'\"()").lower()
            for w in source.split()
            if len(w.strip("#.,!?'\"()")) > 3
        ]
        is_relevant = any(k in (caption or "").lower() for k in keywords)
        return {
            "should_comment": is_relevant,
            "confidence": 0.7 if is_relevant else 0.3,
            "reason": "keyword match" if is_relevant else "no goal-related keywords found",
            "skip_reason": None if is_relevant else "not relevant",
            "url": url,
            "author": author,
            "caption_preview": (caption or "")[:100],
        }

    preview = (caption or "")[:60].encode("ascii", errors="replace").decode("ascii")
    print(f"  Gemini evaluating: @{author} -- {preview}...")
    result = ctx.gemini.evaluate_post_for_comment(
        caption=caption,
        author=author,
        comments=comments,
        commented_urls=list(all_commented),
        # The session goal is the authoritative niche; AGENT_MISSION is only a
        # fallback when the user gave no goal.
        mission=ctx.goal or AGENT_MISSION,
    )
    result["url"] = url
    result["author"] = author
    result["caption_preview"] = (caption or "")[:100]
    return result
