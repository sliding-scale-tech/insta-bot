import { useEffect, useState } from 'react'
import { getSettings, updateSetting, resetSetting, type SettingItem } from '../lib/api'

const GROUPS: { title: string; keys: string[] }[] = [
  {
    title: 'Session caps',
    keys: [
      'MAX_COMMENTS_PER_SESSION',
      'MAX_LIKES_PER_SESSION',
      'MAX_FOLLOWS_PER_SESSION',
      'MAX_DMS_PER_SESSION',
      'MAX_REPLIES_PER_SESSION',
      'SESSION_MINUTES',
    ],
  },
  {
    title: 'Niche fallback',
    keys: ['HASHTAG_TO_SEARCH'],
  },
  {
    title: 'Day plan',
    keys: [
      'PLAN_MIN_BREAK_MINUTES',
      'PLAN_MAX_BREAK_MINUTES',
      'DAILY_CAP_COMMENTS',
      'DAILY_CAP_LIKES',
      'DAILY_CAP_DMS',
      'DAILY_CAP_FOLLOWS',
    ],
  },
]

export default function Settings() {
  const [items, setItems] = useState<SettingItem[] | null>(null)
  const [drafts, setDrafts] = useState<Record<string, string>>({})
  const [saved, setSaved] = useState<Record<string, boolean>>({})
  const [error, setError] = useState('')

  function load() {
    getSettings()
      .then((r) => {
        setItems(r.settings)
        setDrafts(Object.fromEntries(r.settings.map((s) => [s.key, String(s.value)])))
      })
      .catch((e) => setError(String(e)))
  }

  useEffect(load, [])

  async function handleSave(item: SettingItem) {
    const value = drafts[item.key] ?? ''
    if (item.type === 'int') {
      const n = Number(value)
      if (!Number.isFinite(n)) {
        setError(`${item.label}: must be a number`)
        return
      }
    }
    setError('')
    await updateSetting(item.key, value)
    setSaved((s) => ({ ...s, [item.key]: true }))
    setTimeout(() => setSaved((s) => ({ ...s, [item.key]: false })), 2000)
    load()
  }

  async function handleReset(item: SettingItem) {
    await resetSetting(item.key)
    load()
  }

  if (error && !items) {
    return <p className="text-red-400 text-sm">Could not load settings: {error}</p>
  }
  if (!items) {
    return <p className="text-gray-500 text-sm">Loading settings…</p>
  }

  const byKey = Object.fromEntries(items.map((i) => [i.key, i]))

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-gray-400 text-sm mt-1">
          Session caps, timings, and day-plan defaults. Changes apply to the{' '}
          <span className="text-gray-200 font-medium">next</span> session or plan —
          no restart needed.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
          {error}
        </div>
      )}

      {GROUPS.map((group) => (
        <div key={group.title}>
          <h2 className="text-sm font-medium text-gray-400 mb-2">{group.title}</h2>
          <div className="flex flex-col gap-2">
            {group.keys.map((key) => {
              const item = byKey[key]
              if (!item) return null
              const value = drafts[key] ?? ''
              const dirty = value !== String(item.value)
              return (
                <div
                  key={key}
                  className="bg-gray-800 rounded-lg px-4 py-3 flex items-center gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-gray-200">{item.label}</span>
                      {item.is_custom && (
                        <span className="text-xs bg-blue-900 text-blue-300 px-1.5 py-0.5 rounded-full">
                          custom
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{item.description}</p>
                  </div>

                  {item.type === 'int' ? (
                    <input
                      type="number"
                      min={item.min}
                      max={item.max}
                      value={value}
                      onChange={(e) =>
                        setDrafts((d) => ({ ...d, [key]: e.target.value }))
                      }
                      className="w-20 bg-gray-900 text-gray-200 text-sm rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500 text-right"
                    />
                  ) : (
                    <input
                      type="text"
                      value={value}
                      onChange={(e) =>
                        setDrafts((d) => ({ ...d, [key]: e.target.value }))
                      }
                      className="w-40 bg-gray-900 text-gray-200 text-sm rounded px-2 py-1.5 outline-none focus:ring-1 focus:ring-blue-500"
                    />
                  )}

                  <div className="flex items-center gap-2 flex-shrink-0">
                    <button
                      onClick={() => handleSave(item)}
                      disabled={!dirty}
                      className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1.5 rounded transition-colors"
                    >
                      Save
                    </button>
                    <button
                      onClick={() => handleReset(item)}
                      disabled={!item.is_custom}
                      title={`Reset to default (${item.default})`}
                      className="text-xs bg-gray-700 hover:bg-gray-600 disabled:opacity-40 text-gray-200 px-3 py-1.5 rounded transition-colors"
                    >
                      Reset
                    </button>
                  </div>

                  {saved[key] && (
                    <span className="text-green-400 text-xs flex-shrink-0">Saved</span>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
