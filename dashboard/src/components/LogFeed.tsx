import { useEffect, useRef } from 'react'
import { useLogs } from '../lib/logs'

const FILTER_PATTERNS = [
  '->', '[DONE]', 'BLOCKED', 'FAILED', 'Starting', 'Session', 'Goal', '[db]',
  '[queued]', '[processing]', '[completed]', '[failed]', '[stopped]',
  '[plan]', '[planner]', '[safety]', '[warn]', '[session]', '[hashtag]',
]

function lineColor(line: string): string {
  if (/\[completed\]|->.*success|\[DONE\]/i.test(line)) return 'text-green-400'
  if (/\[failed\]|\[stopped\]|FAIL|error/i.test(line)) return 'text-red-400'
  if (/\[queued\]|\[warn\]|BLOCKED/i.test(line)) return 'text-yellow-400'
  if (/\[processing\]|\[plan\]|\[planner\]/i.test(line)) return 'text-blue-400'
  return 'text-gray-400'
}

export default function LogFeed({
  height = 'h-64',
  showAll = false,
}: {
  height?: string
  showAll?: boolean
}) {
  const { lines, connected } = useLogs()
  const bottomRef = useRef<HTMLDivElement>(null)

  const visible = showAll
    ? lines
    : lines.filter((l) => FILTER_PATTERNS.some((p) => l.includes(p)))

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [visible.length])

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <h2 className="text-sm font-medium text-gray-400">Live log</h2>
        <span
          className={`w-2 h-2 rounded-full ${
            connected ? 'bg-green-500' : 'bg-red-500 animate-pulse'
          }`}
          title={connected ? 'Connected' : 'Reconnecting…'}
        />
        <span className="text-xs text-gray-600">
          {connected ? 'live' : 'reconnecting…'}
        </span>
      </div>
      <div
        className={`bg-gray-950 rounded p-3 ${height} overflow-y-auto font-mono text-xs`}
      >
        {visible.length === 0 && (
          <p className="text-gray-600">Waiting for bot output…</p>
        )}
        {visible.map((line, i) => (
          <div key={i} className={lineColor(line)}>
            {line}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
