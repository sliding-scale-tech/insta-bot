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
    "evaluate_current_post": {
        "fn": lambda ctx, _: perception.evaluate_current_post(ctx),
        "description": (
            "AI evaluation: should I comment on this post? "
            "Checks memory (no duplicate), then calls Gemini to decide. "
            "Returns {should_comment, confidence, reason, skip_reason}. "
            "ALWAYS call this after observe_current_post before engaging."
        ),
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
        "description": (
            "Gemini reads the post caption and writes a specific, helpful comment then posts it. "
            "Also likes up to 2 comments automatically. Use AFTER evaluate_current_post returns should_comment=true."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
    "skip_post": {
        "fn": lambda ctx, a: actions.skip_post(ctx, reason=a.get("reason", "")),
        "description": (
            "Record this post as skipped (won't re-open it this session) and go back to feed. "
            "Use when evaluate_current_post returns should_comment=false."
        ),
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
        "description": (
            "Gemini reads a specific comment and writes a natural, human-sounding reply, then posts it. "
            "Use after observe_comments when you see an interesting question or point worth responding to."
        ),
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
        "description": (
            "Send a DM to a real estate professional. "
            "The 'text' field is CONTEXT ABOUT THEM (their niche, market, what they posted) — "
            "the actual message is auto-generated as a genuine 1-sentence question. "
            "If result has skipped=true, that person was already DM'd — pick a DIFFERENT person. "
            "Do NOT call evaluate_current_post before DMing — just open_profile then send_dm."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username to DM"},
                "text": {"type": "string", "description": "Context about this person (their market, niche, what they posted) — used to personalize the auto-generated message"},
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
        "description": (
            "Check a DM thread — if THEY replied last (not you), wait 30-60s then send a short "
            "genuine English reply to build rapport. Skips automatically if we sent the last message. "
            "Use after read_inbox to reply to people who responded to your outreach."
        ),
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
