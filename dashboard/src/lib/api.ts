const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:8000'
const SIMPLE_TOKEN = import.meta.env.VITE_SECRET_TOKEN || ''
const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || ''

/** Returns the auth token — Clerk session token when signed in, else the
 *  simple token (empty unless VITE_SECRET_TOKEN is set for non-Clerk mode). */
export async function getToken(): Promise<string> {
  if (CLERK_KEY) {
    try {
      const clerk = (window as any).Clerk
      if (clerk?.session) return await clerk.session.getToken()
    } catch { /* fall through */ }
  }
  return SIMPLE_TOKEN
}

/** WS URL with the current auth token resolved and appended as ?token=.
 *  Always uses 127.0.0.1 to avoid the IPv6 localhost issue on Windows. */
export async function wsUrlAuthed(path: string): Promise<string> {
  const t = await getToken()
  return `${WS_BASE}${path}?token=${encodeURIComponent(t)}`
}

async function apiFetch(path: string, options: RequestInit = {}): Promise<unknown> {
  const token = await getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers ?? {}),
    },
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

/** Multipart POST — Content-Type is left for the browser to set (with the
 *  boundary), unlike apiFetch which always sends JSON. */
async function apiFetchForm(path: string, form: FormData): Promise<unknown> {
  const token = await getToken()
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export async function generateCaption(file: File, hint = ''): Promise<{ caption: string }> {
  const form = new FormData()
  form.append('file', file)
  form.append('hint', hint)
  return apiFetchForm('/api/caption/generate', form) as Promise<{ caption: string }>
}

export function startBot(goal: string) {
  return apiFetch('/api/bot/start', { method: 'POST', body: JSON.stringify({ goal }) })
}

export function stopBot() {
  return apiFetch('/api/bot/stop', { method: 'POST', body: JSON.stringify({}) })
}

export function botStatus() {
  return apiFetch('/api/bot/status')
}

export function getSessionUrl() {
  return apiFetch('/api/session/url')
}

export function logoutInstagram() {
  return apiFetch('/api/session/logout', { method: 'POST', body: JSON.stringify({}) })
}

export interface PromptDefault {
  key: string
  label: string
  description: string
  placeholders: string[]
  default: string
}

export function getPromptDefaults() {
  return apiFetch('/api/prompts/defaults') as Promise<{ prompts: PromptDefault[] }>
}

export interface SettingItem {
  key: string
  label: string
  description: string
  type: 'int' | 'str'
  default: number | string
  min?: number
  max?: number
  value: number | string
  is_custom: boolean
}

export function getSettings() {
  return apiFetch('/api/settings') as Promise<{ settings: SettingItem[] }>
}

export function updateSetting(key: string, value: string) {
  return apiFetch('/api/settings/update', {
    method: 'POST',
    body: JSON.stringify({ key, value }),
  })
}

export function resetSetting(key: string) {
  return apiFetch('/api/settings/reset', { method: 'POST', body: JSON.stringify({ key }) })
}

export interface PlannedSession {
  goal: string
  break_minutes: number
}

export function generateDayPlan(dayGoal: string, caps?: Record<string, number>) {
  return apiFetch('/api/plan/generate', {
    method: 'POST',
    body: JSON.stringify({ day_goal: dayGoal, caps }),
  }) as Promise<{ created: boolean; plan_id?: string; sessions?: PlannedSession[]; error?: string }>
}

export function startDayPlan(planId: string) {
  return apiFetch('/api/plan/start', { method: 'POST', body: JSON.stringify({ plan_id: planId }) })
}

export function cancelDayPlan(planId: string) {
  return apiFetch('/api/plan/cancel', { method: 'POST', body: JSON.stringify({ plan_id: planId }) })
}
