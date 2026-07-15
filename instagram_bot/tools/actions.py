"""Action tools — comment, reply, like, follow, DMs, skip, dismiss popups."""

import random
import time

from instagram_bot.auth.browser import (
    dismiss_notifications_popup,
    dismiss_popups,
)
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.human import wait_human


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
        if dialog.is_visible(timeout=1000):
            close_btn = dialog.locator('svg[aria-label="Close"]').first
            if close_btn.is_visible(timeout=1000):
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

    post_url = page.url
    ctx.memory.setdefault("commented_posts", []).append(post_url)
    return {"success": True, "post_url": post_url, "comment": text}


def reply_to_comment(
    ctx: ToolContext,
    text: str,
    username: str | None = None,
    comment_index: int | None = None,
) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)

    reply_buttons = page.locator(
        'div[role="button"]:has-text("Reply"), span:has-text("Reply")'
    )
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
    if already_liked.is_visible(timeout=1000):
        return {"success": True, "liked": "post", "already_liked": True, "post_url": page.url}

    icon = page.locator('svg[aria-label="Like"]').first
    icon.wait_for(state="visible", timeout=8000)
    parent = icon.locator("xpath=ancestor::*[@role='button'][1]")
    if parent.count():
        parent.first.click(force=True)
    else:
        icon.click(force=True)
    wait_human(1, 2)

    key = f"post::{page.url}"
    ctx.memory.setdefault("liked_items", []).append(key)
    return {"success": True, "liked": "post", "post_url": page.url}


def like_comment(ctx: ToolContext, comment_index: int = 0) -> dict:
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.5, 1)

    # Scroll comment panel so likes are reachable
    for selector in ('div[role="dialog"] ul', 'article ul'):
        try:
            panel = page.locator(selector).first
            if panel.count() and panel.is_visible(timeout=1500):
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

    key = f"comment::{page.url}::{idx}"
    ctx.memory.setdefault("liked_items", []).append(key)
    return {"success": True, "liked": "comment", "comment_index": idx, "post_url": page.url}


def like_reply(ctx: ToolContext, comment_index: int = 0, reply_index: int = 0) -> dict:
    """Like a reply (sub-comment) on the open post."""
    page = ctx.page
    dismiss_all_popups(ctx)
    wait_human(0.3, 0.7)

    # Expand replies on the target comment first
    try:
        view_replies = page.locator(
            'span:has-text("View replies"), button:has-text("View replies"), '
            'div:has-text("View replies")'
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

    key = f"reply::{page.url}::{comment_index}::{reply_index}"
    ctx.memory.setdefault("liked_items", []).append(key)
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

    comments_liked: list[int] = []
    for idx in (0, 2, 1):
        if len(comments_liked) >= 2:
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
    text = ctx.gemini.generate_helpful_comment(caption, author, comments)
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
    if following_btn.is_visible(timeout=2000):
        return {"success": True, "already_following": True, "username": username}

    follow_btn = page.locator(
        'div[role="button"]:has-text("Follow"):not(:has-text("Following")), '
        'button:has-text("Follow"):not(:has-text("Following"))'
    ).first
    if not follow_btn.is_visible(timeout=5000):
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
    if not following_btn.is_visible(timeout=4000):
        return {"success": False, "reason": "Not following this user", "username": username}

    following_btn.click(force=True)
    wait_human(1, 1.5)

    # Confirm unfollow in dialog
    unfollow_confirm = page.locator(
        'button:has-text("Unfollow"), div[role="button"]:has-text("Unfollow")'
    ).first
    if unfollow_confirm.is_visible(timeout=3000):
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
            if btn.is_visible(timeout=3000):
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
    if send_btn.is_visible(timeout=2000):
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
    if send_btn.is_visible(timeout=2000):
        send_btn.click(force=True)
    else:
        page.keyboard.press("Enter")
    wait_human(1, 2)
    return {"success": True, "replied_in_thread": thread_index, "text": text}


def ai_reply_to_dm(ctx: ToolContext, thread_index: int = 0) -> dict:
    """
    Check a DM thread — only reply if THEY sent the last message (they replied to us).
    Detects by checking if inbox preview starts with 'You:' (= we sent last).
    Waits 30-60s like a human, then sends a short warm-lead reply in English.
    """
    from instagram_bot.perception.page_parser import parse_inbox
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
            if link.is_visible(timeout=2000):
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

    # Human-like delay before replying (30-60 seconds)
    delay = random.uniform(30, 60)
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
    if send_btn.is_visible(timeout=2000):
        send_btn.click(force=True)
    else:
        page.keyboard.press("Enter")
    wait_human(1, 2)

    return {"success": True, "replied_in_thread": thread_index, "reply": reply_text}
