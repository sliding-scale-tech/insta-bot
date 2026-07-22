"""Parse Instagram page DOM into structured JSON for the agent."""

import re
from typing import Any
from urllib.parse import urlparse


_RESERVED_TOP_SEGMENTS = {"explore", "accounts", "direct", "reels", "p", "reel"}


def detect_page_type(url: str) -> str:
    path = urlparse(url).path
    if "/explore/tags/" in path:
        return "hashtag_explore"
    if "/p/" in path or "/reel/" in path:
        return "post"
    if "/reels/" in path:
        return "reels_feed"
    if "/direct/inbox" in path:
        return "inbox"
    if "/direct/" in path:
        return "dm_thread"
    if path in ("", "/"):
        return "home"
    stripped = path.strip("/")
    if stripped == "explore":
        return "explore"
    if stripped == "reels":
        return "reels_feed"
    # Reserved words must be excluded here, or e.g. bare /explore/ falls through
    # and gets misread as a single-segment username ("profile").
    if stripped and "/" not in stripped and stripped not in _RESERVED_TOP_SEGMENTS:
        return "profile"
    if "/explore/" in path:
        return "explore"
    return "unknown"


def parse_page_state(page) -> dict[str, Any]:
    url = page.url
    return {
        "url": url,
        "page_type": detect_page_type(url),
        "title": page.title(),
    }


def parse_feed_posts(page, limit: int = 12) -> list[dict[str, Any]]:
    posts: list[dict[str, Any]] = []
    links = page.locator('a[href*="/p/"], a[href*="/reel/"]')
    count = min(links.count(), limit * 2)

    seen: set[str] = set()
    for i in range(count):
        link = links.nth(i)
        try:
            href = link.get_attribute("href") or ""
            if not href or href in seen:
                continue
            if "/p/" not in href and "/reel/" not in href:
                continue
            # Skip comment/reply URLs like /p/postid/c/commentid/ or /p/postid/r/...
            if "/c/" in href or "/r/" in href:
                continue
            seen.add(href)
            post_url = href if href.startswith("http") else f"https://www.instagram.com{href}"

            # Try to grab caption and author from image alt text
            caption_snippet = ""
            author_hint = ""
            try:
                img = link.locator("img").first
                if img.count():
                    alt = img.get_attribute("alt") or ""
                    # Instagram alt format: "Photo by @username on Month Day, Year: caption"
                    if len(alt) > 5:
                        caption_snippet = alt[:140]
                    if "Photo by" in alt or "photo shared by" in alt.lower():
                        import re as _re
                        m = _re.search(r'(?:Photo by|photo shared by)\s+@?(\w+)', alt, _re.IGNORECASE)
                        if m:
                            author_hint = m.group(1)
            except Exception:
                pass

            posts.append({
                "index": len(posts),
                "url": post_url,
                "media_type": "reel" if "/reel/" in href else "photo",
                "caption_snippet": caption_snippet,
                "author_hint": author_hint,
            })
            if len(posts) >= limit:
                break
        except Exception:
            continue

    return posts


