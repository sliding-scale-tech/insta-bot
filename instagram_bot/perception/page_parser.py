"""Parse Instagram page DOM into structured JSON for the agent."""

import re
from typing import Any
from urllib.parse import urlparse


def detect_page_type(url: str) -> str:
    path = urlparse(url).path
    if "/explore/tags/" in path:
        return "hashtag_explore"
    if "/p/" in path or "/reel/" in path:
        return "post"
    if "/direct/inbox" in path:
        return "inbox"
    if "/direct/" in path:
        return "dm_thread"
    stripped = path.strip("/")
    if stripped and "/" not in stripped:
        return "profile"
    if path in ("", "/"):
        return "home"
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
    """Extract author/caption from Instagram post modal via DOM."""
    try:
        return page.evaluate(
            """() => {
                const root = document.querySelector('div[role="dialog"]')
                    || document.querySelector('article')
                    || document.body;
                if (!root) return { author: '', caption: '' };

                // --- Author extraction ---
                let author = '';
                // First: try to get username from header link href /username/
                const headerLinks = root.querySelectorAll('header a[href^="/"]');
                for (const link of headerLinks) {
                    const href = link.getAttribute('href') || '';
                    const match = href.match(/^\\/([^\\/]+)\\/?$/);
                    if (match && !['explore','p','reel','direct'].includes(match[1])) {
                        author = match[1];
                        break;
                    }
                }
                // Fallback: header link text
                if (!author) {
                    const authorLink = root.querySelector('header a[href^="/"]:not([href="/"])');
                    if (authorLink) {
                        const t = (authorLink.textContent || '').trim().split('\\n')[0];
                        if (t && t.length < 40) author = t;
                    }
                }

                // --- Caption extraction ---
                let caption = '';

                // 1. h1 tag (most reliable on post pages)
                const h1 = root.querySelector('h1');
                if (h1) caption = (h1.textContent || '').trim();

                // 2. span[dir="auto"] — multiple spans, pick longest meaningful one
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

                // 3. og:description meta fallback
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

    # Scroll comment panel before parsing
    for selector in ('div[role="dialog"] ul', 'article ul'):
        try:
            panel = page.locator(selector).first
            if panel.count() and panel.is_visible(timeout=1000):
                panel.evaluate("(el) => { el.scrollTop = 0; }")
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


def parse_profile_page(page) -> dict[str, Any]:
    """Parse key info from an Instagram profile page."""
    state = parse_page_state(page)
    try:
        info = page.evaluate(
            """() => {
                const getText = (sel) => {
                    const el = document.querySelector(sel);
                    return el ? (el.textContent || '').trim() : '';
                };

                // Username from URL
                const pathMatch = window.location.pathname.match(/^\\/([^\\/]+)\\/?$/);
                const username = pathMatch ? pathMatch[1] : '';

                // Bio
                const bio = getText('div._aa_c, header section div:last-child span, [data-testid="user-bio"]') || '';

                // Stats (posts, followers, following) — look for header list items
                const stats = [];
                document.querySelectorAll('header ul li span, header li span._ac2a').forEach(el => {
                    const t = (el.textContent || '').trim();
                    if (t) stats.push(t);
                });

                // Full name
                const fullName = getText('header section h1, span._aade');

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
