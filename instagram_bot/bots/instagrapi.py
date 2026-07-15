"""Instagram bot using the instagrapi API."""

import random
import time

from instagram_bot.auth.instagrapi import get_authenticated_client, relogin_if_needed
from instagram_bot.config.settings import (
    COMMENT_TEXT,
    DM_MESSAGE,
    HASHTAG_TO_SEARCH,
    MAX_COMMENTS,
    MAX_DMS,
)


def wait_human(min_seconds: int = 15, max_seconds: int = 45) -> None:
    delay = random.randint(min_seconds, max_seconds)
    print(f"  ...waiting {delay}s")
    time.sleep(delay)


def run_instagrapi_bot() -> None:
    cl = get_authenticated_client()
    cl = relogin_if_needed(cl)
    print(f"Logged in as @{cl.username} via instagrapi\n")

    print(f"Searching #{HASHTAG_TO_SEARCH}...")
    wait_human(2, 5)
    medias = cl.hashtag_medias_recent(HASHTAG_TO_SEARCH, amount=20)

    if not medias:
        raise SystemExit(f"No posts found for #{HASHTAG_TO_SEARCH}")

    comment_count = 0
    dm_count = 0

    for media in medias:
        if comment_count >= MAX_COMMENTS and dm_count >= MAX_DMS:
            break

        author = media.user.username
        post_url = f"https://www.instagram.com/p/{media.code}/"
        print(f"\nPost by @{author}: {post_url}")

        if comment_count < MAX_COMMENTS:
            try:
                wait_human(20, 45)
                cl.media_comment(media.id, COMMENT_TEXT)
                comment_count += 1
                print(f"[{comment_count}/{MAX_COMMENTS}] Comment posted")
            except Exception as error:
                print(f"Failed to comment: {error}")

        if dm_count < MAX_DMS:
            try:
                wait_human(30, 60)
                cl.direct_send(DM_MESSAGE, user_ids=[int(media.user.pk)])
                dm_count += 1
                print(f"[{dm_count}/{MAX_DMS}] DM sent to @{author}")
            except Exception as error:
                print(f"Failed to send DM: {error}")

        wait_human(15, 30)

    print(f"\nDone. Comments: {comment_count}, DMs: {dm_count}")
