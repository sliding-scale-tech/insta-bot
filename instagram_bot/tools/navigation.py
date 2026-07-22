"""Navigation tools — scroll, open posts, hashtags, profiles, inbox via UI clicks."""

import random
from urllib.parse import urlparse

from instagram_bot.auth.browser import ensure_instagram_ready
from instagram_bot.perception.page_parser import (
    parse_explore_grid,
    parse_feed_posts,
    parse_followers_list,
    parse_inbox,
    parse_notifications,
    parse_page_state,
    parse_profile_page,
    parse_search_results,
)
from instagram_bot.tools.context import ToolContext
from instagram_bot.tools.human import wait_human


def _click_sidebar_icon(page, aria_labels: list[str], timeout: int = 4000) -> bool:
    """Click a sidebar nav icon by its SVG aria-label. Returns True if clicked."""
    for label in aria_labels:
        for sel in [
            f'svg[aria-label="{label}"]',
            f'a[aria-label="{label}"]',
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=timeout):
                    # Click the closest parent link/button
                    parent = page.locator(f'{sel}').locator("xpath=ancestor::a[1] | ancestor::button[1]").first
                    try:
                        parent.click(force=True, timeout=3000)
                    except Exception:
                        el.click(force=True, timeout=3000)
                    return True
            except Exception:
                continue
    return False


def scroll_down(ctx: ToolContext, amount: int | None = None) -> dict:
    page = ctx.page
    pixels = amount or random.randint(400, 900)
    page.mouse.wheel(0, pixels)
    wait_human(1.5, 3)
    return {"scrolled_pixels": pixels, **parse_page_state(page)}


def _search_for_hashtag(page, tag: str) -> bool:
    """
    Use Instagram's sidebar search to navigate to a hashtag.
    The search input is hidden inside a panel — must click the Search sidebar icon first.
    Returns True if successfully navigated to the hashtag page.
    """
    print(f"  [search] Starting UI search on page: {page.url[:60]}")

    # Step 1: Click the Search icon in the sidebar to open the search panel
    search_icon_selectors = [
        'svg[aria-label="Search"]',
        'a[aria-label="Search"]',
        'span[aria-label="Search"]',
    ]
    icon_clicked = False
    for sel in search_icon_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                print(f"  [search] Clicking search icon: {sel}")
                # Click the ancestor link/button for best results
                try:
                    ancestor = page.locator(sel).locator("xpath=ancestor::a[1] | ancestor::button[1]").first
                    ancestor.click(force=True, timeout=3000)
                except Exception:
                    el.click(force=True, timeout=3000)
                icon_clicked = True
                wait_human(0.8, 1.3)
                break
        except Exception:
            continue

    if not icon_clicked:
        print("  [search] Could not find search icon in sidebar")
        return False

    # Step 2: Wait for the search input to appear in the slide-out panel
    try:
        inp = page.locator('input[aria-label="Search input"]')
        inp.wait_for(state="visible", timeout=6000)
        print("  [search] Search panel open, input visible — focusing input...")
        wait_human(0.5, 0.8)  # let the panel animation finish
        try:
            inp.click(force=True, timeout=3000)
        except Exception:
            inp.focus()  # fallback: focus without click
        wait_human(0.3, 0.5)
    except Exception as e:
        print(f"  [search] Search input did not appear after icon click: {e}")
        return False

    # Step 3: Type the hashtag
    try:
        inp.fill("")
        wait_human(0.2, 0.4)
        inp.type(f"#{tag}", delay=120)
        print(f"  [search] Typed '#{tag}', waiting for suggestions...")
        wait_human(2.5, 3.5)
    except Exception as e:
        print(f"  [search] Typing failed: {e}")
        return False

    # Step 4: Click the hashtag suggestion in the dropdown
    for sel in [
        f'a[href="/explore/tags/{tag}/"]',
        f'a[href*="/explore/tags/{tag}"]',
        f'span:text-is("#{tag}")',
        f'a:has-text("#{tag}")',
    ]:
        try:
            result = page.locator(sel).first
            if result.is_visible(timeout=4000):
                print(f"  [search] Clicking result: {sel}")
                result.click(force=True)
                wait_human(2, 3)
                current = page.url.lower()
                print(f"  [search] After click, URL: {current[:60]}")
                if "tags" in current or tag.lower() in current or "explore" in current:
                    return True
        except Exception:
            continue

    print("  [search] No hashtag result found in dropdown, falling back to URL")
    return False


