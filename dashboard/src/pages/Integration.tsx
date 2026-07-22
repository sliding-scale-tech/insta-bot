import MirrorView from '../components/MirrorView'
import { useState, useEffect } from 'react'
import { getSessionUrl } from '../lib/api'

export default function Integration() {
  const [url, setUrl] = useState('')

  useEffect(() => {
    const poll = setInterval(async () => {
      try {
        const data = await getSessionUrl() as { url: string }
        setUrl(data.url)
      } catch { /* ignore */ }
    }, 2000)
    return () => clearInterval(poll)
  }, [])

  const isHome =
    url.includes('instagram.com') && !url.includes('/accounts/')

  return (
    <div className="flex flex-col gap-4 max-w-5xl">
      <div>
        <h1 className="text-xl font-semibold">Integration — Browser Control</h1>
        <p className="text-gray-400 text-sm mt-1">
          Log in to Instagram here. Once you reach the home page, click Save Session.
        </p>
      </div>

      <MirrorView />

      <div className="flex items-center gap-3 text-sm">
        {isHome ? (
          <span className="text-green-400 font-medium">Home page reached!</span>
        ) : (
          <span className="text-gray-500 truncate max-w-xl">{url || 'Not connected'}</span>
        )}
      </div>
    </div>
  )
}
