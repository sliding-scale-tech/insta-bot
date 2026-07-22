import { useEffect, useState } from 'react'
import { useQuery, useMutation } from 'convex/react'
import { api } from '../../convex/_generated/api'
import {
  generateDayPlan,
  startDayPlan,
  cancelDayPlan,
  type PlannedSession,
} from '../lib/api'
import LogFeed from '../components/LogFeed'

const USER_ID = 'default' // Convex prefers the authenticated identity

interface PlanSession extends PlannedSession {
  status: 'pending' | 'running' | 'done' | 'error'
  attempts: number
  started_at?: number
  ended_at?: number
}

interface DayPlanDoc {
  _id: string
  raw_goal: string
  status: 'draft' | 'running' | 'done' | 'cancelled' | 'error'
  sessions: PlanSession[]
  current_index: number
  next_run_at?: number
  note?: string
}

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-gray-700 text-gray-300',
  running: 'bg-blue-900 text-blue-300 animate-pulse',
  done: 'bg-green-900 text-green-300',
  error: 'bg-red-900 text-red-300',
}

function Countdown({ to }: { to: number }) {
  const [now, setNow] = useState(Date.now())
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])
  const left = Math.max(0, Math.floor((to - now) / 1000))
  if (left <= 0) return <span className="text-green-400">starting…</span>
  const m = Math.floor(left / 60)
  const s = left % 60
  return (
    <span className="text-yellow-400 font-mono">
      break {m}m {String(s).padStart(2, '0')}s
    </span>
  )
}

