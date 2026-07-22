import { useState, ReactNode, lazy, Suspense } from 'react'

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || ''
const EXPECTED = import.meta.env.VITE_SECRET_TOKEN || ''
const LS_KEY = 'bot_dashboard_token'

// ── Simple token gate (no Clerk) ──────────────────────────────────────────────

function isTokenAuthed(): boolean {
  if (!EXPECTED) return true
  return localStorage.getItem(LS_KEY) === EXPECTED
}

function SimpleAuthGate({ children }: { children: ReactNode }) {
  const [authed, setAuthed] = useState(isTokenAuthed)
  const [input, setInput] = useState('')
  const [error, setError] = useState(false)

  if (authed) return <>{children}</>

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (input === EXPECTED) {
      localStorage.setItem(LS_KEY, input)
      setAuthed(true)
    } else {
      setError(true)
    }
  }

  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center">
      <form
        onSubmit={handleSubmit}
        className="bg-gray-800 rounded-xl p-8 flex flex-col gap-4 w-80 shadow-xl"
      >
        <h1 className="text-xl font-semibold text-white text-center">Bot Dashboard</h1>
        <input
          type="password"
          value={input}
          onChange={(e) => { setInput(e.target.value); setError(false) }}
          placeholder="Enter access token"
          className="bg-gray-700 text-white rounded px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
          autoFocus
        />
        {error && <p className="text-red-400 text-sm">Incorrect token.</p>}
        <button
          type="submit"
          className="bg-blue-600 hover:bg-blue-700 text-white font-medium rounded px-4 py-2 transition-colors"
        >
          Access Dashboard
        </button>
      </form>
    </div>
  )
}

// ── Clerk gate (only rendered when CLERK_KEY is set + ClerkProvider is present) ──

// Lazy-loaded so it only imports @clerk/clerk-react when needed
const ClerkGuardInner = lazy(() =>
  import('@clerk/clerk-react').then((mod) => {
    const { useAuth, SignIn } = mod

    function ClerkGuard({ children }: { children: ReactNode }) {
      const { isLoaded, isSignedIn } = useAuth()
      if (!isLoaded) {
        return (
          <div className="min-h-screen bg-gray-900 flex items-center justify-center text-gray-400">
            Loading...
          </div>
        )
      }
      if (!isSignedIn) {
        return (
          <div className="min-h-screen bg-gray-900 flex items-center justify-center">
            <SignIn routing="hash" />
          </div>
        )
      }
      return <>{children}</>
    }

    return { default: ClerkGuard }
  })
)

function ClerkAuthGate({ children }: { children: ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-900 flex items-center justify-center text-gray-400">
          Loading...
        </div>
      }
    >
      <ClerkGuardInner>{children}</ClerkGuardInner>
    </Suspense>
  )
}

// ── Export ────────────────────────────────────────────────────────────────────

export default function AuthGate({ children }: { children: ReactNode }) {
  if (CLERK_KEY) return <ClerkAuthGate>{children}</ClerkAuthGate>
  return <SimpleAuthGate>{children}</SimpleAuthGate>
}