def open_hashtag(ctx: ToolContext, hashtag: str) -> dict:
    """Navigate to a hashtag page and land on Recent posts."""
    tag = hashtag.lstrip("#")
    page = ctx.page

    # Try human-like UI search first
    _search_for_hashtag(page, tag)

    # If Instagram redirected to the keyword search page instead of the tags page,
    # navigate directly to the proper hashtag page which has a Recent section
    if "/explore/tags/" not in page.url:
        print(f"  [hashtag] Redirected to search page — navigating to /explore/tags/{tag}/")
        page.goto(
            f"https://www.instagram.com/explore/tags/{tag}/",
            wait_until="domcontentloaded",
        )
        wait_human(1.5, 2.5)

    ensure_instagram_ready(page)
    wait_human(1, 1.5)

    # Try clicking the "Recent" tab to get freshest posts
    for sel in [
        'a:has-text("Recent")',
        'span:has-text("Recent")',
        'div[role="tab"]:has-text("Recent")',
    ]:
        try:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=2000):
                print(f"  [hashtag] Clicking Recent tab: {sel}")
                btn.click(force=True)
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue
    else:
        # No Recent tab found — scroll past Top Posts section
        print("  [hashtag] No Recent tab — scrolling past Top Posts")
        for _ in range(random.randint(3, 4)):
            page.mouse.wheel(0, random.randint(700, 1100))
            wait_human(0.8, 1.4)

    posts = parse_feed_posts(page)
    return {"success": True, "hashtag": tag, "posts_found": len(posts), "posts": posts[:8], **parse_page_state(page)}


def open_post(ctx: ToolContext, url: str | None = None, index: int | None = None) -> dict:
    """Open a post by clicking on it in the grid (by index) or navigating to URL."""
    page = ctx.page
    post_url = url

    if index is not None:
        # Click on the grid post visually
        posts = parse_feed_posts(page)
        if posts and index < len(posts):
            post_url = posts[index]["url"]
            # Click by href, not by positional nth(index) — parse_feed_posts dedupes
            # hrefs and skips /c/ and /r/ links, but a plain 'a[href*="/p/"]' locator
            # does not, so grid_items.nth(index) can point at a different post than
            # posts[index] (e.g. when a post has both an image anchor and a caption
            # anchor). Clicking the exact href guarantees we open the right one.
            try:
                href_path = urlparse(post_url).path
                target = page.locator(f'a[href="{href_path}"]').first
                if target.count():
                    target.click(force=True)
                    wait_human(2, 4)
                    return {"opened_url": page.url, "success": True, **parse_page_state(page)}
            except Exception:
                pass

    if post_url:
        if not post_url.startswith("http"):
            post_url = f"https://www.instagram.com{post_url}"
        page.goto(post_url, wait_until="domcontentloaded")
        wait_human(2, 4)
        return {"opened_url": post_url, "success": True, **parse_page_state(page)}

    raise RuntimeError("Need either url or index to open a post")


def go_home(ctx: ToolContext) -> dict:
    """Go to Instagram home by clicking the Home icon or link."""
    page = ctx.page
    # Try clicking the Home nav link directly (most reliable)
    home_selectors = [
        'a[href="/"]',
        'svg[aria-label="Home"]',
        'a[aria-label="Home"]',
    ]
    clicked = False
    for sel in home_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(force=True, timeout=3000)
                clicked = True
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue
    if not clicked:
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
    ensure_instagram_ready(page)
    wait_human(1.5, 2.5)
    return parse_page_state(page)


def go_back(ctx: ToolContext) -> dict:
    page = ctx.page
    try:
        page.go_back(wait_until="domcontentloaded")
    except Exception:
        try:
            close = page.locator('svg[aria-label="Close"]').first
            if close.is_visible(timeout=1500):
                close.click(force=True)
        except Exception:
            pass
    wait_human(1.5, 2.5)
    return parse_page_state(page)


