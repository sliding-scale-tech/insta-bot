import { useState } from 'react'
import { useQuery } from 'convex/react'
import { api } from '../../convex/_generated/api'

interface Summary {
  totals: { comments: number; likes: number; dms: number; follows: number; replies: number; steps: number }
  daily: { date: string; count: number }[]
  byAction: Record<string, number>
  // Optional: absent until the updated analytics query is deployed
  usage?: {
    api_calls: number
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
    avg_cost_per_session: number
  }
  dailyCost?: { date: string; cost: number }[]
  sessions: { total: number; done: number; running: number }
  jobs: { total: number; done: number; error: number; pending: number; processing: number }
  reach: { postsCommented: number; usersDmd: number; usersFollowed: number }
}

function Stat({
  label,
  value,
  tone = 'default',
}: {
  label: string
  value: number | string
  tone?: string
}) {
  const color =
    tone === 'good' ? 'text-green-400' : tone === 'bad' ? 'text-red-400' : 'text-white'
  return (
    <div className="bg-gray-800 rounded-lg p-4">
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-gray-400 mt-0.5">{label}</div>
    </div>
  )
}

/** Compact token counts: 31744 -> 31.7k */
function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function fmtCost(n: number): string {
  if (n === 0) return '$0'
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

function Bars({ data }: { data: { date: string; count: number }[] }) {
  if (data.length === 0) {
    return <p className="text-gray-600 text-sm">No activity recorded yet.</p>
  }
  const max = Math.max(...data.map((d) => d.count), 1)
  return (
    <div className="flex items-end gap-1.5 h-32">
      {data.map((d) => (
        <div key={d.date} className="flex-1 flex flex-col items-center gap-1 min-w-0">
          <div
            className="w-full bg-blue-600 hover:bg-blue-500 rounded-t transition-colors"
            style={{ height: `${Math.max((d.count / max) * 100, 4)}%` }}
            title={`${d.date}: ${d.count} actions`}
          />
          <span className="text-[10px] text-gray-500 truncate w-full text-center">
            {d.date.slice(5)}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function Analytics() {
  const [days, setDays] = useState<number | undefined>(undefined)
  const data = useQuery(api.analytics.summary, { days }) as Summary | undefined

  if (data === undefined) {
    return <p className="text-gray-500 text-sm">Loading analytics…</p>
  }

  // Tolerate older deployed versions of the query that lack newer fields.
  const usage = data.usage ?? {
    api_calls: 0,
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
    cost_usd: 0,
    avg_cost_per_session: 0,
  }
  const dailyCost = data.dailyCost ?? []
  const daily = data.daily ?? []
  const byAction = data.byAction ?? {}
  const totals = data.totals ?? {
    comments: 0, likes: 0, dms: 0, follows: 0, replies: 0, steps: 0,
  }
  const jobs = data.jobs ?? { total: 0, done: 0, error: 0, pending: 0, processing: 0 }
  const reach = data.reach ?? { postsCommented: 0, usersDmd: 0, usersFollowed: 0 }
  const sessions = data.sessions ?? { total: 0, done: 0, running: 0 }

  const ranges: { label: string; value: number | undefined }[] = [
    { label: '7d', value: 7 },
    { label: '30d', value: 30 },
    { label: 'All time', value: undefined },
  ]

  return (
    <div className="flex flex-col gap-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Analytics</h1>
        <div className="flex gap-1">
          {ranges.map((r) => (
            <button
              key={r.label}
              onClick={() => setDays(r.value)}
              className={`text-xs px-3 py-1 rounded transition-colors ${
                days === r.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:text-white'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Engagement</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Comments" value={totals.comments} />
          <Stat label="Likes" value={totals.likes} />
          <Stat label="DMs" value={totals.dms} />
          <Stat label="Follows" value={totals.follows} />
          <Stat label="Replies" value={totals.replies} />
        </div>
      </section>

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Gemini usage &amp; cost</h2>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <Stat label="Total cost" value={fmtCost(usage.cost_usd)} tone="good" />
          <Stat label="Avg / session" value={fmtCost(usage.avg_cost_per_session)} />
          <Stat label="Total tokens" value={fmtTokens(usage.total_tokens)} />
          <Stat label="Input tokens" value={fmtTokens(usage.input_tokens)} />
          <Stat label="API calls" value={usage.api_calls} />
        </div>
        {!data.usage && (
          <p className="text-xs text-yellow-500 mt-2">
            Cost tracking isn’t live yet — run <code className="text-gray-300">npx convex login</code>{' '}
            then <code className="text-gray-300">npx convex dev --once</code> to deploy it.
          </p>
        )}
        {dailyCost.length > 0 && (
          <div className="bg-gray-800 rounded-lg p-4 mt-3">
            <p className="text-xs text-gray-500 mb-2">Spend per day</p>
            <div className="flex items-end gap-1.5 h-20">
              {dailyCost.map((d) => {
                const max = Math.max(...dailyCost.map((x) => x.cost), 0.0001)
                return (
                  <div key={d.date} className="flex-1 flex flex-col items-center gap-1 min-w-0">
                    <div
                      className="w-full bg-emerald-600 hover:bg-emerald-500 rounded-t transition-colors"
                      style={{ height: `${Math.max((d.cost / max) * 100, 4)}%` }}
                      title={`${d.date}: ${fmtCost(d.cost)}`}
                    />
                    <span className="text-[10px] text-gray-500 truncate w-full text-center">
                      {d.date.slice(5)}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </section>

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Activity (last 14 active days)</h2>
        <div className="bg-gray-800 rounded-lg p-4">
          <Bars data={daily} />
        </div>
      </section>

      <div className="grid md:grid-cols-2 gap-6">
        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-2">Goals</h2>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Completed" value={jobs.done} tone="good" />
            <Stat label="Errored" value={jobs.error} tone="bad" />
            <Stat label="Pending" value={jobs.pending} />
            <Stat label="Processing" value={jobs.processing} />
          </div>
        </section>

        <section>
          <h2 className="text-sm font-medium text-gray-400 mb-2">Unique reach</h2>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="Posts commented" value={reach.postsCommented} />
            <Stat label="Users DM'd" value={reach.usersDmd} />
            <Stat label="Following" value={reach.usersFollowed} />
          </div>
        </section>
      </div>

      <section>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Actions by type</h2>
        {Object.keys(byAction).length === 0 ? (
          <p className="text-gray-600 text-sm">No actions logged yet.</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {Object.entries(byAction)
              .sort(([, a], [, b]) => b - a)
              .map(([action, count]) => (
                <span
                  key={action}
                  className="bg-gray-800 rounded px-3 py-1.5 text-sm"
                >
                  <span className="text-gray-400">{action}</span>{' '}
                  <span className="text-white font-medium">{count}</span>
                </span>
              ))}
          </div>
        )}
      </section>

      <p className="text-xs text-gray-600">
        Sessions: {sessions.total} total · {sessions.done} completed ·{' '}
        {sessions.running} running
      </p>
    </div>
  )
}
