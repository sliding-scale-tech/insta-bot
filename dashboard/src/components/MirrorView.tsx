import { useEffect, useRef, useState } from 'react'
import { wsUrlAuthed, logoutInstagram } from '../lib/api'

type BrowserState =
  | 'disconnected'
  | 'idle'
  | 'starting'
  | 'ready'
  | 'saving'
  | 'saved'
  | 'session_ready'
  | 'bot_running'

export default function MirrorView() {
  const imgRef = useRef<HTMLImageElement>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const prevObjectUrl = useRef<string | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmounted = useRef(false)

  const [browserState, setBrowserState] = useState<BrowserState>('disconnected')
  const [currentUrl, setCurrentUrl] = useState('')
  const [error, setError] = useState('')

  // States where the mirror browser is NOT live (a full-screen panel is shown)
  const isPanel = (s: BrowserState) =>
    s === 'saved' || s === 'session_ready' || s === 'bot_running'

  async function connect() {
    if (unmounted.current) return
    const url = await wsUrlAuthed('/ws/mirror')
    if (unmounted.current) return
    const ws = new WebSocket(url)
    ws.binaryType = 'blob'
    wsRef.current = ws

    ws.onopen = () => {
      if (unmounted.current) { ws.close(); return }
      setError('')
    }

    ws.onclose = () => {
      if (unmounted.current) return
      setBrowserState(prev => (isPanel(prev) ? prev : 'disconnected'))
      reconnectTimer.current = setTimeout(() => connect(), 2000)
    }

    ws.onerror = () => { /* onclose fires right after */ }

    ws.onmessage = (event) => {
      if (unmounted.current) return
      if (event.data instanceof Blob) {
        setBrowserState(prev => (prev === 'saved' ? 'saved' : 'ready'))
        const url = URL.createObjectURL(event.data as Blob)
        if (imgRef.current) imgRef.current.src = url
        if (prevObjectUrl.current) URL.revokeObjectURL(prevObjectUrl.current)
        prevObjectUrl.current = url
        return
      }
      try {
        const msg = JSON.parse(event.data as string)
        if (msg.type === 'status') {
          if (msg.msg === 'bot_running') setBrowserState('bot_running')
          else if (msg.msg === 'session_ready')
            setBrowserState(prev => (prev === 'saved' ? 'saved' : 'session_ready'))
          else if (msg.msg === 'idle')
            setBrowserState(prev => (prev === 'saved' ? 'saved' : 'idle'))
          else if (msg.msg === 'starting')
            setBrowserState(prev => (prev === 'saved' ? 'saved' : 'starting'))
        } else if (msg.type === 'url') {
          setCurrentUrl(msg.url)
        } else if (msg.type === 'session_saved') {
          setBrowserState('saved')
        } else if (msg.type === 'error') {
          setError(msg.msg || 'Unknown error')
          setBrowserState('ready')
        }
      } catch { /* ignore */ }
    }
  }

  function startBrowser() {
    wsRef.current?.send(JSON.stringify({ type: 'start_browser' }))
    setBrowserState('starting')
  }

  function saveSession() {
    if (browserState !== 'ready') return
    setBrowserState('saving')
    wsRef.current?.send(JSON.stringify({ type: 'save_session' }))
  }

  async function logout() {
    try {
      await logoutInstagram()
    } catch { /* ignore */ }
    setCurrentUrl('')
    setBrowserState('idle')
  }

  useEffect(() => {
    unmounted.current = false
    connect()
    return () => {
      unmounted.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [])

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (browserState !== 'ready') return
      if (
        document.activeElement !== containerRef.current &&
        !containerRef.current?.contains(document.activeElement)
      ) return
      wsRef.current?.send(JSON.stringify({ type: 'key', key: e.key }))
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [browserState])

  function handleClick(e: React.MouseEvent<HTMLImageElement>) {
    if (!imgRef.current || browserState !== 'ready') return
    const rect = imgRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left) * (1280 / rect.width)
    const y = (e.clientY - rect.top) * (800 / rect.height)
    wsRef.current?.send(JSON.stringify({ type: 'click', x, y }))
  }

  function handleWheel(e: React.WheelEvent<HTMLImageElement>) {
    if (!imgRef.current || browserState !== 'ready') return
    const rect = imgRef.current.getBoundingClientRect()
    wsRef.current?.send(
      JSON.stringify({ type: 'scroll', x: e.clientX - rect.left, y: e.clientY - rect.top, deltaY: e.deltaY })
    )
  }

  // ── Bot running — mirror parked to avoid two live browsers ──────────────────
  if (browserState === 'bot_running') {
    return (
      <div className="flex flex-col items-center justify-center gap-4 py-16 text-center">
        <div className="flex items-center gap-2 text-green-400">
          <span className="w-2.5 h-2.5 rounded-full bg-green-500 animate-pulse inline-block" />
          <span className="font-semibold">Bot is running</span>
        </div>
        <p className="text-gray-400 text-sm max-w-sm">
          The live mirror is paused while the bot drives its own browser.
          Watch progress and logs on the <span className="text-gray-200 font-medium">Bot</span> tab.
        </p>
      </div>
    )
  }

  // ── Connected — session active (either just saved, or already logged in) ────
  if (browserState === 'saved' || browserState === 'session_ready') {
    const justSaved = browserState === 'saved'
    return (
      <div className="flex flex-col items-center justify-center gap-6 py-16 text-center">
        <div className="w-16 h-16 rounded-full bg-green-500/20 flex items-center justify-center">
          <svg className="w-8 h-8 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <div>
          <h2 className="text-xl font-semibold text-white">
            {justSaved ? 'Connected Successfully' : 'Connected to Instagram'}
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            {justSaved
              ? 'Instagram session saved — the bot can now run.'
              : 'Your Instagram session is active — the bot can run.'}
          </p>
        </div>
        <div className="flex gap-3 mt-2">
          <button
            onClick={startBrowser}
            className="text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 px-4 py-2 rounded transition-colors"
          >
            Open Browser Mirror
          </button>
          <button
            onClick={logout}
            className="text-sm bg-red-700 hover:bg-red-600 text-white px-4 py-2 rounded transition-colors"
          >
            Log out of Instagram
          </button>
        </div>
      </div>
    )
  }

  // ── Status bar ─────────────────────────────────────────────────────────────
  const statusDot =
    browserState === 'ready' || browserState === 'saving'
      ? 'bg-green-500'
      : browserState === 'idle'
      ? 'bg-green-400'
      : browserState === 'starting'
      ? 'bg-yellow-400 animate-pulse'
      : 'bg-red-500'

  const statusLabel =
    browserState === 'saving'
      ? 'Saving session...'
      : browserState === 'ready'
      ? currentUrl || 'instagram.com'
      : browserState === 'idle'
      ? 'No Instagram session — start the browser to log in'
      : browserState === 'starting'
      ? 'Browser starting...'
      : 'Connecting to server...'

  // ── Overlay ────────────────────────────────────────────────────────────────
  const overlayContent: React.ReactNode =
    browserState === 'disconnected' ? (
      <span>Connecting to server...</span>
    ) : browserState === 'idle' ? (
      <div className="flex flex-col items-center gap-4">
        <span className="text-gray-300 text-sm">Log in to Instagram to get started</span>
        <button
          onClick={startBrowser}
          className="bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white font-medium px-6 py-2.5 rounded-lg transition-colors text-sm"
        >
          Start Browser
        </button>
      </div>
    ) : browserState === 'starting' ? (
      <span>Browser starting — please wait...</span>
    ) : browserState === 'saving' ? (
      <div className="flex flex-col items-center gap-3">
        <svg className="w-6 h-6 text-blue-400 animate-spin" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        <span className="text-gray-300 text-sm">Saving session...</span>
      </div>
    ) : null

  return (
    <div ref={containerRef} tabIndex={0} className="outline-none flex flex-col gap-2">
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
          {error}
        </div>
      )}

      <div className="flex items-center gap-3 bg-gray-800 rounded px-3 py-2">
        <span className={`w-2 h-2 rounded-full flex-shrink-0 ${statusDot}`} />
        <span className="text-xs text-gray-400 flex-1 truncate">{statusLabel}</span>
        <button
          onClick={saveSession}
          disabled={browserState !== 'ready'}
          className="text-xs bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white px-3 py-1 rounded transition-colors"
        >
          Save Session
        </button>
      </div>

      <div className="relative">
        {overlayContent && (
          <div className="absolute inset-0 flex items-center justify-center bg-gray-900/80 z-10 rounded text-gray-400 text-sm">
            {overlayContent}
          </div>
        )}
        <img
          ref={imgRef}
          alt="Browser mirror"
          onClick={handleClick}
          onWheel={handleWheel}
          className="w-full object-contain cursor-crosshair rounded max-h-[800px] bg-gray-950"
          style={{ minHeight: overlayContent ? '400px' : undefined }}
        />
      </div>
    </div>
  )
}
