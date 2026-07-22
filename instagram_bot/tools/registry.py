"""Tool registry — schemas for Gemini function calling + Python dispatch."""

from typing import Any, Callable

from instagram_bot.tools import actions, navigation, perception
from instagram_bot.tools.context import ToolContext

ToolFn = Callable[[ToolContext, dict[str, Any]], dict]

TOOLS: dict[str, dict[str, Any]] = {
    # ── Perception ──────────────────────────────────────────────────────────
    "observe_page_state": {
        "fn": lambda ctx, _: perception.observe_page_state(ctx),
        "description": "Get current URL and page type (home, explore, post, profile, inbox, etc.)",
        "parameters": {"type": "object", "properties": {}},
    },
    "observe_feed": {
        "fn": lambda ctx, a: perception.observe_feed(ctx, limit=a.get("limit", 8)),
        "description": "List visible posts on hashtag grid or home feed with index, URL, and caption snippets",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max posts to return"},
            },
        },
    },
    "observe_current_post": {
        "fn": lambda ctx, _: perception.observe_current_post(ctx),
        "description": "Read the open post: author, caption, and top visible comments",
        "parameters": {"type": "object", "properties": {}},
    },
    "observe_comments": {
        "fn": lambda ctx, a: perception.observe_comments(ctx, limit=a.get("limit", 15)),
        "description": "Read visible comments on the open post (index, username, text, likes)",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
            },
        },
    },
    "observe_replies": {
        "fn": lambda ctx, a: perception.observe_replies(ctx, comment_index=a.get("comment_index", 0), limit=a.get("limit", 10)),
        "description": "Expand and read replies (sub-comments) on a specific comment by index. Call before like_reply or ai_reply_to_comment so you can see reply content.",
        "parameters": {
            "type": "object",
            "properties": {
                "comment_index": {"type": "integer", "description": "Parent comment index (from observe_comments)"},
                "limit": {"type": "integer", "description": "Max replies to return"},
            },
        },
    },
    "evaluate_current_post": {
        "fn": lambda ctx, _: perception.evaluate_current_post(ctx),
        "description": "AI check: should I comment on this post? Call after observe_current_post, before engaging. Returns should_comment/confidence/reason.",
        "parameters": {"type": "object", "properties": {}},
    },

    # ── Navigation ──────────────────────────────────────────────────────────
    "scroll_down": {
        "fn": lambda ctx, a: navigation.scroll_down(ctx, amount=a.get("amount")),
        "description": "Scroll down the page naturally (like a human)",
        "parameters": {
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Scroll pixels (omit for random 400-900)"},
            },
        },
    },
    "open_hashtag": {
        "fn": lambda ctx, a: navigation.open_hashtag(ctx, hashtag=a["hashtag"]),
        "description": "Navigate to a hashtag explore page (e.g. 'realestate')",
        "parameters": {
            "type": "object",
            "properties": {
                "hashtag": {"type": "string", "description": "Hashtag without # symbol"},
            },
            "required": ["hashtag"],
        },
    },
    "open_post": {
        "fn": lambda ctx, a: navigation.open_post(ctx, url=a.get("url"), index=a.get("index")),
        "description": "Open a post by URL or grid index number",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full post URL"},
                "index": {"type": "integer", "description": "Grid position (0=first)"},
            },
        },
    },
    "go_home": {
        "fn": lambda ctx, _: navigation.go_home(ctx),
        "description": "Go to Instagram home feed",
        "parameters": {"type": "object", "properties": {}},
    },
    "go_back": {
        "fn": lambda ctx, _: navigation.go_back(ctx),
        "description": "Browser back or close modal",
        "parameters": {"type": "object", "properties": {}},
    },
    "open_profile": {
        "fn": lambda ctx, a: navigation.open_profile(ctx, username=a["username"]),
        "description": "Open a user's Instagram profile page",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Instagram username (without @)"},
            },
            "required": ["username"],
        },
    },
    "open_inbox": {
        "fn": lambda ctx, _: navigation.open_inbox(ctx),
        "description": "Open the DM inbox and list recent conversations",
        "parameters": {"type": "object", "properties": {}},
    },
    "search_account": {
        "fn": lambda ctx, a: navigation.search_account(ctx, query=a["query"]),
        "description": "Search Instagram for a person or username. Returns matching accounts with username and profile URL.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Name or username to search for"},
            },
            "required": ["query"],
        },
    },
    "get_followers": {
        "fn": lambda ctx, a: navigation.get_followers(ctx, username=a["username"], limit=a.get("limit", 20)),
        "description": "Open a user's followers list and return their follower accounts",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Instagram username (without @)"},
                "limit": {"type": "integer", "description": "Max followers to return"},
            },
            "required": ["username"],
        },
    },
    "get_following": {
        "fn": lambda ctx, a: navigation.get_following(ctx, username=a["username"], limit=a.get("limit", 20)),
        "description": "Open a user's following list and return accounts they follow",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Instagram username (without @)"},
                "limit": {"type": "integer", "description": "Max following to return"},
            },
            "required": ["username"],
        },
    },
    "browse_explore": {
        "fn": lambda ctx, _: navigation.browse_explore(ctx),
        "description": "Navigate to the Instagram Explore page and return the post/reel grid",
        "parameters": {"type": "object", "properties": {}},
    },
    "browse_reels_feed": {
        "fn": lambda ctx, _: navigation.browse_reels_feed(ctx),
        "description": "Navigate to the Instagram Reels feed and return visible reels",
        "parameters": {"type": "object", "properties": {}},
    },
    "read_notifications": {
        "fn": lambda ctx, _: navigation.read_notifications(ctx),
        "description": "Open the activity/notifications tab and return recent likes, follows, and comment activity",
        "parameters": {"type": "object", "properties": {}},
    },
    "open_thread": {
        "fn": lambda ctx, a: navigation.open_thread(ctx, username=a["username"]),
        "description": "Open or create a DM thread with a specific user",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to DM"},
            },
            "required": ["username"],
        },
    },

    # ── Actions ─────────────────────────────────────────────────────────────
    "dismiss_popups": {
        "fn": lambda ctx, _: actions.dismiss_all_popups(ctx),
        "description": "Dismiss cookies, notifications, repost modals",
        "parameters": {"type": "object", "properties": {}},
    },
    "comment_on_post": {
        "fn": lambda ctx, a: actions.comment_on_post(ctx, text=a["text"]),
        "description": "Post a comment with your own text on the currently open post",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Comment text"},
            },
            "required": ["text"],
        },
    },
    "ai_comment_on_post": {
        "fn": lambda ctx, _: actions.ai_comment_on_post(ctx),
        "description": "Gemini writes and posts a specific comment from the post caption, likes up to 2 comments. Use after evaluate_current_post says yes.",
        "parameters": {"type": "object", "properties": {}},
    },
    "skip_post": {
        "fn": lambda ctx, a: actions.skip_post(ctx, reason=a.get("reason", "")),
        "description": "Record this post as skipped and go back. Use when evaluate_current_post says no.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why you're skipping (for logs)"},
            },
        },
    },
    "like_post": {
        "fn": lambda ctx, _: actions.like_post(ctx),
        "description": "Like the currently open post",
        "parameters": {"type": "object", "properties": {}},
    },
    "save_post": {
        "fn": lambda ctx, _: actions.save_post(ctx),
        "description": "Bookmark/save the currently open post",
        "parameters": {"type": "object", "properties": {}},
    },
    "list_media_files": {
        "fn": lambda ctx, _: actions.list_media_files(ctx),
        "description": "List photos/videos uploaded from the dashboard's Posts tab that haven't been posted yet. Call this BEFORE post_photo.",
        "parameters": {"type": "object", "properties": {}},
    },
    "post_photo": {
        "fn": lambda ctx, a: actions.post_photo(ctx, image_path=a.get("image_path", ""), caption=a.get("caption", "")),
        "description": "Post the oldest pending dashboard upload to Instagram (call with no arguments) — it is automatically marked posted afterward so it's never reused. Only pass image_path/caption to override with a specific local file.",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {"type": "string", "description": "Optional — leave empty to post the queued dashboard upload. Only set this to use a specific local file path instead."},
                "caption": {"type": "string", "description": "Optional caption override — the queued upload's own caption is used if omitted"},
            },
        },
    },
    "share_post_via_dm": {
        "fn": lambda ctx, a: actions.share_post_via_dm(ctx, username=a["username"]),
        "description": "Share the currently open post to a user via DM using the share button",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to share the post with"},
            },
            "required": ["username"],
        },
    },
    "follow_hashtag": {
        "fn": lambda ctx, a: actions.follow_hashtag(ctx, hashtag=a["hashtag"]),
        "description": "Follow a hashtag on its explore page. Navigates there if not already on the page.",
        "parameters": {
            "type": "object",
            "properties": {
                "hashtag": {"type": "string", "description": "Hashtag to follow (without #)"},
            },
            "required": ["hashtag"],
        },
    },
    "like_comment": {
        "fn": lambda ctx, a: actions.like_comment(ctx, comment_index=a.get("comment_index", 0)),
        "description": "Like a top-level comment on the open post by index (0=first comment)",
        "parameters": {
            "type": "object",
            "properties": {
                "comment_index": {"type": "integer", "description": "Which comment to like (0-based)"},
            },
        },
    },
    "like_reply": {
        "fn": lambda ctx, a: actions.like_reply(
            ctx,
            comment_index=a.get("comment_index", 0),
            reply_index=a.get("reply_index", 0),
        ),
        "description": "Like a reply (sub-comment) on the open post. Expands replies first if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "comment_index": {"type": "integer", "description": "Parent comment index"},
                "reply_index": {"type": "integer", "description": "Which reply to like (0-based)"},
            },
        },
    },
    "ai_reply_to_comment": {
        "fn": lambda ctx, a: actions.ai_reply_to_comment(
            ctx, comment_index=a.get("comment_index", 0)
        ),
        "description": "Gemini writes and posts a natural reply to one comment. Use after observe_comments for a worthwhile reply target.",
        "parameters": {
            "type": "object",
            "properties": {
                "comment_index": {"type": "integer", "description": "Index of the comment to reply to (from observe_comments)"},
            },
        },
    },
    "reply_to_comment": {
        "fn": lambda ctx, a: actions.reply_to_comment(
            ctx,
            text=a["text"],
            username=a.get("username"),
            comment_index=a.get("comment_index"),
        ),
        "description": "Reply to a visible comment on the open post",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Reply text"},
                "username": {"type": "string", "description": "Username being replied to"},
                "comment_index": {"type": "integer", "description": "Which comment to reply to"},
            },
            "required": ["text"],
        },
    },
    "follow_user": {
        "fn": lambda ctx, a: actions.follow_user(ctx, username=a["username"]),
        "description": "Follow a user. Navigates to their profile if not already there.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to follow (without @)"},
            },
            "required": ["username"],
        },
    },
    "unfollow_user": {
        "fn": lambda ctx, a: actions.unfollow_user(ctx, username=a["username"]),
        "description": "Unfollow a user.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to unfollow"},
            },
            "required": ["username"],
        },
    },
    "send_dm": {
        "fn": lambda ctx, a: actions.send_dm(ctx, username=a["username"], text=a.get("text", "")),
        "description": "DM a real estate pro. 'text' = context about them (message is auto-generated). skipped=true means already DM'd, pick someone else. No evaluate_current_post needed — just open_profile then send_dm.",
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to DM"},
                "text": {"type": "string", "description": "Context about this person (market/niche/post) to personalize the message"},
            },
            "required": ["username"],
        },
    },
    "read_inbox": {
        "fn": lambda ctx, a: actions.read_inbox(ctx, limit=a.get("limit", 5)),
        "description": "Read DM inbox and list recent conversations with username and preview",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "Max threads to return"},
            },
        },
    },
    "reply_to_dm": {
        "fn": lambda ctx, a: actions.reply_to_dm(
            ctx, thread_index=a.get("thread_index", 0), text=a["text"]
        ),
        "description": "Reply to a DM thread by index (from read_inbox results) with your own text",
        "parameters": {
            "type": "object",
            "properties": {
                "thread_index": {"type": "integer", "description": "Thread index from read_inbox"},
                "text": {"type": "string", "description": "Reply text"},
            },
            "required": ["text"],
        },
    },
    "ai_reply_to_dm": {
        "fn": lambda ctx, a: actions.ai_reply_to_dm(
            ctx, thread_index=a.get("thread_index", 0)
        ),
        "description": "If they replied last (not you), wait then send a short genuine English reply. Auto-skips if it's still our turn. Use after read_inbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "thread_index": {"type": "integer", "description": "Thread index from read_inbox (default 0 = first thread)"},
            },
        },
    },

    # ── Session ──────────────────────────────────────────────────────────────
    "wait": {
        "fn": lambda ctx, a: actions.wait_idle(ctx, seconds=a.get("seconds")),
        "description": "Pause like a human reading the page (2-5 seconds)",
        "parameters": {
            "type": "object",
            "properties": {
                "seconds": {"type": "number", "description": "Seconds to wait"},
            },
        },
    },
    "end_session": {
        "fn": lambda ctx, _: {"ended": True},
        "description": "End the browsing session. Call when comment goal is reached or time is up.",
        "parameters": {"type": "object", "properties": {}},
    },
}


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": name,
            "description": spec["description"],
            "parameters": spec["parameters"],
        }
        for name, spec in TOOLS.items()
    ]


def execute_tool(ctx: ToolContext, name: str, arguments: dict | None = None) -> dict:
    if name not in TOOLS:
        raise ValueError(f"Unknown tool: {name}")
    args = arguments or {}
    return TOOLS[name]["fn"](ctx, args)
