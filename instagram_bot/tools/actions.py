"""Action tools — comment, reply, like, follow, DMs, skip, dismiss popups."""

import random
import time

from instagram_bot.auth.browser import (
    dismiss_notifications_popup,
    dismiss_popups,
)
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.human import wait_human


def _visible(locator, timeout: int = 2000) -> bool:
    """Wait up to `timeout`ms for a locator to become visible. Returns False on timeout.

    Locator.is_visible(timeout=...) does NOT actually wait — it checks the current
    state instantly and the timeout kwarg is ignored, causing false negatives on
    elements that render a moment later. This actually polls.
    """
    try:
        locator.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def dismiss_all_popups(ctx: ToolContext) -> dict:
    dismiss_popups(ctx.page)
    dismiss_notifications_popup(ctx.page)
    dismissed_repost = _dismiss_repost_modal(ctx.page)
    return {"dismissed_repost": dismissed_repost}


def _dismiss_repost_modal(page) -> bool:
    # Only close dialogs that are specifically repost/share modals, NOT the post viewer modal.
    # We detect a repost modal by requiring the dialog to contain repost-related text.
    try:
        dialog = page.locator('div[role="dialog"]:has-text("Repost"), div[role="dialog"]:has-text("Share to"), div[role="dialog"]:has-text("Add to story")').first
        if _visible(dialog, 1000):
            close_btn = dialog.locator('svg[aria-label="Close"]').first
            if _visible(close_btn, 1000):
                close_btn.click(force=True)
                time.sleep(0.8)
                return True
    except Exception:
        pass
    return False


def _get_comment_textarea(page):
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


def _find_comment_post_button(page, textarea):
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


def _type_in_textarea(page, textarea, text: str) -> None:
    textarea.scroll_into_view_if_needed()
    textarea.click(force=True)
    wait_human(0.3, 0.6)
    textarea.fill("")
    for char in text:
        page.keyboard.insert_text(char)
        time.sleep(random.uniform(0.06, 0.18))
    wait_human(0.5, 1)


def _submit_textarea(page, textarea) -> None:
    post_btn = _find_comment_post_button(page, textarea)
    if post_btn is not None:
        post_btn.click(force=True)
        wait_human(1.5, 3)
        return
    textarea.press("Enter")
    wait_human(1.5, 3)


def comment_on_post(ctx: ToolContext, text: str) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)

    textarea = _get_comment_textarea(page)
    textarea.wait_for(state="visible", timeout=10000)
    _type_in_textarea(page, textarea, text)
    typed = textarea.input_value()
    if not typed.strip():
        raise RuntimeError("Comment text did not appear in textarea")

    _submit_textarea(page, textarea)
    _dismiss_repost_modal(page)

    # Verify the comment actually landed. Instagram can silently drop a submit
    # (rate limit / "Action Blocked" / button not firing) — without this check the
    # tool would report success and permanently mark the post as commented.
    verified = _comment_appears_on_page(page, text)
    if not verified:
        print("  [warn] Comment submit not verified on page — it may not have posted")

    post_url = page.url
    ctx.memory.setdefault("commented_posts", []).append(post_url)
    return {
        "success": True,
        "post_url": post_url,
        "comment": text,
        "verified": verified,
    }


def _comment_appears_on_page(page, text: str, timeout_ms: int = 6000) -> bool:
    """Poll the page for a distinctive slice of the comment we just submitted."""
    import time as _time

    # A middle slice avoids emoji/truncation issues at the edges.
    probe = (text or "").strip()[:60].strip()
    if len(probe) < 8:
        return False

    deadline = _time.time() + (timeout_ms / 1000)
    while _time.time() < deadline:
        try:
            # Textarea cleared is a strong signal the submit went through.
            body = page.inner_text("body")
            if probe in body:
                return True
        except Exception:
            pass
        _time.sleep(0.5)
    return False


def reply_to_comment(
    ctx: ToolContext,
    text: str,
    username: str | None = None,
    comment_index: int | None = None,
) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)

    # A single specific selector — "div[role=button], span" both matching the same
    # control (wrapper + inner text span) would double-count and shift every index.
    reply_buttons = page.locator('div[role="button"]:has-text("Reply")')
    if reply_buttons.count() == 0:
        raise RuntimeError("No Reply buttons visible on this post")

    idx = comment_index if comment_index is not None else 0
    if idx >= reply_buttons.count():
        raise RuntimeError(f"Reply index {idx} out of range ({reply_buttons.count()} replies)")

    target = reply_buttons.nth(idx)
    target.scroll_into_view_if_needed()
    wait_human(0.5, 1)
    target.click(force=True)
    wait_human(0.8, 1.5)

    textarea = _get_comment_textarea(page)
    textarea.wait_for(state="visible", timeout=8000)
    _type_in_textarea(page, textarea, text)
    _submit_textarea(page, textarea)
    _dismiss_repost_modal(page)

    key = f"{page.url}::{username or idx}"
    ctx.memory.setdefault("replied_comments", []).append(key)
    return {
        "success": True,
        "post_url": page.url,
        "reply_to_index": idx,
        "reply_to_username": username,
        "reply": text,
    }