def _extract_post_via_js(page) -> dict[str, str]:
    """Extract author/caption from Instagram post modal or reel page via DOM."""
    try:
        return page.evaluate(
            """() => {
                const isReel = window.location.pathname.includes('/reel/');
                const root = document.querySelector('div[role="dialog"]')
                    || document.querySelector('article')
                    || document.body;
                if (!root) return { author: '', caption: '' };

                // --- Author extraction ---
                let author = '';

                // For reels: the author link is often outside dialog, in a header section
                // or as a standalone link with /username/ pattern
                const searchRoots = isReel
                    ? [document.querySelector('section'), document.querySelector('main'), root]
                    : [root];

                for (const searchRoot of searchRoots) {
                    if (!searchRoot) continue;
                    const headerLinks = searchRoot.querySelectorAll('header a[href^="/"], a[href^="/"][role="link"]');
                    for (const link of headerLinks) {
                        const href = link.getAttribute('href') || '';
                        const match = href.match(/^\\/([^\\/]+)\\/?$/);
                        if (match && !['explore','p','reel','direct','reels','accounts','web'].includes(match[1])) {
                            author = match[1];
                            break;
                        }
                    }
                    if (author) break;
                }

                // Fallback: any profile link visible
                if (!author) {
                    const allLinks = document.querySelectorAll('a[href^="/"]');
                    for (const link of allLinks) {
                        const href = link.getAttribute('href') || '';
                        const match = href.match(/^\\/([^\\/]+)\\/?$/);
                        if (match && !['explore','p','reel','direct','reels','accounts','web',''].includes(match[1])) {
                            const t = (link.textContent || '').trim();
                            if (t && t.length < 40 && t === match[1]) {
                                author = match[1];
                                break;
                            }
                        }
                    }
                }

                // --- Caption extraction ---
                let caption = '';

                // 1. h1 tag (most reliable on post pages)
                const h1 = root.querySelector('h1');
                if (h1) caption = (h1.textContent || '').trim();

                // 2. For reels: look for caption in the reel overlay/description area
                if (isReel && (!caption || caption.length < 20)) {
                    // Reels show caption in a div with dir="auto" near the bottom overlay
                    const reelCaptionCandidates = document.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                    let best = '';
                    for (const el of reelCaptionCandidates) {
                        const text = (el.textContent || '').trim();
                        if (text.length < 20) continue;
                        if (text === author) continue;
                        if (/^(like|comment|share|save|reply|follow|audio|original)$/i.test(text)) continue;
                        if (/^\\d+(\\.\\d+)?[KMB]?\\s*(likes?|comments?|views?)$/i.test(text)) continue;
                        if (text.length > best.length) best = text;
                    }
                    if (best) caption = best;
                }

                // 3. span[dir="auto"] — multiple spans, pick longest meaningful one
                if (!caption || caption.length < 20) {
                    const spans = root.querySelectorAll('span[dir="auto"]');
                    let best = '';
                    for (const span of spans) {
                        const text = (span.textContent || '').trim();
                        if (text.length < 20) continue;
                        if (text === author) continue;
                        if (/^(like|comment|share|save|reply|follow)$/i.test(text)) continue;
                        if (text.length > best.length) best = text;
                    }
                    if (best) caption = best;
                }

                // 4. og:description meta fallback (works for both posts and reels)
                if (!caption) {
                    const meta = document.querySelector('meta[property="og:description"]');
                    if (meta) caption = (meta.getAttribute('content') || '').trim();
                }

                return { author, caption: caption.slice(0, 900) };
            }"""
        ) or {"author": "", "caption": ""}
    except Exception:
        return {"author": "", "caption": ""}


def parse_current_post(page) -> dict[str, Any]:
    state = parse_page_state(page)
    extracted = _extract_post_via_js(page)
    author = extracted.get("author", "")
    caption = extracted.get("caption", "")

    if not author:
        for selector in [
            'header a[href*="/"]:not([href="/"])',
            'article header a',
            'div[role="dialog"] header a',
        ]:
            try:
                loc = page.locator(selector).first
                if loc.is_visible(timeout=1500):
                    author = (loc.inner_text(timeout=1000) or "").strip().split("\n")[0]
                    if author:
                        break
            except Exception:
                continue

    if not caption:
        caption_selectors = [
            'div[role="dialog"] h1',
            'article h1',
            'div[role="dialog"] span[dir="auto"]',
            'article span[dir="auto"]',
        ]
        for selector in caption_selectors:
            try:
                locs = page.locator(selector)
                for j in range(min(locs.count(), 8)):
                    text = (locs.nth(j).inner_text(timeout=800) or "").strip()
                    if not text or len(text) < 15:
                        continue
                    if text == author or text.startswith(author + "\n"):
                        continue
                    if text.lower() in {"like", "comment", "share", "save"}:
                        continue
                    caption = text[:800]
                    break
                if caption:
                    break
            except Exception:
                continue

    return {
        **state,
        "author": author,
        "caption": caption,
        "comments_visible": parse_comments(page, limit=5),
    }


