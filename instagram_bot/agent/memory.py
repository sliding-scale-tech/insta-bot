"""Session memory — track actions to avoid spam within one run."""

from dataclasses import dataclass, field
from typing import Any

from instagram_bot.agent.persistent_memory import normalize_url


@dataclass
class SessionMemory:
    commented_posts: list[str] = field(default_factory=list)
    replied_comments: list[str] = field(default_factory=list)
    skipped_posts: list[str] = field(default_factory=list)
    followed_users: list[str] = field(default_factory=list)
    dm_sent: list[str] = field(default_factory=list)
    liked_items: list[str] = field(default_factory=list)
    actions_log: list[dict[str, Any]] = field(default_factory=list)
    comments_count: int = 0
    replies_count: int = 0
    likes_count: int = 0
    follows_count: int = 0
    dms_count: int = 0

    def has_commented(self, post_url: str) -> bool:
        n = normalize_url(post_url)
        return any(normalize_url(u) == n for u in self.commented_posts)

    def has_skipped(self, post_url: str) -> bool:
        n = normalize_url(post_url)
        return any(normalize_url(u) == n for u in self.skipped_posts)

    def has_liked(self, key: str) -> bool:
        return key in self.liked_items

    def has_followed(self, username: str) -> bool:
        return username.lstrip("@").lower() in [u.lower() for u in self.followed_users]

    def record_action(self, tool: str, result: dict) -> None:
        self.actions_log.append({"tool": tool, "result": result})

    def summary(self) -> dict:
        return {
            "comments": self.comments_count,
            "replies": self.replies_count,
            "likes": self.likes_count,
            "follows": self.follows_count,
            "dms": self.dms_count,
            "posts_commented": self.commented_posts,
            "posts_skipped": len(self.skipped_posts),
            "total_actions": len(self.actions_log),
        }