export default function DayPlan() {
  const [dayGoal, setDayGoal] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [drafts, setDrafts] = useState<PlannedSession[] | null>(null)

  const plan = useQuery(api.dayplans.activePlan, { user_id: USER_ID }) as
    | DayPlanDoc
    | null
    | undefined
  const updateSessions = useMutation(api.dayplans.updateSessions)

  // Seed the editable draft list from the plan
  useEffect(() => {
    if (plan?.status === 'draft' && drafts === null) {
      setDrafts(plan.sessions.map((s) => ({ goal: s.goal, break_minutes: s.break_minutes })))
    }
    if (!plan || plan.status !== 'draft') setDrafts(null)
  }, [plan]) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleGenerate() {
    if (!dayGoal.trim()) return
    setBusy(true); setError('')
    try {
      const r = await generateDayPlan(dayGoal.trim())
      if (!r.created) setError(r.error || 'Could not generate a plan')
      setDrafts(null)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleStart() {
    if (!plan || !drafts) return
    setBusy(true)
    try {
      await updateSessions({ plan_id: plan._id as any, sessions: drafts })
      await startDayPlan(plan._id)
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  async function handleCancel() {
    if (!plan) return
    setBusy(true)
    try {
      await cancelDayPlan(plan._id)
    } finally {
      setBusy(false)
    }
  }

  const isDraft = plan?.status === 'draft'
  const isRunning = plan?.status === 'running'

  return (
    <div className="flex flex-col gap-5 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">Day Plan</h1>
        <p className="text-gray-400 text-sm mt-1">
          Describe the whole day once. It gets split into small, self-contained sessions
          with breaks between them — related actions on the same post stay together.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
          {error}
        </div>
      )}

      {/* Compose */}
      {!isRunning && (
        <div className="flex flex-col gap-2">
          <textarea
            value={dayGoal}
            onChange={(e) => setDayGoal(e.target.value)}
            placeholder="e.g. comment on 5 saloon posts in usa and like each of them, send 3 DMs to barbershops, like 20 saloon posts"
            className="w-full bg-gray-800 text-white rounded px-3 py-2 min-h-[90px] outline-none focus:ring-2 focus:ring-blue-500 resize-y text-sm"
          />
          <div>
            <button
              onClick={handleGenerate}
              disabled={busy || !dayGoal.trim()}
              className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium rounded px-5 py-2 transition-colors text-sm"
            >
              {busy ? 'Planning…' : 'Generate Plan'}
            </button>
          </div>
        </div>
      )}

      {plan === undefined && <p className="text-gray-500 text-sm">Loading…</p>}

      {plan && (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium text-gray-400">
              {isDraft ? 'Review & edit' : 'Today’s plan'}
            </h2>
            <span
              className={`text-xs px-2 py-0.5 rounded-full ${
                isRunning
                  ? 'bg-blue-900 text-blue-300'
                  : plan.status === 'done'
                  ? 'bg-green-900 text-green-300'
                  : 'bg-gray-700 text-gray-300'
              }`}
            >
              {plan.status}
            </span>
            {isRunning && plan.next_run_at && (
              <Countdown to={plan.next_run_at} />
            )}
          </div>

          {plan.note && <p className="text-xs text-gray-500">{plan.note}</p>}

          <div className="flex flex-col gap-2">
            {(isDraft && drafts ? drafts : plan.sessions).map((s, i) => {
              const live = plan.sessions[i]
              return (
                <div key={i} className="bg-gray-800 rounded px-3 py-2 flex items-start gap-3">
                  <span className="text-xs text-gray-500 mt-2 w-5 flex-shrink-0">{i + 1}</span>
                  <div className="flex-1 flex flex-col gap-2">
                    {isDraft && drafts ? (
                      <textarea
                        value={s.goal}
                        onChange={(e) => {
                          const next = [...drafts]
                          next[i] = { ...next[i], goal: e.target.value }
                          setDrafts(next)
                        }}
                        className="w-full bg-gray-900 text-gray-200 text-sm rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500 resize-y"
                      />
                    ) : (
                      <span className="text-sm text-gray-200">{s.goal}</span>
                    )}
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-gray-500">break after:</span>
                      {isDraft && drafts ? (
                        <input
                          type="number"
                          min={0}
                          value={s.break_minutes}
                          onChange={(e) => {
                            const next = [...drafts]
                            next[i] = { ...next[i], break_minutes: Number(e.target.value) }
                            setDrafts(next)
                          }}
                          className="w-16 bg-gray-900 text-gray-200 rounded px-2 py-0.5 outline-none"
                        />
                      ) : (
                        <span className="text-gray-300">{s.break_minutes}</span>
                      )}
                      <span className="text-gray-500">min</span>
                      {live && (
                        <span
                          className={`ml-auto px-2 py-0.5 rounded-full ${
                            STATUS_STYLE[live.status] ?? 'bg-gray-700 text-gray-300'
                          }`}
                        >
                          {live.status}
                          {live.attempts > 1 ? ` (retry ${live.attempts - 1})` : ''}
                        </span>
                      )}
                    </div>
                  </div>
                  {isDraft && drafts && drafts.length > 1 && (
                    <button
                      onClick={() => setDrafts(drafts.filter((_, j) => j !== i))}
                      className="text-gray-500 hover:text-red-400 text-xs mt-2"
                      title="Remove session"
                    >
                      ✕
                    </button>
                  )}
                </div>
              )
            })}
          </div>

          <div className="flex gap-3">
            {isDraft && (
              <button
                onClick={handleStart}
                disabled={busy || !drafts?.length}
                className="bg-green-600 hover:bg-green-700 disabled:opacity-40 text-white font-medium rounded px-5 py-2 transition-colors text-sm"
              >
                Start Day
              </button>
            )}
            {(isDraft || isRunning) && (
              <button
                onClick={handleCancel}
                disabled={busy}
                className="bg-red-700 hover:bg-red-600 disabled:opacity-40 text-white rounded px-4 py-2 transition-colors text-sm"
              >
                Cancel Plan
              </button>
            )}
          </div>
        </div>
      )}

      {plan === null && (
        <p className="text-gray-600 text-sm">
          No active plan. Describe your day above and hit Generate Plan.
        </p>
      )}

      <LogFeed />
    </div>
  )
}