def wait_idle(ctx: ToolContext, seconds: float | None = None) -> dict:
    wait_human(seconds or random.uniform(2, 5), (seconds or 5) + 2)
    return {"waited": True}


def like_post(ctx: ToolContext) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.5, 1)

    # Check if already liked (aria-label="Unlike" means it's already liked)
    already_liked = page.locator('svg[aria-label="Unlike"]').first
    if _visible(already_liked, 1000):
        return {"success": True, "liked": "post", "already_liked": True, "post_url": page.url}

    icon = page.locator('svg[aria-label="Like"]').first
    icon.wait_for(state="visible", timeout=8000)
    parent = icon.locator("xpath=ancestor::*[@role='button'][1]")
    if parent.count():
        parent.first.click(force=True)
    else:
        icon.click(force=True)
    wait_human(1, 2)

    # liked_items bookkeeping is owned by runner.py (single canonical key format,
    # used for both the pre-call dedup guard and the post-call record).
    return {"success": True, "liked": "post", "post_url": page.url}


def like_comment(ctx: ToolContext, comment_index: int = 0) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.5, 1)

    # Scroll comment panel so likes are reachable
    for selector in ('div[role="dialog"] ul', 'article ul'):
        try:
            panel = page.locator(selector).first
            if panel.count() and _visible(panel, 1500):
                panel.evaluate(
                    "(el, n) => { el.scrollTop = Math.min(el.scrollHeight, n * 120); }",
                    comment_index,
                )
                break
        except Exception:
            continue

    wait_human(0.3, 0.6)

    # Use ul-scoped selectors only — avoid hitting the post-level like button
    hearts = page.locator(
        'div[role="dialog"] ul svg[aria-label="Like"], '
        'article ul svg[aria-label="Like"]'
    )
    if hearts.count() == 0:
        # Narrower fallback: small like icons (12px) inside list items
        hearts = page.locator('ul li svg[aria-label="Like"]')
    if hearts.count() == 0:
        raise RuntimeError("No comment like buttons found inside comment list")

    idx = min(comment_index, hearts.count() - 1)
    target = hearts.nth(idx)
    target.scroll_into_view_if_needed()
    parent = target.locator("xpath=ancestor::*[@role='button'][1]")
    if parent.count():
        parent.first.click(force=True)
    else:
        target.click(force=True)
    wait_human(0.8, 1.5)

    return {"success": True, "liked": "comment", "comment_index": idx, "post_url": page.url}


def like_reply(ctx: ToolContext, comment_index: int = 0, reply_index: int = 0) -> dict:
    """Like a reply (sub-comment) on the open post."""
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.3, 0.7)

    # Expand replies on the target comment first.
    # NOTE: `div:has-text(...)` matches every ancestor div containing the text too,
    # not just the clickable control — that inflates .count() and breaks indexing.
    try:
        view_replies = page.locator(
            'div[role="button"]:has-text("View replies"), button:has-text("View replies")'
        )
        if view_replies.count() > comment_index:
            btn = view_replies.nth(comment_index)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)
            wait_human(1, 2)
    except Exception:
        pass

    # Reply likes are nested deeper: ul ul li
    reply_hearts = page.locator(
        'ul ul li svg[aria-label="Like"], '
        'ul ul div svg[aria-label="Like"]'
    )

    if reply_hearts.count() == 0:
        raise RuntimeError("No reply like buttons found — try expanding replies first")

    idx = min(reply_index, reply_hearts.count() - 1)
    target = reply_hearts.nth(idx)
    target.scroll_into_view_if_needed()
    parent = target.locator("xpath=ancestor::*[@role='button'][1]")
    if parent.count():
        parent.first.click(force=True)
    else:
        target.click(force=True)
    wait_human(0.8, 1.5)

    return {
        "success": True,
        "liked": "reply",
        "comment_index": comment_index,
        "reply_index": reply_index,
        "post_url": page.url,
    }


def ai_comment_on_post(ctx: ToolContext) -> dict:
    """Read post, like some comments, generate helpful Gemini comment, then post it."""
    from instagram_bot.perception.page_parser import parse_comments, parse_current_post

    if ctx.gemini is None:
        raise RuntimeError("Gemini agent not available for AI comments")

    # Respect the session-wide like cap — runner.py sets this before every step so
    # this internal liking can't silently blow past MAX_LIKES_PER_SESSION.
    likes_budget = min(2, ctx.memory.get("likes_remaining", 2))
    comments_liked: list[int] = []
    for idx in (0, 2, 1):
        if len(comments_liked) >= likes_budget:
            break
        try:
            like_comment(ctx, idx)
            comments_liked.append(idx)
        except Exception:
            continue

    post = parse_current_post(ctx.page)
    comments = parse_comments(ctx.page, limit=8)
    caption = post.get("caption") or post.get("title") or ""
    author = post.get("author") or ""

    print("  Gemini analyzing post and writing comment...")
    text = ctx.gemini.generate_helpful_comment(caption, author, comments, goal=ctx.goal)
    safe = text[:80].encode("ascii", errors="replace").decode("ascii")
    print(f"  Generated: {safe}...")

    result = comment_on_post(ctx, text)
    result["generated_by"] = "gemini"
    result["comments_liked"] = comments_liked
    return result


