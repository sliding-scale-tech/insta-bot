import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const listSettings = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("settings").collect();
  },
});

export const upsertSetting = mutation({
  args: { key: v.string(), value: v.string() },
  handler: async (ctx, { key, value }) => {
    const identity = await ctx.auth.getUserIdentity();
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", key))
      .first();
    const patch = { value, updated_at: Date.now(), updated_by: identity?.subject };
    if (existing) {
      await ctx.db.patch(existing._id, patch);
      return existing._id;
    }
    return await ctx.db.insert("settings", { key, ...patch });
  },
});

export const resetSetting = mutation({
  args: { key: v.string() },
  handler: async (ctx, { key }) => {
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_key", (q) => q.eq("key", key))
      .first();
    if (existing) await ctx.db.delete(existing._id);
  },
});
