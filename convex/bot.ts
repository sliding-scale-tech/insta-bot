import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// ── commented_posts ──────────────────────────────────────────────────────────

export const hasCommented = query({
  args: { url: v.string() },
  handler: async (ctx, { url }) => {
    const row = await ctx.db
      .query("commented_posts")
      .withIndex("by_url", (q) => q.eq("url", url))
      .first();
    return row !== null;
  },
});

export const addCommentedPost = mutation({
  args: {
    url: v.string(),
    shortcode: v.string(),
    comment_snippet: v.string(),
    username: v.string(),
  },
  handler: async (ctx, args) => {
    const existing = await ctx.db
      .query("commented_posts")
      .withIndex("by_url", (q) => q.eq("url", args.url))
      .first();
    if (existing) return existing._id;
    return await ctx.db.insert("commented_posts", {
      ...args,
      commented_at: Date.now(),
    });
  },
});

export const getAllCommentedUrls = query({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db.query("commented_posts").collect();
    return rows.map((r) => r.url);
  },
});

export const getAllDmUsernames = query({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db.query("dm_sent").collect();
    return [...new Set(rows.map((r) => r.to_username))];
  },
});

// ── dm_sent ──────────────────────────────────────────────────────────────────

export const hasDmSent = query({
  args: { to_username: v.string(), from_username: v.string() },
  handler: async (ctx, { to_username, from_username }) => {
    const row = await ctx.db
      .query("dm_sent")
      .withIndex("by_to_username", (q) => q.eq("to_username", to_username))
      .filter((q) => q.eq(q.field("from_username"), from_username))
      .first();
    return row !== null;
  },
});

export const addDmSent = mutation({
  args: {
    to_username: v.string(),
    from_username: v.string(),
    message_preview: v.string(),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("dm_sent", {
      ...args,
      sent_at: Date.now(),
    });
  },
});

export const getAllFollowedUsernames = query({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db
      .query("followed_users")
      .filter((q) => q.eq(q.field("unfollowed_at"), undefined))
      .collect();
    return rows.map((r) => r.username);
  },
});

// ── followed_users ───────────────────────────────────────────────────────────

export const hasFollowed = query({
  args: { username: v.string() },
  handler: async (ctx, { username }) => {
    const row = await ctx.db
      .query("followed_users")
      .withIndex("by_username", (q) => q.eq("username", username))
      .first();
    return row !== null && row.unfollowed_at === undefined;
  },
});

export const addFollowedUser = mutation({
  args: { username: v.string() },
  handler: async (ctx, { username }) => {
    const existing = await ctx.db
      .query("followed_users")
      .withIndex("by_username", (q) => q.eq("username", username))
      .first();
    if (existing) return existing._id;
    return await ctx.db.insert("followed_users", {
      username,
      followed_at: Date.now(),
    });
  },
});

// ── sessions ─────────────────────────────────────────────────────────────────

export const startSession = mutation({
  args: { goal: v.string() },
  handler: async (ctx, { goal }) => {
    return await ctx.db.insert("sessions", {
      goal,
      started_at: Date.now(),
      comments: 0,
      likes: 0,
      follows: 0,
      dms: 0,
      replies: 0,
      steps: 0,
      status: "running",
    });
  },
});

export const endSession = mutation({
  args: {
    session_id: v.id("sessions"),
    comments: v.number(),
    likes: v.number(),
    follows: v.number(),
    dms: v.number(),
    replies: v.number(),
    steps: v.number(),
    status: v.string(),
    // Gemini usage (optional — dry runs have none)
    model: v.optional(v.string()),
    api_calls: v.optional(v.number()),
    input_tokens: v.optional(v.number()),
    output_tokens: v.optional(v.number()),
    thinking_tokens: v.optional(v.number()),
    total_tokens: v.optional(v.number()),
    cost_usd: v.optional(v.number()),
  },
  handler: async (ctx, { session_id, ...stats }) => {
    await ctx.db.patch(session_id, {
      ...stats,
      ended_at: Date.now(),
    });
  },
});

export const listSessions = query({
  args: { limit: v.optional(v.number()) },
  handler: async (ctx, { limit }) => {
    const rows = await ctx.db.query("sessions").order("desc").take(limit ?? 20);
    return rows;
  },
});

// ── engagement_log ───────────────────────────────────────────────────────────

// ── browser_sessions ─────────────────────────────────────────────────────────

export const saveBrowserSession = mutation({
  args: { user_id: v.string(), storage_state: v.string() },
  handler: async (ctx, { user_id, storage_state }) => {
    const existing = await ctx.db
      .query("browser_sessions")
      .withIndex("by_user_id", (q) => q.eq("user_id", user_id))
      .first();
    if (existing) {
      await ctx.db.patch(existing._id, { storage_state, saved_at: Date.now() });
    } else {
      await ctx.db.insert("browser_sessions", { user_id, storage_state, saved_at: Date.now() });
    }
  },
});

export const getBrowserSession = query({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    const row = await ctx.db
      .query("browser_sessions")
      .withIndex("by_user_id", (q) => q.eq("user_id", user_id))
      .first();
    return row ? row.storage_state : null;
  },
});

export const deleteBrowserSession = mutation({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    const row = await ctx.db
      .query("browser_sessions")
      .withIndex("by_user_id", (q) => q.eq("user_id", user_id))
      .first();
    if (row) await ctx.db.delete(row._id);
  },
});

// ─────────────────────────────────────────────────────────────────────────────

export const clearAll = mutation({
  args: {},
  handler: async (ctx) => {
    const tables = ["commented_posts", "dm_sent", "followed_users", "sessions", "engagement_log", "browser_sessions", "jobs"] as const;
    let total = 0;
    for (const table of tables) {
      const rows = await ctx.db.query(table).collect();
      for (const row of rows) {
        await ctx.db.delete(row._id);
        total++;
      }
    }
    return { deleted: total };
  },
});

export const logEngagement = mutation({
  args: {
    post_url: v.string(),
    action: v.string(),
    detail: v.string(),
    session_id: v.optional(v.id("sessions")),
  },
  handler: async (ctx, args) => {
    return await ctx.db.insert("engagement_log", {
      ...args,
      acted_at: Date.now(),
    });
  },
});