def ai_reply_to_comment(ctx: ToolContext, comment_index: int = 0) -> dict:
    """Read a specific comment and post a Gemini-generated natural reply."""
    from instagram_bot.perception.page_parser import parse_comments, parse_current_post

    if ctx.gemini is None:
        raise RuntimeError("Gemini agent not available")

    # Get the target comment
    comments = parse_comments(ctx.page, limit=comment_index + 5)
    if not comments or comment_index >= len(comments):
        raise RuntimeError(f"Comment index {comment_index} not found (only {len(comments)} visible)")

    target = comments[comment_index]
    comment_text = target.get("text", "")
    comment_author = target.get("username", "")

    if not comment_text:
        raise RuntimeError(f"Comment {comment_index} has no text")

    # Get post context for better replies
    post = parse_current_post(ctx.page)
    caption = post.get("caption", "")
    post_author = post.get("author", "")

    print(f"  Replying to @{comment_author}: {comment_text[:60]}...")
    reply_text = ctx.gemini.generate_reply_to_comment(
        comment_text=comment_text,
        comment_author=comment_author,
        post_caption=caption,
        post_author=post_author,
    )

    safe = reply_text[:60].encode("ascii", errors="replace").decode("ascii")
    print(f"  Generated reply: {safe}...")

    result = reply_to_comment(ctx, text=reply_text, username=comment_author, comment_index=comment_index)
    result["replied_to_comment"] = comment_text[:80]
    result["replied_to_user"] = comment_author
    result["reply_generated_by"] = "gemini"
    return result


def skip_post(ctx: ToolContext, reason: str = "") -> dict:
    """Record this post as skipped (won't re-open this session) and go back."""
    from instagram_bot.tools.navigation import go_back

    url = ctx.page.url
    ctx.memory.setdefault("skipped_posts", []).append(url)
    go_back(ctx)
    safe_reason = str(reason).encode("ascii", errors="replace").decode("ascii")
    print(f"  Skipped: {url} -- {safe_reason}")
    return {"skipped": True, "url": url, "reason": reason}


def follow_user(ctx: ToolContext, username: str) -> dict:
    """Follow a user. Navigates to their profile if not already there."""
    page = ctx.page
    username = username.lstrip("@").strip()

    if f"/{username}" not in page.url:
        page.goto(
            f"https://www.instagram.com/{username}/",
            wait_until="domcontentloaded",
        )
        try:
            page.locator(
                'div[role="button"]:has-text("Follow"), '
                'div[role="button"]:has-text("Following"), '
                'div[role="button"]:has-text("Message")'
            ).first.wait_for(state="visible", timeout=6000)
        except Exception:
            pass
        wait_human(1.5, 2.5)

    dismiss_all_popups(ctx)

    # Check if already following
    following_btn = page.locator(
        'div[role="button"]:has-text("Following"), button:has-text("Following")'
    ).first
    if _visible(following_btn, 2000):
        return {"success": True, "already_following": True, "username": username}

    follow_btn = page.locator(
        'div[role="button"]:has-text("Follow"):not(:has-text("Following")), '
        'button:has-text("Follow"):not(:has-text("Following"))'
    ).first
    if not _visible(follow_btn, 5000):
        return {"success": False, "reason": "Follow button not found", "username": username}

    follow_btn.click(force=True)
    wait_human(1.5, 2.5)
    ctx.memory.setdefault("followed_users", []).append(username)
    return {"success": True, "followed": username}


def unfollow_user(ctx: ToolContext, username: str) -> dict:
    """Unfollow a user."""
    page = ctx.page
    username = username.lstrip("@").strip()

    if f"/{username}" not in page.url:
        page.goto(
            f"https://www.instagram.com/{username}/",
            wait_until="domcontentloaded",
        )
        wait_human(2, 3)

    dismiss_all_popups(ctx)

    following_btn = page.locator(
        'div[role="button"]:has-text("Following"), button:has-text("Following")'
    ).first
    if not _visible(following_btn, 4000):
        return {"success": False, "reason": "Not following this user", "username": username}

    following_btn.click(force=True)
    wait_human(1, 1.5)

    # Confirm unfollow in dialog
    unfollow_confirm = page.locator(
        'button:has-text("Unfollow"), div[role="button"]:has-text("Unfollow")'
    ).first
    if _visible(unfollow_confirm, 3000):
        unfollow_confirm.click(force=True)
        wait_human(1, 2)

    return {"success": True, "unfollowed": username}