def open_profile(ctx: ToolContext, username: str) -> dict:
    """Navigate to a user's profile — click their link on page, or navigate via URL."""
    page = ctx.page
    username = username.lstrip("@").strip()

    # Step 1: Try clicking a profile link already visible on the page
    for link_sel in [
        f'a[href="/{username}/"]',
        f'header a[href*="/{username}"]',
        f'article a[href*="/{username}"]',
    ]:
        try:
            el = page.locator(link_sel).first
            if el.is_visible(timeout=1500):
                el.click(force=True)
                wait_human(2, 3)
                return parse_profile_page(page)
        except Exception:
            continue

    # Step 2: Use URL navigation (reliable and natural for profiles)
    page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
    # Wait for profile content to render (bio, follow button, posts)
    try:
        page.locator('header section, div[role="button"]:has-text("Follow"), div[role="button"]:has-text("Message")').first.wait_for(state="visible", timeout=6000)
    except Exception:
        pass
    wait_human(1.5, 2.5)
    return parse_profile_page(page)


def open_inbox(ctx: ToolContext) -> dict:
    """Navigate to the DM inbox by clicking the messenger/DM icon."""
    page = ctx.page

    dm_selectors = [
        'a[href="/direct/inbox/"]',
        'svg[aria-label="Messenger"]',
        'svg[aria-label="Direct messaging"]',
        'svg[aria-label="Direct"]',
        'a[aria-label="Direct messaging"]',
    ]
    clicked = False
    for sel in dm_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                el.click(force=True, timeout=3000)
                clicked = True
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue
    if not clicked:
        page.goto("https://www.instagram.com/direct/inbox/", wait_until="domcontentloaded")

    # Wait for inbox content — try multiple signals since Instagram layout varies
    for wait_sel in [
        'a[href*="/direct/t/"]',
        'div[tabindex="0"] img[alt]',
        'div[role="button"] img[alt]',
        'span:has-text("Messages")',
    ]:
        try:
            page.locator(wait_sel).first.wait_for(state="visible", timeout=5000)
            break
        except Exception:
            continue
    wait_human(1, 2)
    from instagram_bot.perception.page_parser import _debug_inbox_dom
    dom_debug = _debug_inbox_dom(page)
    if dom_debug:
        print(f"  [inbox DOM sample]\n{dom_debug[:800]}")
    threads = parse_inbox(page, limit=10)
    return {"threads": threads, "count": len(threads), **parse_page_state(page)}


def search_account(ctx: ToolContext, query: str) -> dict:
    """Search Instagram for a person/username via the search UI."""
    page = ctx.page

    # Make sure we're on a page with the sidebar (home/hashtag/profile)
    # Reels full-screen and direct/DM pages hide the sidebar nav
    if "/reel/" in page.url or "/reels/" in page.url or "/direct/" in page.url:
        page.goto("https://www.instagram.com/", wait_until="domcontentloaded")
        wait_human(1.5, 2.5)

    # Click the Search icon in the sidebar
    search_icon_selectors = [
        'svg[aria-label="Search"]',
        'a[aria-label="Search"]',
        'span[aria-label="Search"]',
    ]
    icon_clicked = False
    for sel in search_icon_selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2000):
                try:
                    ancestor = page.locator(sel).locator("xpath=ancestor::a[1] | ancestor::button[1]").first
                    ancestor.click(force=True, timeout=3000)
                except Exception:
                    el.click(force=True, timeout=3000)
                icon_clicked = True
                wait_human(0.8, 1.3)
                break
        except Exception:
            continue

    if not icon_clicked:
        return {"success": False, "reason": "Search icon not found", "results": []}

    # Wait for search input
    try:
        inp = page.locator('input[aria-label="Search input"]')
        inp.wait_for(state="visible", timeout=6000)
        wait_human(0.4, 0.7)
        try:
            inp.click(force=True, timeout=3000)
        except Exception:
            inp.focus()
        wait_human(0.3, 0.5)
    except Exception as e:
        return {"success": False, "reason": f"Search input not visible: {e}", "results": []}

    # Type the query (no # prefix — this is account search)
    try:
        inp.fill("")
        wait_human(0.2, 0.3)
        inp.type(query, delay=110)
        wait_human(2, 3)
    except Exception as e:
        return {"success": False, "reason": f"Typing failed: {e}", "results": []}

    results = parse_search_results(page, limit=10)
    return {"success": True, "query": query, "results": results, "count": len(results)}


