import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// All prompts that have been overridden in the DB.
export const listPrompts = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("prompts").collect();
  },
});

// Single prompt by key — used by the automation backend at session start.
export const getPrompt = query({
  args: { key: v.string() },
  handler: async (ctx, { key }) => {
    const row = await ctx.db
      .query("prompts")
      .withIndex("by_key", (q) => q.eq("key", key))
      .first();
    return row ? row.content : null;
  },
});

// Create or update a prompt from the dashboard.
export const upsertPrompt = mutation({
  args: { key: v.string(), content: v.string() },
  handler: async (ctx, { key, content }) => {
    const identity = await ctx.auth.getUserIdentity();
    const existing = await ctx.db
      .query("prompts")
      .withIndex("by_key", (q) => q.eq("key", key))
      .first();
    const patch = {
      content,
      updated_at: Date.now(),
      updated_by: identity?.subject ?? undefined,
    };
    if (existing) {
      await ctx.db.patch(existing._id, patch);
      return existing._id;
    }
    return await ctx.db.insert("prompts", { key, ...patch });
  },
});

// Delete the override so the backend falls back to the built-in default.
export const resetPrompt = mutation({
  args: { key: v.string() },
  handler: async (ctx, { key }) => {
    const row = await ctx.db
      .query("prompts")
      .withIndex("by_key", (q) => q.eq("key", key))
      .first();
    if (row) await ctx.db.delete(row._id);
  },
});
