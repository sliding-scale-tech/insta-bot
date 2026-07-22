import { useQuery } from 'convex/react'
import { api } from '../../convex/_generated/api'
import { useState } from 'react'

interface Session {
  _id: string
  date: string
  goal: string
  comments: number
  likes: number
  dms: number
  follows: number
  steps: number
  duration: number
  status: string
  started_at?: number
  ended_at?: number
  model?: string
  api_calls?: number
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
  cost_usd?: number
}

function fmtTokens(n?: number): string {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return String(n)
}

function fmtCost(n?: number): string {
  if (!n) return '—'
  if (n < 0.01) return `$${n.toFixed(4)}`
  return `$${n.toFixed(2)}`
}

function Skeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="h-10 bg-gray-800 rounded animate-pulse" />
      ))}
    </div>
  )
}

export default function History() {
  const sessions = useQuery(api.bot.listSessions, { limit: 50 })
  const [expanded, setExpanded] = useState<string | null>(null)

  return (
    <div className="flex flex-col gap-4 max-w-5xl">
      <h1 className="text-xl font-semibold">History</h1>

      {sessions === undefined && <Skeleton />}

      {sessions !== undefined && (sessions as Session[]).length === 0 && (
        <p className="text-gray-500">No sessions yet.</p>
      )}

      {sessions !== undefined && (sessions as Session[]).length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-gray-400 border-b border-gray-800">
                <th className="text-left py-2 pr-4 font-medium">Date</th>
                <th className="text-left py-2 pr-4 font-medium">Goal</th>
                <th className="text-right py-2 pr-4 font-medium">Comments</th>
                <th className="text-right py-2 pr-4 font-medium">Likes</th>
                <th className="text-right py-2 pr-4 font-medium">DMs</th>
                <th className="text-right py-2 pr-4 font-medium">Follows</th>
                <th className="text-right py-2 pr-4 font-medium">Steps</th>
                <th className="text-right py-2 pr-4 font-medium">Tokens</th>
                <th className="text-right py-2 pr-4 font-medium">Cost</th>
                <th className="text-right py-2 pr-4 font-medium">Duration</th>
                <th className="text-left py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(sessions as Session[]).map((s) => (
                <SessionRow
                  key={s._id}
                  session={s}
                  expanded={expanded === s._id}
                  onToggle={() => setExpanded(expanded === s._id ? null : s._id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function SessionRow({
  session: s,
  expanded,
  onToggle,
}: {
  session: Session
  expanded: boolean
  onToggle: () => void
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-gray-800 hover:bg-gray-800 cursor-pointer transition-colors"
      >
        <td className="py-2 pr-4 text-gray-400">{new Date(s.date).toLocaleString()}</td>
        <td className="py-2 pr-4 max-w-xs truncate">{s.goal}</td>
        <td className="py-2 pr-4 text-right">{s.comments}</td>
        <td className="py-2 pr-4 text-right">{s.likes}</td>
        <td className="py-2 pr-4 text-right">{s.dms}</td>
        <td className="py-2 pr-4 text-right">{s.follows}</td>
        <td className="py-2 pr-4 text-right">{s.steps}</td>
        <td className="py-2 pr-4 text-right text-gray-400">{fmtTokens(s.total_tokens)}</td>
        <td className="py-2 pr-4 text-right text-emerald-400">{fmtCost(s.cost_usd)}</td>
        <td className="py-2 pr-4 text-right">{s.duration}m</td>
        <td className="py-2">
          <span
            className={`px-2 py-0.5 rounded-full text-xs ${
              s.status === 'done'
                ? 'bg-green-900 text-green-300'
                : s.status === 'failed'
                ? 'bg-red-900 text-red-300'
                : 'bg-gray-700 text-gray-300'
            }`}
          >
            {s.status}
          </span>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={11} className="px-4 py-3 bg-gray-800/50">
            <div className="text-sm text-gray-300 mb-2 break-words">{s.goal}</div>
            {s.total_tokens ? (
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
                <div>
                  <div className="text-gray-500">Model</div>
                  <div className="text-gray-200 font-mono">{s.model || '—'}</div>
                </div>
                <div>
                  <div className="text-gray-500">API calls</div>
                  <div className="text-gray-200">{s.api_calls ?? '—'}</div>
                </div>
                <div>
                  <div className="text-gray-500">Input tokens</div>
                  <div className="text-gray-200">{(s.input_tokens ?? 0).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-gray-500">Output tokens</div>
                  <div className="text-gray-200">{(s.output_tokens ?? 0).toLocaleString()}</div>
                </div>
                <div>
                  <div className="text-gray-500">Cost</div>
                  <div className="text-emerald-400 font-medium">{fmtCost(s.cost_usd)}</div>
                </div>
              </div>
            ) : (
              <p className="text-gray-500 text-xs">
                No token usage recorded for this session (dry run, or it predates cost tracking).
              </p>
            )}
          </td>
        </tr>
      )}
    </>
  )
}
