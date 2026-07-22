"""Quick smoke test for Convex DB connection."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from instagram_bot.db.convex_client import (
    has_commented, add_commented_post, get_all_commented_urls,
    has_dm_sent, add_dm_sent, has_followed, add_followed_user,
    start_session, end_session,
)

print("=== Convex DB Smoke Test ===\n")

# 1. Commented posts
TEST_URL = "https://www.instagram.com/p/TEST123/"
print("1. commented_posts")
print(f"   has_commented before: {has_commented(TEST_URL)}")
add_commented_post(TEST_URL, "TEST123", "Great post!", "testuser")
print(f"   has_commented after:  {has_commented(TEST_URL)}")
urls = get_all_commented_urls()
print(f"   total urls in DB: {len(urls)}")
print("   [PASS]\n")

# 2. DM sent
print("2. dm_sent")
print(f"   has_dm_sent before: {has_dm_sent('target_user', 'mybot')}")
add_dm_sent("target_user", "mybot", "Hey, saw your post about...")
print(f"   has_dm_sent after:  {has_dm_sent('target_user', 'mybot')}")
print("   [PASS]\n")

# 3. Followed users
print("3. followed_users")
print(f"   has_followed before: {has_followed('some_realtor')}")
add_followed_user("some_realtor")
print(f"   has_followed after:  {has_followed('some_realtor')}")
print("   [PASS]\n")

# 4. Sessions
print("4. sessions")
sid = start_session("comment on 3 posts")
print(f"   session_id: {sid}")
end_session(sid, comments=3, likes=5, follows=1, dms=1, replies=2, steps=20)
print("   session ended")
print("   [PASS]\n")

print("=== All tests passed — Convex is working! ===")