def get_followers(ctx: ToolContext, username: str, limit: int = 20) -> dict:
    """Open the followers modal for a user and return their follower list."""
    page = ctx.page
    username = username.lstrip("@").strip()

    # Navigate to profile first if needed
    if f"/{username}" not in page.url:
        page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
        wait_human(2, 3)

    # Click the "followers" count link
    for sel in [
        f'a[href="/{username}/followers/"]',
        'a[href*="/followers/"]',
        'span:has-text("followers")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click(force=True)
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue
    else:
        # Direct navigation fallback
        page.goto(f"https://www.instagram.com/{username}/followers/", wait_until="domcontentloaded")
        wait_human(2, 3)

    # Wait for modal content
    try:
        page.locator('div[role="dialog"]').first.wait_for(state="visible", timeout=5000)
    except Exception:
        pass

    # Scroll the modal to load more users
    try:
        modal = page.locator('div[role="dialog"]').first
        for _ in range(3):
            modal.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
            wait_human(0.8, 1.2)
    except Exception:
        pass

    users = parse_followers_list(page, limit=limit)
    return {"username": username, "type": "followers", "users": users, "count": len(users), **parse_page_state(page)}


def get_following(ctx: ToolContext, username: str, limit: int = 20) -> dict:
    """Open the following modal for a user and return who they follow."""
    page = ctx.page
    username = username.lstrip("@").strip()

    if f"/{username}" not in page.url:
        page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
        wait_human(2, 3)

    for sel in [
        f'a[href="/{username}/following/"]',
        'a[href*="/following/"]',
        'span:has-text("following")',
    ]:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                el.click(force=True)
                wait_human(1.5, 2.5)
                break
        except Exception:
            continue
    else:
        page.goto(f"https://www.instagram.com/{username}/following/", wait_until="domcontentloaded")
        wait_human(2, 3)

    try:
        page.locator('div[role="dialog"]').first.wait_for(state="visible", timeout=5000)
    except Exception:
        pass

    try:
        modal = page.locator('div[role="dialog"]').first
        for _ in range(3):
            modal.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
            wait_human(0.8, 1.2)
    except Exception:
        pass

    users = parse_followers_list(page, limit=limit)
    return {"username": username, "type": "following", "users": users, "count": len(users), **parse_page_state(page)}


def browse_explore(ctx: ToolContext) -> dict:
    """Navigate to the Instagram Explore page and return the post grid."""
    page = ctx.page

    # Always navigate directly — sidebar Explore icon is unreliable when sidebars are hidden
    page.goto("https://www.instagram.com/explore/", wait_until="domcontentloaded")
    ensure_instagram_ready(page)
    wait_human(1.5, 2.5)

    # Wait for at least one post link to appear (Explore grid is lazily rendered)
    try:
        page.locator('a[href*="/p/"], a[href*="/reel/"]').first.wait_for(state="visible", timeout=8000)
    except Exception:
        pass

    # Scroll to trigger lazy loading if grid is empty
    for _ in range(2):
        page.mouse.wheel(0, 500)
        wait_human(0.8, 1.2)

    posts = parse_explore_grid(page, limit=20)
    return {"success": True, "posts": posts, "count": len(posts), **parse_page_state(page)}


def browse_reels_feed(ctx: ToolContext) -> dict:
    """Navigate to the Instagram Reels feed and return visible reels.

    Instagram's /reels/ page is a full-screen video player (not a grid). We parse
    the current reel being shown plus any reel links visible in the sidebar/overlay.
    """
    page = ctx.page

    page.goto("https://www.instagram.com/reels/", wait_until="domcontentloaded")
    ensure_instagram_ready(page)
    wait_human(2, 3)

    # The reels page immediately plays a reel — collect reel URLs from the current URL
    # and any /reel/ links rendered on the page (sidebar suggestions)
    reels = []
    seen: set = set()

    # Current reel from URL — Instagram uses /reels/<id>/ (plural) for the feed player
    current_url = page.url
    if "/reel/" in current_url or "/reels/" in current_url:
        reels.append({"index": 0, "url": current_url, "media_type": "reel", "caption_snippet": "", "author_hint": ""})
        seen.add(current_url)

    # Additional reel links on the page (suggestions / carousel)
    try:
        reel_links = page.evaluate("""() => {
            const seen = new Set();
            const out = [];
            document.querySelectorAll('a[href*="/reel/"]').forEach(a => {
                const href = a.getAttribute('href') || '';
                const url = href.startsWith('http') ? href : 'https://www.instagram.com' + href;
                if (!seen.has(url) && !href.includes('/c/') && !href.includes('/r/')) {
                    seen.add(url);
                    const img = a.querySelector('img');
                    const alt = img ? (img.getAttribute('alt') || '') : '';
                    out.push({ url, media_type: 'reel', caption_snippet: alt.slice(0, 140), author_hint: '' });
                }
            });
            return out;
        }""")
        for item in (reel_links or []):
            if item["url"] not in seen:
                item["index"] = len(reels)
                reels.append(item)
                seen.add(item["url"])
    except Exception:
        pass

    return {"success": True, "reels": reels, "count": len(reels), **parse_page_state(page)}


def read_notifications(ctx: ToolContext) -> dict:
    """Open the notifications/activity tab and return recent activity."""
    page = ctx.page

    # Click the heart/notifications icon in the sidebar
    clicked = _click_sidebar_icon(page, ["Notifications", "Activity", "Heart"])
    if not clicked:
        # Try alternate approach: look for notification bell
        for sel in [
            'svg[aria-label="Notifications"]',
            'a[href*="/accounts/activity/"]',
        ]:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click(force=True)
                    clicked = True
                    wait_human(1, 2)
                    break
            except Exception:
                continue

    if not clicked:
        page.goto("https://www.instagram.com/accounts/activity/", wait_until="domcontentloaded")

    wait_human(1.5, 2.5)
    notifications = parse_notifications(page, limit=20)
    return {"success": True, "notifications": notifications, "count": len(notifications), **parse_page_state(page)}


def open_thread(ctx: ToolContext, username: str) -> dict:
    """Open a DM conversation with a specific user."""
    page = ctx.page
    username = username.lstrip("@").strip()

    # Go to inbox first if not already there
    if "/direct/" not in page.url:
        open_inbox(ctx)

    # Try clicking the conversation if it exists in inbox
    items = page.locator('div[role="listitem"]')
    for i in range(min(items.count(), 15)):
        item = items.nth(i)
        try:
            text = (item.inner_text(timeout=400) or "").lower()
            if username.lower() in text:
                item.click(force=True)
                wait_human(1.5, 2.5)
                return {"opened_thread_with": username, **parse_page_state(page)}
        except Exception:
            continue

    # Compose new message
    try:
        compose = page.locator(
            'svg[aria-label="New message"], button[aria-label="New message"], '
            'div[role="button"]:has-text("New message")'
        ).first
        if compose.is_visible(timeout=3000):
            compose.click(force=True)
            wait_human(1, 2)

            search = page.locator('input[name="queryBox"], input[placeholder*="Search"]').first
            if search.is_visible(timeout=3000):
                search.fill(username)
                wait_human(1.5, 2.5)

                result = page.locator(
                    f'div[role="button"]:has-text("{username}"), span:has-text("{username}")'
                ).first
                if result.is_visible(timeout=3000):
                    result.click(force=True)
                    wait_human(0.8, 1.5)

                next_btn = page.locator('div[role="button"]:has-text("Next"), button:has-text("Next")').first
                if next_btn.is_visible(timeout=2000):
                    next_btn.click(force=True)
                    wait_human(1, 2)
    except Exception:
        pass

    return {"opened_thread_with": username, **parse_page_state(page)}
