import { useEffect, useState } from 'react'
import { useQuery } from 'convex/react'
import { api } from '../../convex/_generated/api'
import { startBot, stopBot, botStatus } from '../lib/api'
import LogFeed from '../components/LogFeed'

const USER_ID = 'default' // fallback; Convex prefers the authenticated identity

interface Job {
  _id: string
  goal: string
  status: 'pending' | 'processing' | 'done' | 'error'
  created_at: number
  started_at?: number
  ended_at?: number
  error?: string
}

const STATUS_STYLE: Record<Job['status'], string> = {
  pending: 'bg-yellow-900 text-yellow-300',
  processing: 'bg-blue-900 text-blue-300 animate-pulse',
  done: 'bg-green-900 text-green-300',
  error: 'bg-red-900 text-red-300',
}

export default function Bot() {
  const [goal, setGoal] = useState('')
  const [running, setRunning] = useState(false)

  const jobs = useQuery(api.jobs.listJobs, { user_id: USER_ID, limit: 30 }) as
    | Job[]
    | undefined
  const pendingCount = (jobs ?? []).filter((j) => j.status === 'pending').length
  const processing = (jobs ?? []).find((j) => j.status === 'processing')

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const s = (await botStatus()) as { running: boolean }
        setRunning(s.running)
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(poll)
  }, [])

  async function handleAdd() {
    if (!goal.trim()) return
    await startBot(goal.trim())
    setGoal('')
    setRunning(true)
  }

  async function handleStop() {
    await stopBot()
    setRunning(false)
  }

  const isBusy = running || !!processing

  return (
    <div className="flex flex-col gap-4 max-w-3xl">
      <h1 className="text-xl font-semibold">Bot</h1>

      <div className="flex gap-2">
        <input
          type="text"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          placeholder="comment on 3 posts and send 2 DMs"
          className="flex-1 bg-gray-800 text-white rounded px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleAdd}
          disabled={!goal.trim()}
          className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-medium rounded px-5 py-2 transition-colors whitespace-nowrap"
        >
          {isBusy ? 'Queue Goal' : 'Run'}
        </button>
        <button
          onClick={handleStop}
          disabled={!isBusy}
          className="bg-red-600 hover:bg-red-700 disabled:opacity-40 text-white font-medium rounded px-5 py-2 transition-colors"
        >
          Stop
        </button>
      </div>

      <div className="flex items-center gap-3 text-sm">
        <span
          className={`font-medium px-3 py-1 rounded-full ${
            isBusy ? 'bg-green-900 text-green-300' : 'bg-gray-700 text-gray-400'
          }`}
        >
          {processing ? 'Running' : isBusy ? 'Running' : 'Idle'}
        </span>
        {pendingCount > 0 && (
          <span className="text-yellow-400">{pendingCount} queued</span>
        )}
        {processing && (
          <span className="text-gray-400 truncate">→ {processing.goal}</span>
        )}
      </div>

      {/* Goal queue */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Goals</h2>
        {jobs === undefined ? (
          <p className="text-gray-600 text-sm">Loading…</p>
        ) : jobs.length === 0 ? (
          <p className="text-gray-600 text-sm">No goals yet. Type one above and hit Run.</p>
        ) : (
          <div className="flex flex-col gap-2">
            {jobs.map((j) => (
              <div
                key={j._id}
                className="flex items-center gap-3 bg-gray-800 rounded px-3 py-2"
              >
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0 ${STATUS_STYLE[j.status]}`}
                >
                  {j.status}
                </span>
                <span className="text-sm text-gray-200 flex-1 truncate">{j.goal}</span>
                <span className="text-xs text-gray-500 flex-shrink-0">
                  {new Date(j.created_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      <LogFeed />
    </div>
  )
}
