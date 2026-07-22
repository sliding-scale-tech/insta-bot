import { useEffect, useState } from 'react'
import { useQuery, useMutation } from 'convex/react'
import { api } from '../../convex/_generated/api'
import { getPromptDefaults, type PromptDefault } from '../lib/api'

interface StoredPrompt {
  _id: string
  key: string
  content: string
  updated_at: number
}

export default function Prompts() {
  const [defaults, setDefaults] = useState<PromptDefault[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})
  const [error, setError] = useState('')

  const stored = useQuery(api.prompts.listPrompts) as StoredPrompt[] | undefined
  const upsert = useMutation(api.prompts.upsertPrompt)
  const reset = useMutation(api.prompts.resetPrompt)

  useEffect(() => {
    getPromptDefaults()
      .then((r) => setDefaults(r.prompts))
      .catch((e) => setError(String(e)))
  }, [])

  // Seed editors: DB override if present, else the built-in default.
  useEffect(() => {
    if (!defaults || stored === undefined) return
    const byKey = Object.fromEntries(stored.map((s) => [s.key, s.content]))
    setDrafts((prev) => {
      const next = { ...prev }
      for (const d of defaults) {
        if (next[d.key] === undefined) next[d.key] = byKey[d.key] ?? d.default
      }
      return next
    })
  }, [defaults, stored])

  async function handleSave(key: string) {
    await upsert({ key, content: drafts[key] ?? '' })
    setSaved((s) => ({ ...s, [key]: true }))
    setTimeout(() => setSaved((s) => ({ ...s, [key]: false })), 2000)
  }

  async function handleReset(key: string, def: string) {
    await reset({ key })
    setDrafts((d) => ({ ...d, [key]: def }))
  }

  if (error) {
    return <p className="text-red-400 text-sm">Could not load prompts: {error}</p>
  }
  if (!defaults) {
    return <p className="text-gray-500 text-sm">Loading prompts…</p>
  }

  const overridden = new Set((stored ?? []).map((s) => s.key))

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold">Prompts</h1>
        <p className="text-gray-400 text-sm mt-1">
          These are the live prompts the bot uses. Edits save to the database and are
          picked up by the automation backend on its next run — no redeploy needed.
        </p>
      </div>

      {defaults.map((p) => {
        const value = drafts[p.key] ?? ''
        const isOverridden = overridden.has(p.key)
        const dirty = value !== (stored?.find((s) => s.key === p.key)?.content ?? p.default)
        return (
          <div key={p.key} className="bg-gray-800 rounded-lg p-4 flex flex-col gap-3">
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h2 className="font-medium text-white">{p.label}</h2>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      isOverridden
                        ? 'bg-blue-900 text-blue-300'
                        : 'bg-gray-700 text-gray-400'
                    }`}
                  >
                    {isOverridden ? 'custom' : 'default'}
                  </span>
                </div>
                <p className="text-gray-400 text-xs mt-1">{p.description}</p>
              </div>
            </div>

            {p.placeholders.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {p.placeholders.map((ph) => (
                  <code
                    key={ph}
                    className="text-[11px] bg-gray-900 text-emerald-300 px-1.5 py-0.5 rounded"
                    title="Placeholder — replaced at runtime"
                  >
                    {`{${ph}}`}
                  </code>
                ))}
              </div>
            )}

            <textarea
              value={value}
              onChange={(e) => setDrafts((d) => ({ ...d, [p.key]: e.target.value }))}
              spellCheck={false}
              className="w-full bg-gray-950 text-gray-200 font-mono text-xs rounded p-3 min-h-[220px] outline-none focus:ring-2 focus:ring-blue-500 resize-y"
            />

            <div className="flex items-center gap-3">
              <button
                onClick={() => handleSave(p.key)}
                disabled={!dirty}
                className="text-sm bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-4 py-1.5 rounded transition-colors"
              >
                Save
              </button>
              <button
                onClick={() => handleReset(p.key, p.default)}
                disabled={!isOverridden}
                className="text-sm bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-200 px-4 py-1.5 rounded transition-colors"
              >
                Reset to default
              </button>
              {saved[p.key] && <span className="text-green-400 text-xs">Saved</span>}
              {dirty && !saved[p.key] && (
                <span className="text-yellow-400 text-xs">Unsaved changes</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
