import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  // Posts the bot has already commented on (replaces data/commented_posts.json)
  commented_posts: defineTable({
    url: v.string(),           // normalized post URL
    shortcode: v.string(),     // e.g. "ABC123" from /p/ABC123/
    comment_snippet: v.string(), // first 100 chars of what was said
    username: v.string(),      // Instagram account that did the commenting
    commented_at: v.number(),  // unix timestamp ms
  }).index("by_url", ["url"])
    .index("by_shortcode", ["shortcode"]),

  // DMs sent — dedup guard across sessions
  dm_sent: defineTable({
    to_username: v.string(),
    from_username: v.string(),
    message_preview: v.string(),
    sent_at: v.number(),
  }).index("by_to_username", ["to_username"]),

  // Users followed by the bot
  followed_users: defineTable({
    username: v.string(),
    followed_at: v.number(),
    unfollowed_at: v.optional(v.number()),
  }).index("by_username", ["username"]),

  // Session logs — one record per run
  sessions: defineTable({
    goal: v.string(),
    started_at: v.number(),
    ended_at: v.optional(v.number()),
    comments: v.number(),
    likes: v.number(),
    follows: v.number(),
    dms: v.number(),
    replies: v.number(),
    steps: v.number(),
    status: v.string(), // "running" | "done" | "error"
    // Gemini usage for this session (absent on older rows)
    model: v.optional(v.string()),
    api_calls: v.optional(v.number()),
    input_tokens: v.optional(v.number()),
    output_tokens: v.optional(v.number()),
    thinking_tokens: v.optional(v.number()),
    total_tokens: v.optional(v.number()),
    cost_usd: v.optional(v.number()),
  }),

  // Photos/videos uploaded from the dashboard for the bot to post. Files live in
  // Convex file storage (not on the VPS disk) — the bot downloads to a temp file
  // only while posting, then deletes it. Each file is posted AT MOST ONCE:
  // post_photo only picks "pending" rows and flips them to "posted" right after
  // a successful share, so re-runs can't reuse it.
  media_posts: defineTable({
    user_id: v.string(),
    storage_id: v.id("_storage"),
    original_name: v.string(),  // name as uploaded, for display
    caption: v.string(),
    status: v.string(),         // "pending" | "posted" | "error"
    uploaded_at: v.number(),
    posted_at: v.optional(v.number()),
    post_url: v.optional(v.string()),
    error: v.optional(v.string()),
    error_screenshot_id: v.optional(v.id("_storage")),
  }).index("by_user_status", ["user_id", "status"]),

  // A whole day's work split into session-goals with breaks between them.
  // The backend poller drives it; state lives here so a restart resumes cleanly.
  day_plans: defineTable({
    user_id: v.string(),
    raw_goal: v.string(),        // what the user asked for the whole day
    status: v.string(),          // "draft" | "running" | "done" | "cancelled" | "error"
    sessions: v.array(
      v.object({
        goal: v.string(),
        break_minutes: v.number(),
        status: v.string(),      // "pending" | "running" | "done" | "error"
        attempts: v.number(),
        job_id: v.optional(v.id("jobs")),
        started_at: v.optional(v.number()),
        ended_at: v.optional(v.number()),
      })
    ),
    current_index: v.number(),
    next_run_at: v.optional(v.number()),  // when the next session may start
    daily_caps: v.object({
      comments: v.number(),
      likes: v.number(),
      dms: v.number(),
      follows: v.number(),
    }),
    created_at: v.number(),
    started_at: v.optional(v.number()),
    ended_at: v.optional(v.number()),
    note: v.optional(v.string()),
  }).index("by_user_status", ["user_id", "status"])
    .index("by_status", ["status"]),

  // Editable settings (session caps, timings, niche fallback) — dashboard writes
  // them, the automation backend reads them at the start of each session/plan.
  // Stored as strings; the backend parses to int/str per key's declared type.
  settings: defineTable({
    key: v.string(),
    value: v.string(),
    updated_at: v.number(),
    updated_by: v.optional(v.string()),
  }).index("by_key", ["key"]),

  // Editable prompts — dashboard writes them, the automation backend reads them
  // at session start (falls back to code defaults when a key is absent).
  prompts: defineTable({
    key: v.string(),          // "system" | "evaluate_post" | "generate_comment" | ...
    content: v.string(),      // template text with {placeholders}
    updated_at: v.number(),
    updated_by: v.optional(v.string()),
  }).index("by_key", ["key"]),

  // Users synced from Clerk via webhook (user.created / updated / deleted)
  users: defineTable({
    externalId: v.string(),   // Clerk user id (the "sub" in the JWT)
    email: v.string(),
    name: v.string(),
    imageUrl: v.optional(v.string()),
    updatedAt: v.number(),
  }).index("byExternalId", ["externalId"]),

  // Goal queue — one row per goal the user submits from the dashboard
  jobs: defineTable({
    user_id: v.string(),
    goal: v.string(),
    status: v.string(),        // "pending" | "processing" | "done" | "error"
    created_at: v.number(),
    started_at: v.optional(v.number()),
    ended_at: v.optional(v.number()),
    error: v.optional(v.string()),
    exit_code: v.optional(v.number()),
  }).index("by_user_id", ["user_id"])
    .index("by_user_status", ["user_id", "status"]),

  // Instagram browser sessions (Playwright storage_state JSON, keyed by user_id)
  browser_sessions: defineTable({
    user_id: v.string(),
    storage_state: v.string(), // full Playwright storage_state JSON
    saved_at: v.number(),
  }).index("by_user_id", ["user_id"]),

  // Per-post engagement log (every like, comment, follow from a post visit)
  engagement_log: defineTable({
    post_url: v.string(),
    action: v.string(),        // "comment" | "like" | "reply" | "follow" | "dm"
    detail: v.string(),        // comment text, username followed, etc.
    session_id: v.optional(v.id("sessions")),
    acted_at: v.number(),
  }).index("by_post_url", ["post_url"])
    .index("by_action", ["action"]),
});
