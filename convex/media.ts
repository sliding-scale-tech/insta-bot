import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

/** Frontend calls this, then POSTs the file bytes directly to the returned URL —
 * the file never passes through the FastAPI backend or touches VPS disk. */
export const generateUploadUrl = mutation({
  args: {},
  handler: async (ctx) => {
    return await ctx.storage.generateUploadUrl();
  },
});

export const createMediaPost = mutation({
  args: {
    user_id: v.string(),
    storage_id: v.id("_storage"),
    original_name: v.string(),
    caption: v.string(),
  },
  handler: async (ctx, args) => {
    // Prefer the authenticated Clerk identity over the passed-in user_id, so an
    // upload always lands under the same id listMediaPosts/pendingMediaPosts
    // reads from — otherwise a signed-in upload could be written to "default"
    // while the dashboard (and the bot) look under the real Clerk id.
    const identity = await ctx.auth.getUserIdentity();
    const uid = identity?.subject ?? args.user_id;
    return await ctx.db.insert("media_posts", {
      ...args,
      user_id: uid,
      status: "pending",
      uploaded_at: Date.now(),
    });
  },
});

export const listMediaPosts = query({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    const identity = await ctx.auth.getUserIdentity();
    const uid = identity?.subject ?? user_id;
    const rows = await ctx.db
      .query("media_posts")
      .withIndex("by_user_status", (q) => q.eq("user_id", uid))
      .collect();
    const withUrls = await Promise.all(
      rows.map(async (r) => ({
        ...r,
        preview_url: await ctx.storage.getUrl(r.storage_id),
        error_screenshot_url: r.error_screenshot_id
          ? await ctx.storage.getUrl(r.error_screenshot_id)
          : null,
      }))
    );
    return withUrls.sort((a, b) => b.uploaded_at - a.uploaded_at);
  },
});

/** All not-yet-posted rows for a user — what the bot is allowed to post. */
export const pendingMediaPosts = query({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    const rows = await ctx.db
      .query("media_posts")
      .withIndex("by_user_status", (q) => q.eq("user_id", user_id).eq("status", "pending"))
      .collect();
    return rows.sort((a, b) => a.uploaded_at - b.uploaded_at); // oldest first
  },
});

/** Signed download URL the bot fetches bytes from — used only for the moment
 * of posting; the caller downloads to a temp file and deletes it right after. */
export const getMediaUrl = query({
  args: { storage_id: v.id("_storage") },
  handler: async (ctx, { storage_id }) => {
    return await ctx.storage.getUrl(storage_id);
  },
});

export const markMediaPosted = mutation({
  args: { media_id: v.id("media_posts"), post_url: v.optional(v.string()) },
  handler: async (ctx, { media_id, post_url }) => {
    await ctx.db.patch(media_id, {
      status: "posted",
      posted_at: Date.now(),
      post_url,
    });
  },
});

export const markMediaError = mutation({
  args: {
    media_id: v.id("media_posts"),
    error: v.string(),
    error_screenshot_id: v.optional(v.id("_storage")),
  },
  handler: async (ctx, { media_id, error, error_screenshot_id }) => {
    await ctx.db.patch(media_id, { status: "error", error, error_screenshot_id });
  },
});

/** Requeue an errored (or wrongly-marked) upload so the bot can try it again. */
export const retryMediaPost = mutation({
  args: { media_id: v.id("media_posts") },
  handler: async (ctx, { media_id }) => {
    await ctx.db.patch(media_id, {
      status: "pending",
      error: undefined,
      error_screenshot_id: undefined,
      post_url: undefined,
      posted_at: undefined,
    });
  },
});

export const deleteMediaPost = mutation({
  args: { media_id: v.id("media_posts") },
  handler: async (ctx, { media_id }) => {
    const row = await ctx.db.get(media_id);
    if (row) {
      // The stored file may already be gone (e.g. deleted separately, or by a
      // prior delete that failed midway) — don't let that block removing the
      // row itself, or the entry becomes permanently stuck.
      try {
        await ctx.storage.delete(row.storage_id);
      } catch (err) {
        console.warn(`storage delete skipped for ${row.storage_id}:`, err);
      }
      await ctx.db.delete(media_id);
    }
  },
});