def send_dm(ctx: ToolContext, username: str, text: str) -> dict:
    """Send a DM to a user via their profile's Message button. Skips if already DM'd."""
    from instagram_bot.agent.dm_memory import has_dm_sent, save_dm_sent
    page = ctx.page
    username = username.lstrip("@").strip()

    if has_dm_sent(username):
        return {"success": False, "skipped": True, "reason": f"Already DM'd @{username} in a previous session"}

    # Always use the dedicated DM generator to ensure proper tone (genuine question, not compliments)
    if ctx.gemini:
        try:
            text = ctx.gemini.generate_dm_message(username, context=text or "")
        except Exception:
            pass  # fall back to whatever text was provided

    dismiss_all_popups(ctx)

    # Navigate to profile to click Message button
    if f"/{username}" not in page.url:
        page.goto(
            f"https://www.instagram.com/{username}/",
            wait_until="domcontentloaded",
        )
        try:
            page.locator(
                'div[role="button"]:has-text("Message"), button:has-text("Message")'
            ).first.wait_for(state="visible", timeout=6000)
        except Exception:
            pass
        wait_human(1.5, 2.5)

    msg_selectors = [
        'div[role="button"]:has-text("Message")',
        'button:has-text("Message")',
        'a:has-text("Message")',
    ]
    clicked = False
    for sel in msg_selectors:
        try:
            btn = page.locator(sel).first
            if _visible(btn, 3000):
                btn.click(force=True)
                clicked = True
                wait_human(1.5, 3)
                break
        except Exception:
            continue

    if not clicked:
        raise RuntimeError(f"Message button not found on @{username}'s profile")

    # Instagram opens DMs as a floating mini-popup (contenteditable div) or full page.
    # contenteditable works for both; aria-label="Message" only on the full page.
    inp = None
    for sel in [
        'div[contenteditable="true"]',
        'div[aria-label="Message"]',
    ]:
        try:
            loc = page.locator(sel).last
            loc.wait_for(state="visible", timeout=4000)
            inp = loc
            print(f"  [DM] Found input: {sel}")
            break
        except Exception:
            continue

    if inp is None:
        raise RuntimeError(f"DM message input not found after opening conversation with @{username}")

    inp.click()
    wait_human(0.4, 0.7)
    page.keyboard.type(text, delay=80)
    wait_human(0.5, 1)

    send_btn = page.locator('div[role="button"]:has-text("Send"), button:has-text("Send")').first
    if _visible(send_btn, 2000):
        send_btn.click(force=True)
    else:
        page.keyboard.press("Enter")
    wait_human(1, 2)
    ctx.memory.setdefault("dm_sent", []).append(username)
    save_dm_sent(username, text[:120])
    return {"success": True, "dm_sent_to": username, "message": text}


def read_inbox(ctx: ToolContext, limit: int = 10) -> dict:
    """Navigate to DM inbox, wait for threads to load, return thread list."""
    from instagram_bot.perception.page_parser import parse_inbox
    from instagram_bot.tools.navigation import open_inbox

    # Always navigate to the inbox page (not a mini-popup or thread)
    if "/direct/inbox" not in ctx.page.url:
        open_inbox(ctx)
        wait_human(2, 3)

    # Wait for inbox content to load — try multiple signals
    for wait_sel in [
        'a[href*="/direct/t/"]',
        'div[tabindex="0"] img[alt]',
        'div[role="button"] img[alt]',
        'span:has-text("Messages")',
    ]:
        try:
            ctx.page.locator(wait_sel).first.wait_for(state="visible", timeout=5000)
            break
        except Exception:
            continue

    threads = parse_inbox(ctx.page, limit=limit)
    return {"threads": threads, "count": len(threads)}


def reply_to_dm(ctx: ToolContext, thread_index: int = 0, text: str = "") -> dict:
    """Reply in an open DM thread (click thread by index, then type reply)."""
    page = ctx.page

    if "/direct/inbox" in page.url:
        items = page.locator('div[role="listitem"]')
        if items.count() > thread_index:
            items.nth(thread_index).click(force=True)
            wait_human(1.5, 2.5)

    inp = None
    for sel in ['div[contenteditable="true"]', 'div[aria-label="Message"]']:
        try:
            loc = page.locator(sel).last
            loc.wait_for(state="visible", timeout=4000)
            inp = loc
            break
        except Exception:
            continue

    if inp is None:
        raise RuntimeError("DM message input not found")

    inp.click()
    wait_human(0.3, 0.6)
    page.keyboard.type(text, delay=80)
    wait_human(0.4, 0.8)

    send_btn = page.locator('div[role="button"]:has-text("Send"), button:has-text("Send")').first
    if _visible(send_btn, 2000):
        send_btn.click(force=True)
    else:
        page.keyboard.press("Enter")
    wait_human(1, 2)
    return {"success": True, "replied_in_thread": thread_index, "text": text}


