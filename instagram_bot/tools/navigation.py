"""Navigation tools — scroll, open posts, hashtags, profiles, inbox via UI clicks."""

import random

from instagram_bot.auth.browser import ensure_instagram_ready
from instagram_bot.perception.page_parser import parse_feed_posts, parse_inbox, parse_page_state, parse_profile_page
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
    return {"hashtag": tag, "posts_found": len(posts), "posts": posts[:8], **parse_page_state(page)}


def open_post(ctx: ToolContext, url: str | None = None, index: int | None = None) -> dict:
    """Open a post by clicking on it in the grid (by index) or navigating to URL."""
    page = ctx.page
    post_url = url

    if index is not None:
        # Click on the grid post visually
        posts = parse_feed_posts(page)
        if posts and index < len(posts):
            post_url = posts[index]["url"]
            # Try clicking the image/grid item first
            try:
                grid_items = page.locator('article a[href*="/p/"], div a[href*="/p/"]')
                if grid_items.count() > index:
                    grid_items.nth(index).click(force=True)
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
