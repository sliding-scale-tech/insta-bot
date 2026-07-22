import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// Create a new job in "pending" state.
export const createJob = mutation({
  args: { user_id: v.string(), goal: v.string() },
  handler: async (ctx, { user_id, goal }) => {
    return await ctx.db.insert("jobs", {
      user_id,
      goal,
      status: "pending",
      created_at: Date.now(),
    });
  },
});

// Move a job to "processing".
export const startJob = mutation({
  args: { job_id: v.id("jobs") },
  handler: async (ctx, { job_id }) => {
    await ctx.db.patch(job_id, { status: "processing", started_at: Date.now() });
  },
});

// Finish a job — status is "done" or "error".
export const finishJob = mutation({
  args: {
    job_id: v.id("jobs"),
    status: v.string(),
    exit_code: v.optional(v.number()),
    error: v.optional(v.string()),
  },
  handler: async (ctx, { job_id, status, exit_code, error }) => {
    await ctx.db.patch(job_id, {
      status,
      ended_at: Date.now(),
      ...(exit_code !== undefined ? { exit_code } : {}),
      ...(error !== undefined ? { error } : {}),
    });
  },
});

// List recent jobs for a user (newest first). Prefers the authenticated Clerk
// identity so the client always sees its own jobs; falls back to the passed
// user_id in simple-token mode (no Clerk identity).
export const listJobs = query({
  args: { user_id: v.string(), limit: v.optional(v.number()) },
  handler: async (ctx, { user_id, limit }) => {
    const identity = await ctx.auth.getUserIdentity();
    const uid = identity?.subject ?? user_id;
    return await ctx.db
      .query("jobs")
      .withIndex("by_user_id", (q) => q.eq("user_id", uid))
      .order("desc")
      .take(limit ?? 30);
  },
});

// Oldest pending job for a user (queue head) — used by the server to dequeue.
export const nextPending = query({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    return await ctx.db
      .query("jobs")
      .withIndex("by_user_status", (q) =>
        q.eq("user_id", user_id).eq("status", "pending")
      )
      .order("asc")
      .first();
  },
});

// On server restart, mark any orphaned processing jobs as errored.
export const failStaleProcessing = mutation({
  args: { user_id: v.string() },
  handler: async (ctx, { user_id }) => {
    const rows = await ctx.db
      .query("jobs")
      .withIndex("by_user_status", (q) =>
        q.eq("user_id", user_id).eq("status", "processing")
      )
      .collect();
    for (const row of rows) {
      await ctx.db.patch(row._id, {
        status: "error",
        ended_at: Date.now(),
        error: "Server restarted while job was running",
      });
    }
    return rows.length;
  },
});

// Same as failStaleProcessing but across ALL users — used at server startup
// since a restart can orphan any user's job, not just "default".
export const failAllStaleProcessing = mutation({
  args: {},
  handler: async (ctx) => {
    const rows = await ctx.db
      .query("jobs")
      .filter((q) => q.eq(q.field("status"), "processing"))
      .collect();
    for (const row of rows) {
      await ctx.db.patch(row._id, {
        status: "error",
        ended_at: Date.now(),
        error: "Server restarted while job was running",
      });
    }
    return rows.length;
  },
});