def save_post(ctx: ToolContext) -> dict:
    """Bookmark/save the currently open post."""
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.3, 0.6)

    # Check if already saved (aria-label="Remove" on save icon means saved)
    already_saved = page.locator('svg[aria-label="Remove"]').first
    if _visible(already_saved, 1000):
        return {"success": True, "saved": True, "already_saved": True, "post_url": page.url}

    save_icon = page.locator('svg[aria-label="Save"]').first
    if not _visible(save_icon, 5000):
        return {"success": False, "reason": "Save button not found", "post_url": page.url}

    parent = save_icon.locator("xpath=ancestor::*[@role='button'][1]")
    if parent.count():
        parent.first.click(force=True)
    else:
        save_icon.click(force=True)
    wait_human(0.8, 1.5)

    return {"success": True, "saved": True, "post_url": page.url}


def share_post_via_dm(ctx: ToolContext, username: str) -> dict:
    """Share the currently open post to a user via DM using the share/send button."""
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.3, 0.6)

    # Click the paper-plane / share icon on the post
    share_selectors = [
        'svg[aria-label="Share Post"]',
        'svg[aria-label="Share"]',
        'div[role="button"][aria-label*="share" i]',
    ]
    clicked = False
    for sel in share_selectors:
        try:
            el = page.locator(sel).first
            if _visible(el, 2000):
                parent = el.locator("xpath=ancestor::*[@role='button'][1]")
                if parent.count():
                    parent.first.click(force=True)
                else:
                    el.click(force=True)
                clicked = True
                wait_human(1, 1.5)
                break
        except Exception:
            continue

    if not clicked:
        return {"success": False, "reason": "Share button not found on post", "post_url": page.url}

    # In the share sheet, search for the username
    try:
        search = page.locator('input[placeholder*="Search"], input[aria-label*="Search"]').first
        if _visible(search, 3000):
            search.fill(username)
            wait_human(1.5, 2.5)

            # Click the user result
            result = page.locator(
                f'div[role="button"]:has-text("{username}"), span:has-text("{username}")'
            ).first
            if _visible(result, 3000):
                result.click(force=True)
                wait_human(0.8, 1.5)
    except Exception:
        pass

    # Click Send
    send_btn = page.locator('div[role="button"]:has-text("Send"), button:has-text("Send")').first
    if _visible(send_btn, 3000):
        send_btn.click(force=True)
        wait_human(1, 2)
        return {"success": True, "shared_to": username, "post_url": page.url}

    return {"success": False, "reason": "Send button not found in share sheet", "post_url": page.url}


def post_photo(ctx: ToolContext, image_path: str = "", caption: str = "") -> dict:
    """Upload a photo/video and post it to Instagram with a caption.

    Prefers the dashboard-uploaded media queue (Convex `media_posts`, status
    "pending") — each file there is posted AT MOST ONCE; on success it's flipped
    to "posted" so it can never be reused. Call list_media_files first to see
    what's queued. image_path is only used as a fallback for the legacy
    project-root media/ folder when nothing is queued.

    Files live in Convex file storage, not on disk — this downloads to a temp
    file only for the duration of the upload, then deletes it, so the VPS disk
    never accumulates media.
    """
    import os
    from pathlib import Path
    from instagram_bot.config.settings import PROJECT_ROOT

    page = ctx.page
    dismiss_all_popups(ctx)

    user_id = os.environ.get("BOT_USER_ID", "default")
    media_id = None
    temp_path: str | None = None

    if not image_path:
        # Pull the oldest not-yet-posted upload for this user from Convex.
        try:
            from instagram_bot.db.convex_client import pending_media_posts, download_media_to_temp
            pending = pending_media_posts(user_id)
        except Exception:
            pending = []
        if not pending:
            return {
                "success": False,
                "reason": "No pending uploads queued. Upload a photo from the dashboard's Posts tab first.",
            }

        queued = pending[0]
        media_id = queued["_id"]
        caption = caption or queued.get("caption", "")
        suffix = Path(queued.get("original_name", "")).suffix or ".jpg"
        temp_path = download_media_to_temp(queued["storage_id"], suffix=suffix)
        if not temp_path:
            try:
                from instagram_bot.db.convex_client import mark_media_error
                mark_media_error(media_id, "Failed to download from Convex storage")
            except Exception:
                pass
            return {"success": False, "reason": "Could not download queued media from storage"}
        p = Path(temp_path)
    else:
        p = Path(image_path)
        if not p.is_absolute():
            p = PROJECT_ROOT / image_path
        if not p.exists():
            return {"success": False, "reason": f"File not found: {p}"}

    try:
        result = _upload_and_share(page, p, caption)
    finally:
        # Always clean up the temp download — never leave media on VPS disk.
        if temp_path:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    if media_id:
        try:
            if result.get("success"):
                from instagram_bot.db.convex_client import mark_media_posted
                mark_media_posted(media_id, post_url=page.url)
            else:
                from instagram_bot.db.convex_client import mark_media_error, upload_error_screenshot
                screenshot_id = None
                try:
                    screenshot_id = upload_error_screenshot(page.screenshot())
                except Exception:
                    pass
                mark_media_error(
                    media_id,
                    result.get("reason", "Unknown error"),
                    error_screenshot_id=screenshot_id,
                )
        except Exception:
            pass

    return result


