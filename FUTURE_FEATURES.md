# Future Features

Capabilities a normal Instagram user has that this bot doesn't yet — deferred until
after the bug-fix/token-cost hardening pass and the VPS conversion. Not started;
no code exists for any of these.

## Missing entirely (no tool)


- **Reels feed** — browse/watch reels (not just open a single reel by URL)
- **Save / bookmark** a post
- **Share a post via DM** ("send to…")
- **Account/people search** — current search is hashtag-only; can't find a person by name/username without already knowing it
- **Followers / following lists** — view who follows or is followed by an account
- **Notifications tab** — read the activity/heart feed
- **Posting content** — upload a photo/video/reel/story with a caption
- **Follow a hashtag**
- **Explore-page browsing** (the general Explore grid, not hashtag pages)but 

## Exists but incomplete

- **Reel handling** — `open_post` can navigate to a `/reel/` URL, but `parse_current_post` is tuned for the photo-post DOM; author/caption extraction is unreliable on reels
- **Reply-thread observation** — `like_reply` can like a reply once replies are expanded, but there's no `observe_replies` tool, so the model has to guess `reply_index` blindly instead of reading what the replies say
- **Comment pagination** — `parse_comments` now loads once via the "load more" control, but doesn't loop to keep loading — very long comment threads still aren't fully explorable