def parse_comments(page, limit: int = 20) -> list[dict[str, Any]]:
    """Parse visible comments. Scrolls comment panel first for reliability."""

    # Load + scroll the comment panel before parsing. Click "load more" repeatedly
    # until no button remains or we hit a safety cap (prevents infinite loops on huge threads).
    for selector in ('div[role="dialog"] ul', 'article ul'):
        try:
            panel = page.locator(selector).first
            if panel.count() == 0:
                continue
            for _ in range(5):  # up to 5 load-more clicks
                try:
                    load_more = page.locator(
                        'button:has-text("View more comments"), '
                        'button:has-text("Load more comments")'
                    ).first
                    if load_more.count() == 0:
                        break
                    load_more.scroll_into_view_if_needed()
                    load_more.click(force=True, timeout=1000)
                    page.wait_for_timeout(800)
                except Exception:
                    break
            panel.evaluate("(el) => { el.scrollTop = el.scrollHeight; }")
            break
        except Exception:
            continue

    comments: list[dict[str, Any]] = []

    # Primary: JS extraction — finds top-level comment rows by profile link + text span
    try:
        raw = page.evaluate(
            """(limit) => {
                const root = document.querySelector('div[role="dialog"]') || document.querySelector('article');
                if (!root) return [];
                const out = [];

                // Top-level comment items: direct children of the comment UL
                // Each has a profile link (href=/username/) and a text span[dir="auto"]
                const commentItems = root.querySelectorAll('ul > li, ul > div');
                for (const item of commentItems) {
                    // Must have a username link
                    const links = item.querySelectorAll('a[href^="/"]');
                    let username = '';
                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const m = href.match(/^\\/([^\\/]+)\\/?$/);
                        if (m && !['explore','p','reel','direct','accounts','web'].includes(m[1])) {
                            username = m[1];
                            break;
                        }
                    }
                    if (!username) continue;

                    // Get comment text — prefer longest span[dir="auto"]
                    let text = '';
                    const spans = item.querySelectorAll('span[dir="auto"]');
                    for (const span of spans) {
                        const t = (span.textContent || '').trim();
                        if (t.length <= 3) continue;
                        if (/^(like|reply|see translation|view replies|\\d+\\s*(like|reply)s?)$/i.test(t)) continue;
                        if (t.length > text.length) text = t;
                    }
                    if (!text || text === username) continue;

                    // Like count if visible
                    let likes = 0;
                    const likeSpan = item.querySelector('button span');
                    if (likeSpan) {
                        const lText = (likeSpan.textContent || '').trim();
                        const lm = lText.match(/^(\\d+)/);
                        if (lm) likes = parseInt(lm[1]);
                    }

                    out.push({ username, text: text.slice(0, 300), likes });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, row in enumerate(raw or []):
            comments.append({
                "index": i,
                "username": row.get("username", ""),
                "text": row.get("text", ""),
                "likes": row.get("likes", 0),
            })
        if comments:
            return comments
    except Exception:
        pass

    # Fallback: Playwright locator approach
    items = page.locator("ul > div, ul ul > li, article ul li")
    item_count = items.count()

    for i in range(min(item_count, limit * 3)):
        item = items.nth(i)
        try:
            if not item.is_visible():
                continue
            text = (item.inner_text(timeout=800) or "").strip()
            if not text or len(text) < 3:
                continue
            if text.lower() in {"reply", "like", "see translation"}:
                continue

            username = ""
            user_link = item.locator('a[href*="/"]').first
            try:
                href = user_link.get_attribute("href") or ""
                match = re.match(r"^/([^/]+)/?$", href)
                if match:
                    username = match.group(1)
            except Exception:
                pass

            comments.append({
                "index": len(comments),
                "username": username,
                "text": text[:300],
                "likes": 0,
            })
            if len(comments) >= limit:
                break
        except Exception:
            continue

    return comments


def parse_replies(page, comment_index: int = 0, limit: int = 10) -> list[dict[str, Any]]:
    """Expand and parse replies (sub-comments) for a specific comment by index."""
    # Try to click "View replies" for the target comment
    try:
        view_replies_btns = page.locator(
            'div[role="button"]:has-text("View replies"), button:has-text("View replies")'
        )
        if view_replies_btns.count() > comment_index:
            btn = view_replies_btns.nth(comment_index)
            btn.scroll_into_view_if_needed()
            btn.click(force=True)
            page.wait_for_timeout(1000)
            # Click again if "Hide replies" is NOT shown yet (sometimes needs two clicks)
            hide = page.locator('div[role="button"]:has-text("Hide replies"), button:has-text("Hide replies")')
            if hide.count() == 0:
                try:
                    btn.click(force=True)
                    page.wait_for_timeout(800)
                except Exception:
                    pass
    except Exception:
        pass

    replies: list[dict[str, Any]] = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const root = document.querySelector('div[role="dialog"]') || document.querySelector('article');
                if (!root) return [];
                // Reply items live in nested ul (ul ul li or ul ul div)
                const replyItems = root.querySelectorAll('ul ul li, ul ul > div');
                const out = [];
                for (const item of replyItems) {
                    const links = item.querySelectorAll('a[href^="/"]');
                    let username = '';
                    for (const link of links) {
                        const href = link.getAttribute('href') || '';
                        const m = href.match(/^\\/([^\\/]+)\\/?$/);
                        if (m && !['explore','p','reel','direct','accounts','web'].includes(m[1])) {
                            username = m[1];
                            break;
                        }
                    }
                    if (!username) continue;
                    let text = '';
                    const spans = item.querySelectorAll('span[dir="auto"]');
                    for (const span of spans) {
                        const t = (span.textContent || '').trim();
                        if (t.length <= 3) continue;
                        if (/^(like|reply|see translation|\\d+\\s*(like|reply)s?)$/i.test(t)) continue;
                        if (t.length > text.length) text = t;
                    }
                    if (!text || text === username) continue;
                    let likes = 0;
                    const likeSpan = item.querySelector('button span');
                    if (likeSpan) {
                        const lm = (likeSpan.textContent || '').match(/^(\\d+)/);
                        if (lm) likes = parseInt(lm[1]);
                    }
                    out.push({ username, text: text.slice(0, 300), likes });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, row in enumerate(raw or []):
            replies.append({
                "index": i,
                "username": row.get("username", ""),
                "text": row.get("text", ""),
                "likes": row.get("likes", 0),
            })
    except Exception:
        pass
    return replies


def parse_explore_grid(page, limit: int = 20) -> list[dict[str, Any]]:
    """Parse the explore grid — returns post URLs and media type."""
    posts: list[dict[str, Any]] = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const seen = new Set();
                const out = [];
                const links = document.querySelectorAll('a[href*="/p/"], a[href*="/reel/"]');
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    if (!href || seen.has(href)) continue;
                    if (href.includes('/c/') || href.includes('/r/')) continue;
                    seen.add(href);
                    const img = a.querySelector('img');
                    const alt = img ? (img.getAttribute('alt') || '') : '';
                    out.push({
                        url: href.startsWith('http') ? href : 'https://www.instagram.com' + href,
                        media_type: href.includes('/reel/') ? 'reel' : 'photo',
                        caption_snippet: alt.slice(0, 140),
                    });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, item in enumerate(raw or []):
            posts.append({"index": i, **item})
    except Exception:
        pass
    return posts


def parse_followers_list(page, limit: int = 20) -> list[dict[str, Any]]:
    """Parse the followers or following modal user list."""
    users: list[dict[str, Any]] = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const out = [];
                const seen = new Set();
                // The modal uses a scrollable list div; entries have profile links
                const modal = document.querySelector('div[role="dialog"]') || document.body;
                const links = modal.querySelectorAll('a[href^="/"]');
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/^\\/([^\\/]+)\\/?$/);
                    if (!m) continue;
                    const uname = m[1];
                    if (['explore','p','reel','direct','reels','accounts','web',''].includes(uname)) continue;
                    if (seen.has(uname)) continue;
                    seen.add(uname);
                    // Try to get display name from nearby text
                    let displayName = '';
                    const parent = a.closest('li') || a.parentElement;
                    if (parent) {
                        const spans = parent.querySelectorAll('span');
                        for (const s of spans) {
                            const t = (s.textContent || '').trim();
                            if (t && t !== uname && t.length < 60 && !/^(Follow|Following|Remove)$/i.test(t)) {
                                displayName = t;
                                break;
                            }
                        }
                    }
                    out.push({ username: uname, display_name: displayName });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, item in enumerate(raw or []):
            users.append({"index": i, **item})
    except Exception:
        pass
    return users


def parse_notifications(page, limit: int = 20) -> list[dict[str, Any]]:
    """Parse the activity/notifications feed."""
    notifications: list[dict[str, Any]] = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const out = [];
                const seen = new Set();
                // Notifications are in a scrollable panel; each item has username + action text
                const items = document.querySelectorAll(
                    'div[role="button"], a[href*="/p/"], a[href*="/reel/"]'
                );
                // More reliable: find all notification rows by looking for items with profile links
                const allLinks = document.querySelectorAll('a[href^="/"]');
                for (const a of allLinks) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/^\\/([^\\/]+)\\/?$/);
                    if (!m) continue;
                    const uname = m[1];
                    if (['explore','p','reel','direct','reels','accounts','web',''].includes(uname)) continue;
                    if (seen.has(uname)) continue;
                    // Get the surrounding text for this notification
                    const row = a.closest('li') || a.closest('div[role="button"]') || a.parentElement;
                    if (!row) continue;
                    const text = (row.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 200);
                    if (text.length < 5) continue;
                    seen.add(uname);
                    out.push({ username: uname, text });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, item in enumerate(raw or []):
            notifications.append({"index": i, **item})
    except Exception:
        pass
    return notifications


def parse_search_results(page, limit: int = 10) -> list[dict[str, Any]]:
    """Parse account search results from the search panel dropdown."""
    results: list[dict[str, Any]] = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const out = [];
                const seen = new Set();
                // Search results appear in a listbox/list panel
                const panel = document.querySelector('div[role="listbox"], div[role="list"], ul[role="listbox"]')
                    || document.querySelector('div[aria-label*="Search"]')
                    || document.body;
                const links = panel.querySelectorAll('a[href^="/"]');
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const m = href.match(/^\\/([^\\/]+)\\/?$/);
                    if (!m) continue;
                    const uname = m[1];
                    if (['explore','p','reel','direct','reels','accounts','web',''].includes(uname)) continue;
                    if (seen.has(uname)) continue;
                    // Skip hashtag results (href contains /explore/tags/)
                    if (href.includes('/explore/tags/') || href.includes('/explore/')) continue;
                    seen.add(uname);
                    // Get display name
                    let displayName = '';
                    const row = a.closest('div[role="option"]') || a.closest('li') || a.parentElement;
                    if (row) {
                        const spans = Array.from(row.querySelectorAll('span'));
                        for (const s of spans) {
                            const t = (s.textContent || '').trim();
                            if (t && t !== uname && t.length < 80 && t.length > 1) {
                                displayName = t;
                                break;
                            }
                        }
                    }
                    out.push({
                        username: uname,
                        display_name: displayName,
                        profile_url: 'https://www.instagram.com' + href,
                    });
                    if (out.length >= limit) break;
                }
                return out;
            }""",
            limit,
        )
        for i, item in enumerate(raw or []):
            results.append({"index": i, **item})
    except Exception:
        pass
    return results