def _upload_and_share(page, p, caption: str) -> dict:
    """Drive Instagram's Create dialog: select file, advance steps, caption, share."""
    # ── Step 1: Click the Create (+) button in the sidebar ───────────────────
    create_selectors = [
        'svg[aria-label="New post"]',
        'svg[aria-label="Create"]',
        'a[aria-label="New post"]',
    ]
    clicked = False
    for sel in create_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                parent = el.locator("xpath=ancestor::*[@role='button'][1] | ancestor::a[1]").first
                try:
                    parent.click(force=True, timeout=3000)
                except Exception:
                    el.click(force=True, timeout=3000)
                clicked = True
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue

    if not clicked:
        return {"success": False, "reason": "Create/New post (+) button not found in sidebar"}

    # ── Step 2: Wait for dialog to load, then select the file ────────────────
    # The Create dialog shows a loading spinner first — wait for content
    try:
        page.locator('div[role="dialog"]').first.wait_for(state="visible", timeout=8000)
    except Exception:
        return {"success": False, "reason": "Create dialog did not open"}

    # Wait for "Select from computer" button to appear (spinner must finish)
    select_btn = None
    for sel in [
        'button:has-text("Select from computer")',
        'div[role="button"]:has-text("Select from computer")',
    ]:
        try:
            el = page.locator(sel).first
            el.wait_for(state="visible", timeout=10000)
            select_btn = el
            break
        except Exception:
            continue

    if select_btn is None:
        return {"success": False, "reason": "Select from computer button did not appear in Create dialog"}

    # Register filechooser handler BEFORE clicking the trigger
    file_chosen = False

    def _handle_chooser(chooser):
        nonlocal file_chosen
        chooser.set_files(str(p))
        file_chosen = True

    page.once("filechooser", _handle_chooser)
    select_btn.click(force=True)
    # Give the file chooser time to fire and the preview to start rendering
    wait_human(2, 3)

    if not file_chosen:
        # Fallback: directly set the hidden file input
        try:
            inp = page.locator('input[type="file"]').first
            if inp.count():
                inp.set_input_files(str(p))
                file_chosen = True
                wait_human(2, 3)
        except Exception:
            pass

    if not file_chosen:
        return {"success": False, "reason": "File chooser did not fire — could not upload image"}

    # Wait for the image preview to render inside the dialog
    try:
        page.locator('div[role="dialog"] img, div[role="dialog"] canvas').first.wait_for(
            state="visible", timeout=8000
        )
    except Exception:
        pass
    wait_human(1, 2)

    # ── Step 3: Advance through Crop → Filters → Caption ─────────────────────
    # The number of "Next" steps isn't fixed (IG sometimes inserts an extra
    # step, e.g. an accessibility/alt-text screen) — clicking exactly twice
    # was brittle and silently landed on the wrong step. Instead, click Next
    # repeatedly, scoped to the dialog, until either the caption box or the
    # Share button becomes visible (we've reached the final step).
    dialog = page.locator('div[role="dialog"]').first

    def _at_caption_step() -> bool:
        try:
            return dialog.locator(
                'div[aria-label*="caption" i][contenteditable="true"], '
                'textarea[aria-label*="caption" i], '
                'div[role="button"]:has-text("Share"), button:has-text("Share")'
            ).first.is_visible(timeout=1500)
        except Exception:
            return False

    def _click_dialog_next() -> bool:
        for sel in [
            'div[role="button"]:has-text("Next")',
            'button:has-text("Next")',
        ]:
            try:
                btn = dialog.locator(sel).first
                if btn.is_visible(timeout=4000):
                    btn.click(force=True)
                    wait_human(1.5, 2.5)
                    return True
            except Exception:
                continue
        return False

    steps_clicked = 0
    while not _at_caption_step() and steps_clicked < 5:
        if not _click_dialog_next():
            break
        steps_clicked += 1

    if not _at_caption_step():
        return {
            "success": False,
            "reason": f"Never reached the caption/Share step after {steps_clicked} Next click(s)",
        }

    # ── Step 4: Type the caption ──────────────────────────────────────────────
    if caption:
        dialog = page.locator('div[role="dialog"]').first
        for sel in [
            'div[aria-label*="caption" i][contenteditable="true"]',
            'textarea[aria-label*="caption" i]',
            'div[contenteditable="true"]',
        ]:
            try:
                inp = dialog.locator(sel).first
                if inp.is_visible(timeout=5000):
                    inp.click(force=True)
                    wait_human(0.5, 0.8)
                    page.keyboard.type(caption, delay=55)
                    wait_human(0.8, 1.5)
                    break
            except Exception:
                continue

    # ── Step 5: Click Share ───────────────────────────────────────────────────
    dialog = page.locator('div[role="dialog"]').first
    for sel in [
        'div[role="button"]:has-text("Share")',
        'button:has-text("Share")',
    ]:
        try:
            share_btn = dialog.locator(sel).first
            if share_btn.is_visible(timeout=6000):
                share_btn.click(force=True)
                # After Share, Instagram shows a "Sharing" spinner and then a
                # "Post shared / Your post has been shared." confirmation screen
                # with a "Done" button — the dialog element itself never becomes
                # hidden on its own (confirmed by direct observation), so waiting
                # for state="hidden" blocks forever even on a genuine success.
                # Poll for the confirmation text instead, then click Done.
                confirmed = False
                for _ in range(24):  # up to ~72s (24 * 3s)
                    try:
                        if dialog.count() == 0:
                            confirmed = True  # dialog closed on its own
                            break
                        text = dialog.inner_text(timeout=2000)
                        if "shared" in text.lower() or "post shared" in text.lower():
                            confirmed = True
                            break
                    except Exception:
                        pass
                    wait_human(2.5, 3.5)

                if not confirmed:
                    return {
                        "success": False,
                        "reason": "Share was clicked but no share confirmation appeared "
                                   "(upload may still be processing or failed) — not "
                                   "confirmed posted",
                        "image": str(p),
                    }

                # Dismiss the confirmation dialog so it doesn't block the next action.
                for done_sel in ['div[role="button"]:has-text("Done")', 'button:has-text("Done")']:
                    try:
                        done_btn = dialog.locator(done_sel).first
                        if done_btn.is_visible(timeout=3000):
                            done_btn.click(force=True)
                            wait_human(1, 2)
                            break
                    except Exception:
                        continue

                return {"success": True, "posted": True, "image": str(p.name), "caption": caption[:100]}
        except Exception:
            continue

    return {"success": False, "reason": "Share button not found at Caption step", "image": str(p)}


