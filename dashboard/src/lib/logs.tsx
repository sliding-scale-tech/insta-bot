import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { wsUrlAuthed } from './api'

const MAX_LINES = 400

interface LogState {
  lines: string[]
  connected: boolean
  clear: () => void
}

const LogContext = createContext<LogState>({
  lines: [],
  connected: false,
  clear: () => {},
})

export function useLogs() {
  return useContext(LogContext)
}

/**
 * Owns the single /ws/log connection for the whole app.
 *
 * Mounted ABOVE the router, so switching tabs never unmounts it — logs and the
 * connection survive navigation. On a full page refresh the server replays its
 * rolling buffer, so history comes back too.
 */
export function LogProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)

  useEffect(() => {
    unmounted.current = false

    async function connect() {
      if (unmounted.current) return
      let url: string
      try {
        url = await wsUrlAuthed('/ws/log')
      } catch {
        reconnectTimer.current = setTimeout(connect, 3000)
        return
      }
      if (unmounted.current) return

      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (unmounted.current) { ws.close(); return }
        setConnected(true)
        // Server replays its buffer on connect — start clean so a refresh or
        // reconnect doesn't duplicate the replayed history.
        setLines([])
      }

      ws.onmessage = (event) => {
        if (unmounted.current) return
        const line: string = event.data
        setLines((prev) => {
          const next = [...prev, line]
          return next.length > MAX_LINES ? next.slice(-MAX_LINES) : next
        })
      }

      ws.onclose = () => {
        if (unmounted.current) return
        setConnected(false)
        reconnectTimer.current = setTimeout(connect, 2000)
      }

      ws.onerror = () => { /* onclose handles reconnect */ }
    }

    connect()

    return () => {
      unmounted.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [])

  return (
    <LogContext.Provider value={{ lines, connected, clear: () => setLines([]) }}>
      {children}
    </LogContext.Provider>
  )
}