def parse_profile_page(page) -> dict[str, Any]:
    """Parse key info from an Instagram profile page."""
    state = parse_page_state(page)
    try:
        info = page.evaluate(
            """() => {
                // NOTE: avoid Instagram's obfuscated hashed classnames (e.g. "_aa_c",
                // "_ac2a") — they rotate frequently and silently return nothing.
                // Everything below reads structure (header/ul/li) or <meta> tags instead.

                // Username from URL
                const pathMatch = window.location.pathname.match(/^\\/([^\\/]+)\\/?$/);
                const username = pathMatch ? pathMatch[1] : '';

                // Stats (posts, followers, following) — header <ul><li> items
                const stats = [];
                document.querySelectorAll('header ul li').forEach(li => {
                    const t = (li.textContent || '').trim();
                    if (t) stats.push(t);
                });

                // Bio — og:description meta is stable: "N Followers, N Following, N Posts -
                // See Instagram photos and videos from NAME (@username)"
                let bio = '';
                const metaDesc = document.querySelector('meta[property="og:description"]');
                if (metaDesc) bio = (metaDesc.getAttribute('content') || '').trim();

                // Full name — best-effort: first short text node in the header section
                // that isn't the username and isn't a stats/button label
                let fullName = '';
                const headerSection = document.querySelector('header section');
                if (headerSection) {
                    const candidates = Array.from(headerSection.querySelectorAll('span, div'))
                        .map(el => (el.textContent || '').trim())
                        .filter(t => t && t.length < 80 && t !== username && !stats.includes(t));
                    if (candidates.length) fullName = candidates[0];
                }

                // Is following / is followed back
                const allBtns = Array.from(document.querySelectorAll('div[role="button"], button'));
                const isFollowing = allBtns.some(b => (b.textContent || '').trim() === 'Following');

                return { username, bio: bio.slice(0, 200), fullName, stats, isFollowing };
            }"""
        ) or {}
    except Exception:
        info = {}

    return {**state, **info}