def list_media_files(ctx: ToolContext) -> dict:
    """Return media uploaded from the dashboard's Posts tab and not yet posted.

    Each entry is posted at most once — call post_photo() with no image_path to
    post the oldest pending one; it's automatically marked "posted" afterward.
    """
    import os
    from instagram_bot.db.convex_client import pending_media_posts

    user_id = os.environ.get("BOT_USER_ID", "default")
    pending = pending_media_posts(user_id)
    if not pending:
        return {
            "files": [],
            "note": "No pending uploads. The user needs to upload a photo from the dashboard's Posts tab first.",
        }
    return {
        "files": [
            {"name": p.get("original_name"), "caption": p.get("caption", "")}
            for p in pending
        ],
        "note": "Call post_photo() with no image_path — it posts the oldest pending upload and marks it posted.",
    }


def follow_hashtag(ctx: ToolContext, hashtag: str) -> dict:
    """Follow a hashtag — must be on the hashtag's explore page.

    Note: Instagram removed the hashtag follow feature in late 2023. This function
    navigates to the hashtag page and attempts to find the Follow button; if none
    exists, it returns a clear not-supported message rather than silently failing.
    """
    from instagram_bot.tools.navigation import open_hashtag

    page = ctx.page
    hashtag = hashtag.lstrip("#").strip()

    # Navigate to the hashtag page if not already there
    if f"/explore/tags/{hashtag}" not in page.url:
        open_hashtag(ctx, hashtag)

    dismiss_all_popups(ctx)
    wait_human(0.5, 1)

    # Check if already following
    following = page.locator('div[role="button"]:has-text("Following"), button:has-text("Following")').first
    if _visible(following, 1500):
        return {"success": True, "already_following_hashtag": True, "hashtag": hashtag}

    # Click the Follow button for the hashtag
    follow_selectors = [
        'div[role="button"]:has-text("Follow"):not(:has-text("Following"))',
        'button:has-text("Follow"):not(:has-text("Following"))',
        '[aria-label*="follow" i][role="button"]',
    ]
    for sel in follow_selectors:
        try:
            btn = page.locator(sel).first
            if _visible(btn, 2000):
                btn.click(force=True)
                wait_human(1, 2)
                return {"success": True, "followed_hashtag": hashtag}
        except Exception:
            continue

    # Instagram removed hashtag following in late 2023 — no Follow button will exist
    return {
        "success": False,
        "reason": "Follow button not available — Instagram removed hashtag following in 2023/2024",
        "hashtag": hashtag,
        "note": "Use open_hashtag to browse posts tagged #" + hashtag + " instead",
    }


