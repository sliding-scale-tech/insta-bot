import { query } from "./_generated/server";
import { v } from "convex/values";

/** Aggregate stats across all sessions + engagement, for the Analytics tab. */
export const summary = query({
  args: { days: v.optional(v.number()) },
  handler: async (ctx, { days }) => {
    const since = days ? Date.now() - days * 24 * 60 * 60 * 1000 : 0;

    const sessions = (await ctx.db.query("sessions").collect())
      .filter((s) => s.started_at >= since);
    const engagement = (await ctx.db.query("engagement_log").collect())
      .filter((e) => e.acted_at >= since);
    const jobs = (await ctx.db.query("jobs").collect())
      .filter((j) => j.created_at >= since);

    const totals = sessions.reduce(
      (acc, s) => ({
        comments: acc.comments + (s.comments ?? 0),
        likes: acc.likes + (s.likes ?? 0),
        dms: acc.dms + (s.dms ?? 0),
        follows: acc.follows + (s.follows ?? 0),
        replies: acc.replies + (s.replies ?? 0),
        steps: acc.steps + (s.steps ?? 0),
      }),
      { comments: 0, likes: 0, dms: 0, follows: 0, replies: 0, steps: 0 }
    );

    // Actions per day (last 14 buckets) for a simple trend chart
    const byDay: Record<string, number> = {};
    for (const e of engagement) {
      const d = new Date(e.acted_at).toISOString().slice(0, 10);
      byDay[d] = (byDay[d] ?? 0) + 1;
    }
    const daily = Object.entries(byDay)
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .slice(-14)
      .map(([date, count]) => ({ date, count }));

    // Breakdown by action type
    const byAction: Record<string, number> = {};
    for (const e of engagement) {
      byAction[e.action] = (byAction[e.action] ?? 0) + 1;
    }

    // Gemini usage + spend
    const usage = sessions.reduce(
      (acc, s) => ({
        api_calls: acc.api_calls + (s.api_calls ?? 0),
        input_tokens: acc.input_tokens + (s.input_tokens ?? 0),
        output_tokens: acc.output_tokens + (s.output_tokens ?? 0),
        total_tokens: acc.total_tokens + (s.total_tokens ?? 0),
        cost_usd: acc.cost_usd + (s.cost_usd ?? 0),
      }),
      { api_calls: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0, cost_usd: 0 }
    );
    const withCost = sessions.filter((s) => (s.cost_usd ?? 0) > 0);
    const avgCost = withCost.length ? usage.cost_usd / withCost.length : 0;

    // Spend per day, aligned with the activity chart
    const costByDay: Record<string, number> = {};
    for (const s of sessions) {
      if (!s.cost_usd) continue;
      const d = new Date(s.started_at).toISOString().slice(0, 10);
      costByDay[d] = (costByDay[d] ?? 0) + s.cost_usd;
    }
    const dailyCost = Object.entries(costByDay)
      .sort(([a], [b]) => (a < b ? -1 : 1))
      .slice(-14)
      .map(([date, cost]) => ({ date, cost }));

    const commented = await ctx.db.query("commented_posts").collect();
    const dmSent = await ctx.db.query("dm_sent").collect();
    const followed = await ctx.db.query("followed_users").collect();

    return {
      totals,
      daily,
      byAction,
      usage: { ...usage, avg_cost_per_session: avgCost },
      dailyCost,
      sessions: {
        total: sessions.length,
        done: sessions.filter((s) => s.status === "done").length,
        running: sessions.filter((s) => s.status === "running").length,
      },
      jobs: {
        total: jobs.length,
        done: jobs.filter((j) => j.status === "done").length,
        error: jobs.filter((j) => j.status === "error").length,
        pending: jobs.filter((j) => j.status === "pending").length,
        processing: jobs.filter((j) => j.status === "processing").length,
      },
      reach: {
        postsCommented: commented.length,
        usersDmd: new Set(dmSent.map((d) => d.to_username)).size,
        usersFollowed: followed.filter((f) => f.unfollowed_at === undefined).length,
      },
    };
  },
});