def _debug_inbox_dom(page) -> str:
    """Dump inbox DOM structure for debugging."""
    try:
        return page.evaluate("""() => {
            const results = [];
            // Dump all imgs with alt on the page
            document.querySelectorAll('img[alt]').forEach(img => {
                const alt = img.getAttribute('alt') || '';
                if (alt) results.push('IMG:' + alt.slice(0, 60));
            });
            // Dump all a[href*=direct] links
            document.querySelectorAll('a[href*="direct"]').forEach(a => {
                results.push('LINK:' + (a.getAttribute('href') || '').slice(0, 80));
            });
            return results.join('\\n');
        }""")
    except Exception:
        return ""


def parse_inbox(page, limit: int = 10) -> list[dict[str, Any]]:
    """Parse DM inbox thread list."""
    threads = []
    try:
        raw = page.evaluate(
            """(limit) => {
                const out = [];
                const seen = new Set();

                // Helper: extract username + preview from a container element
                function extractThread(el) {
                    const text = (el.textContent || '').trim();
                    const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);
                    if (lines.length < 1) return null;
                    // First non-empty line is the display name / username
                    const username = lines[0];
                    if (!username || username.length > 60) return null;
                    // Skip UI chrome items
                    if (['Messages', 'Requests', 'Search', 'Your note'].includes(username)) return null;
                    const preview = lines.slice(1).join(' ').trim().slice(0, 200);
                    return { username, preview };
                }

                // Strategy 1: anchor links with /direct/t/ (thread-specific URLs)
                const threadLinks = document.querySelectorAll('a[href*="/direct/t/"]');
                for (const a of threadLinks) {
                    const href = a.getAttribute('href') || '';
                    const threadId = (href.split('/direct/t/')[1] || '').replace(/\\/.*/, '');
                    const info = extractThread(a);
                    if (info && !seen.has(info.username)) {
                        seen.add(info.username);
                        out.push({ ...info, threadId, href });
                        if (out.length >= limit) return out;
                    }
                }
                if (out.length > 0) return out;

                // Strategy 2: Instagram uses img[alt="user-profile-picture"] for thread avatars
                // Walk up from each avatar to find the containing thread row, then extract
                // name and preview from the first two significant child text nodes
                const avatarImgs = document.querySelectorAll('img[alt="user-profile-picture"]');
                for (const img of avatarImgs) {
                    let el = img.parentElement;
                    for (let i = 0; i < 10 && el; i++) {
                        const txt = (el.textContent || '').trim();
                        if (txt.length < 3 || txt.length > 800) { el = el.parentElement; continue; }
                        // Find all leaf-level text spans/divs within this container
                        const leafTexts = [];
                        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
                        let node;
                        while ((node = walker.nextNode())) {
                            const t = (node.textContent || '').trim();
                            if (t.length > 1 && !/^[·•\\s]+$/.test(t)) leafTexts.push(t);
                        }
                        if (leafTexts.length >= 1) {
                            // First significant text = display name, rest = preview
                            // Filter out timestamp tokens (e.g. "27m", "1h", "2d")
                            const nonTimestamp = leafTexts.filter(t => !/^\\d+[smhd]$/.test(t));
                            const username = nonTimestamp[0] || '';
                            if (username && username.length < 80 &&
                                !['Messages','Requests','Search',"What's new",'Your note'].includes(username) &&
                                !seen.has(username)) {
                                const preview = nonTimestamp.slice(1).join(' ').trim().slice(0, 200);
                                seen.add(username);
                                out.push({ username, preview, threadId: '', href: '', domIndex: out.length });
                                if (out.length >= limit) return out;
                                break;
                            }
                        }
                        el = el.parentElement;
                    }
                }
                if (out.length > 0) return out;

                // Strategy 3: any listitem / listbox option
                const items = document.querySelectorAll('div[role="listitem"], li[role="option"], li');
                for (const item of items) {
                    const info = extractThread(item);
                    if (!info || seen.has(info.username)) continue;
                    seen.add(info.username);
                    out.push({ ...info, threadId: '', href: '' });
                    if (out.length >= limit) return out;
                }
                if (out.length > 0) return out;

                // Strategy 4: find the Messages section header and grab siblings
                const headers = Array.from(document.querySelectorAll('span, h1, h2, h3, div'))
                    .filter(el => el.textContent.trim() === 'Messages');
                for (const hdr of headers) {
                    let sibling = hdr.parentElement && hdr.parentElement.nextElementSibling;
                    let checked = 0;
                    while (sibling && checked < 20) {
                        const info = extractThread(sibling);
                        if (info && !seen.has(info.username)) {
                            seen.add(info.username);
                            out.push({ ...info, threadId: '', href: '' });
                            if (out.length >= limit) return out;
                        }
                        sibling = sibling.nextElementSibling;
                        checked++;
                    }
                }

                return out;
            }""",
            limit,
        )
        for i, t in enumerate(raw or []):
            threads.append({"index": i, **t})
    except Exception:
        pass
    return threads
