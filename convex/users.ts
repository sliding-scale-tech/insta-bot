import { internalMutation, query } from "./_generated/server";
import type { QueryCtx } from "./_generated/server";
import { v } from "convex/values";

// Upsert a user from a Clerk user.created / user.updated webhook payload.
export const upsertFromClerk = internalMutation({
  args: { data: v.any() }, // Clerk UserJSON
  handler: async (ctx, { data }) => {
    const externalId: string = data.id;
    const email: string = data.email_addresses?.[0]?.email_address ?? "";
    const name = `${data.first_name ?? ""} ${data.last_name ?? ""}`.trim()
      || data.username
      || email;
    const attrs = {
      externalId,
      email,
      name,
      imageUrl: data.image_url ?? undefined,
      updatedAt: Date.now(),
    };

    const existing = await userByExternalId(ctx, externalId);
    if (existing === null) {
      await ctx.db.insert("users", attrs);
    } else {
      await ctx.db.patch(existing._id, attrs);
    }
  },
});

// Delete a user from a Clerk user.deleted webhook payload.
export const deleteFromClerk = internalMutation({
  args: { clerkUserId: v.string() },
  handler: async (ctx, { clerkUserId }) => {
    const existing = await userByExternalId(ctx, clerkUserId);
    if (existing !== null) {
      await ctx.db.delete(existing._id);
    }
  },
});

// Read the currently-authenticated user (uses the Clerk JWT identity).
export const current = query({
  args: {},
  handler: async (ctx) => {
    const identity = await ctx.auth.getUserIdentity();
    if (identity === null) return null;
    return await userByExternalId(ctx, identity.subject);
  },
});

export const getByExternalId = query({
  args: { externalId: v.string() },
  handler: async (ctx, { externalId }) => {
    return await userByExternalId(ctx, externalId);
  },
});

export const listAll = query({
  args: {},
  handler: async (ctx) => {
    return await ctx.db.query("users").collect();
  },
});

export async function userByExternalId(ctx: QueryCtx, externalId: string) {
  return await ctx.db
    .query("users")
    .withIndex("byExternalId", (q) => q.eq("externalId", externalId))
    .unique();
}
