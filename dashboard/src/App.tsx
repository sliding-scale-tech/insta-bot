import { Routes, Route, NavLink } from 'react-router-dom'
import { lazy, Suspense } from 'react'
import AuthGate from './components/AuthGate'
import { LogProvider } from './lib/logs'
import Integration from './pages/Integration'
import Bot from './pages/Bot'
import History from './pages/History'
import Analytics from './pages/Analytics'
import Prompts from './pages/Prompts'
import DayPlan from './pages/DayPlan'
import Posts from './pages/Posts'
import Settings from './pages/Settings'
import Info from './pages/Info'

const CLERK_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || ''

// Clerk avatar + sign-out menu, only when Clerk is configured.
const ClerkUserButton = lazy(() =>
  import('@clerk/clerk-react').then((mod) => {
    function UB() {
      return <mod.UserButton afterSignOutUrl="/" />
    }
    return { default: UB }
  })
)

function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      end={to === '/'}
      className={({ isActive }) =>
        `px-4 py-2 text-sm font-medium rounded transition-colors ${
          isActive
            ? 'bg-gray-700 text-white'
            : 'text-gray-400 hover:text-white hover:bg-gray-800'
        }`
      }
    >
      {label}
    </NavLink>
  )
}

export default function App() {
  return (
    <AuthGate>
      {/* Above the router: the log WebSocket survives tab switches */}
      <LogProvider>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <header className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
          <span className="font-semibold text-lg">Bot Dashboard</span>
          <nav className="flex gap-2">
            <NavTab to="/info" label="Info" />
            <NavTab to="/" label="Integration" />
            <NavTab to="/bot" label="Bot" />
            <NavTab to="/day-plan" label="Day Plan" />
            <NavTab to="/posts" label="Posts" />
            <NavTab to="/analytics" label="Analytics" />
            <NavTab to="/prompts" label="Prompts" />
            <NavTab to="/settings" label="Settings" />
            <NavTab to="/history" label="History" />
          </nav>
          {CLERK_KEY && (
            <div className="ml-auto flex items-center">
              <Suspense fallback={null}>
                <ClerkUserButton />
              </Suspense>
            </div>
          )}
        </header>
        <main className="p-6">
          <Routes>
            <Route path="/info" element={<Info />} />
            <Route path="/" element={<Integration />} />
            <Route path="/bot" element={<Bot />} />
            <Route path="/day-plan" element={<DayPlan />} />
            <Route path="/posts" element={<Posts />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/prompts" element={<Prompts />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/history" element={<History />} />
          </Routes>
        </main>
      </div>
      </LogProvider>
    </AuthGate>
  )
}