def ai_reply_to_dm(ctx: ToolContext, thread_index: int = 0) -> dict:
    """
    Check a DM thread — only reply if THEY sent the last message (they replied to us).
    Detects by checking if inbox preview starts with 'You:' (= we sent last).
    Waits ~8-15s like a human, then sends a short warm-lead reply in English.
    """
    from instagram_bot.perception.page_parser import parse_inbox

    if ctx.gemini is None:
        raise RuntimeError("Gemini agent not available for AI DM replies")

    page = ctx.page

    # Go to inbox first to read previews (most reliable reply detection)
    if "/direct/inbox" not in page.url:
        from instagram_bot.tools.navigation import open_inbox
        open_inbox(ctx)

    # Use the same reliable parse_inbox parser used by read_inbox
    threads = parse_inbox(page, limit=20)

    if thread_index >= len(threads):
        return {"success": False, "skipped": True, "reason": f"Thread index {thread_index} not found in inbox (only {len(threads)} threads)"}

    thread = threads[thread_index]
    preview = thread.get("preview", "")
    username = thread.get("username", f"thread_{thread_index}")
    print(f"  [DM reply] Thread @{username} preview: {preview[:100]}")

    # If preview starts with "You:" — we sent last, no reply from them yet
    if preview.lower().startswith("you:") or preview.lower().startswith("you "):
        return {
            "success": False,
            "skipped": True,
            "reason": f"@{username} hasn't replied yet (last message was ours)",
        }

    # They replied — open the thread by clicking it
    thread_href = thread.get("href", "")
    clicked = False
    if thread_href:
        try:
            link = page.locator(f'a[href="{thread_href}"]').first
            if _visible(link, 2000):
                link.click(force=True)
                wait_human(1.5, 2.5)
                clicked = True
        except Exception:
            pass
    if not clicked:
        # Instagram inbox uses div rows with img[alt="user-profile-picture"] avatars
        # Click the parent row of the nth avatar image
        dom_idx = thread.get("domIndex", thread_index)
        try:
            clicked = page.evaluate(f"""() => {{
                const imgs = document.querySelectorAll('img[alt="user-profile-picture"]');
                const img = imgs[{dom_idx}];
                if (!img) return false;
                // Walk up to find a clickable ancestor
                let el = img.parentElement;
                for (let i = 0; i < 8 && el; i++) {{
                    const txt = (el.textContent || '').trim();
                    if (txt.length > 5 && txt.length < 600) {{
                        el.click();
                        return true;
                    }}
                    el = el.parentElement;
                }}
                return false;
            }}""")
        except Exception:
            pass
        if clicked:
            wait_human(1.5, 2.5)
    if not clicked:
        # Last resort: listitem by index
        items = page.locator('div[role="listitem"]')
        if items.count() > thread_index:
            items.nth(thread_index).click(force=True)
            wait_human(1.5, 2.5)

    # Read recent messages for context
    messages = page.evaluate("""() => {
        const divs = document.querySelectorAll('div[dir="auto"], span[dir="auto"]');
        const texts = [];
        for (const d of divs) {
            const t = (d.textContent || '').trim();
            if (t && t.length > 2 && t.length < 400) texts.push(t);
        }
        return [...new Set(texts)].slice(-8);
    }""") or []

    thread_context = f"Conversation with @{username}:\n" + "\n".join(messages) if messages else f"@{username} replied (preview: {preview})"
    print(f"  [DM reply] Context: {thread_context[:200]}")

    # Human-like delay before replying — kept short so one DM reply doesn't eat a
    # large chunk of the session's time budget.
    delay = random.uniform(8, 15)
    print(f"  [DM reply] They replied — waiting {delay:.0f}s before responding...")
    time.sleep(delay)

    reply_text = ctx.gemini.generate_dm_reply(thread_context=thread_context)
    print(f"  [DM reply] Generated: {reply_text[:80]}...")

    # Find and type in DM input (contenteditable first — works for both popup and full page)
    inp = None
    for sel in ['div[contenteditable="true"]', 'div[aria-label="Message"]']:
        try:
            loc = page.locator(sel).last
            loc.wait_for(state="visible", timeout=4000)
            inp = loc
            break
        except Exception:
            continue

    if inp is None:
        raise RuntimeError("DM input not found for reply")

    inp.click()
    wait_human(0.4, 0.7)
    page.keyboard.type(reply_text, delay=80)
    wait_human(0.5, 1)

    send_btn = page.locator('div[role="button"]:has-text("Send"), button:has-text("Send")').first
    if _visible(send_btn, 2000):
        send_btn.click(force=True)
    else:
        page.keyboard.press("Enter")
    wait_human(1, 2)

    return {"success": True, "replied_in_thread": thread_index, "reply": reply_text}
