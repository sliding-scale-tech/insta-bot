import { useRef, useState } from 'react'
import { useMutation, useQuery } from 'convex/react'
import { api } from '../../convex/_generated/api'
import { generateCaption } from '../lib/api'

const USER_ID = 'default' // fallback; Convex prefers the authenticated identity

interface MediaPost {
  _id: string
  original_name: string
  caption: string
  status: 'pending' | 'posted' | 'error'
  uploaded_at: number
  posted_at?: number
  post_url?: string
  error?: string
  error_screenshot_url?: string | null
  preview_url: string | null
}

const STATUS_STYLE: Record<string, string> = {
  pending: 'bg-yellow-900 text-yellow-300',
  posted: 'bg-green-900 text-green-300',
  error: 'bg-red-900 text-red-300',
}

export default function Posts() {
  const [caption, setCaption] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [writingCaption, setWritingCaption] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  const posts = useQuery(api.media.listMediaPosts, { user_id: USER_ID }) as
    | MediaPost[]
    | undefined
  const generateUploadUrl = useMutation(api.media.generateUploadUrl)
  const createMediaPost = useMutation(api.media.createMediaPost)
  const deleteMediaPost = useMutation(api.media.deleteMediaPost)
  const retryMediaPost = useMutation(api.media.retryMediaPost)

  async function handleUpload() {
    if (!file) return
    setUploading(true)
    setError('')
    try {
      // Standard Convex file upload: get a one-time URL, POST bytes directly to
      // it (never through our backend), then record the post with the returned
      // storage id. Nothing touches VPS disk.
      const uploadUrl = await generateUploadUrl()
      const res = await fetch(uploadUrl, {
        method: 'POST',
        headers: { 'Content-Type': file.type },
        body: file,
      })
      if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
      const { storageId } = await res.json()

      await createMediaPost({
        user_id: USER_ID,
        storage_id: storageId,
        original_name: file.name,
        caption: caption.trim(),
      })

      setFile(null)
      setCaption('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (e) {
      setError(String(e))
    } finally {
      setUploading(false)
    }
  }

  async function handleWriteWithAI() {
    if (!file) {
      setError('Pick a photo first, then click Write with AI.')
      return
    }
    setWritingCaption(true)
    setError('')
    try {
      const { caption: generated } = await generateCaption(file, caption.trim())
      setCaption(generated)
    } catch (e) {
      setError(String(e))
    } finally {
      setWritingCaption(false)
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteMediaPost({ media_id: id as any })
    } catch (e) {
      setError(String(e))
    }
  }

  async function handleRetry(id: string) {
    try {
      await retryMediaPost({ media_id: id as any })
    } catch (e) {
      setError(String(e))
    }
  }

  const queued = (posts ?? []).filter((p) => p.status === 'pending' || p.status === 'error')
  const posted = (posts ?? []).filter((p) => p.status === 'posted')
  const pendingCount = (posts ?? []).filter((p) => p.status === 'pending').length
  const isVideo = !!file && /\.(mp4|mov)$/i.test(file.name)

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-semibold">Posts</h1>
        <p className="text-gray-400 text-sm mt-1">
          Upload photos/videos for the bot to post. Each upload is posted{' '}
          <span className="text-gray-200 font-medium">at most once</span> — once
          posted, it's marked done and never reused.
        </p>
      </div>

      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 text-xs px-3 py-2 rounded">
          {error}
        </div>
      )}

      {/* Upload form */}
      <div className="bg-gray-800 rounded-lg p-4 flex flex-col gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,video/mp4,video/quicktime"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-gray-300 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:bg-blue-600 file:text-white file:text-sm hover:file:bg-blue-700 file:cursor-pointer cursor-pointer"
        />
        <div className="relative">
          <textarea
            value={caption}
            onChange={(e) => setCaption(e.target.value)}
            placeholder="Caption for this post (optional) — or let AI write one from the photo"
            className="w-full bg-gray-900 text-gray-200 text-sm rounded px-3 py-2 pr-28 min-h-[70px] outline-none focus:ring-2 focus:ring-blue-500 resize-y"
          />
          <button
            onClick={handleWriteWithAI}
            disabled={!file || isVideo || writingCaption}
            title={isVideo ? 'AI captions only support photos right now' : undefined}
            className="absolute top-2 right-2 text-xs bg-purple-600 hover:bg-purple-700 disabled:opacity-40 text-white font-medium px-3 py-1.5 rounded transition-colors flex items-center gap-1"
          >
            {writingCaption ? (
              <>
                <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Writing…
              </>
            ) : (
              <>✨ Write with AI</>
            )}
          </button>
        </div>
        <div>
          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium rounded px-5 py-2 transition-colors text-sm"
          >
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>

      {/* Queue — not yet posted (pending or errored) */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <h2 className="text-sm font-medium text-gray-400">Queue</h2>
          {pendingCount > 0 && (
            <span className="text-xs text-yellow-400">{pendingCount} pending</span>
          )}
        </div>

        {posts === undefined ? (
          <p className="text-gray-600 text-sm">Loading…</p>
        ) : queued.length === 0 ? (
          <p className="text-gray-600 text-sm">
            Nothing queued. Upload a photo above — the bot posts the oldest
            pending upload when it runs a posting goal.
          </p>
        ) : (
          <PostGrid posts={queued} onDelete={handleDelete} onRetry={handleRetry} />
        )}
      </div>

      {/* Posted — already published, kept as history */}
      <div>
        <h2 className="text-sm font-medium text-gray-400 mb-2">Posted</h2>
        {posts === undefined ? null : posted.length === 0 ? (
          <p className="text-gray-600 text-sm">Nothing posted yet.</p>
        ) : (
          <PostGrid posts={posted} onDelete={handleDelete} onRetry={handleRetry} />
        )}
      </div>
    </div>
  )
}

function PostGrid({
  posts,
  onDelete,
  onRetry,
}: {
  posts: MediaPost[]
  onDelete: (id: string) => void
  onRetry: (id: string) => void
}) {
  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      {posts.map((p) => (
        <div key={p._id} className="bg-gray-800 rounded-lg overflow-hidden flex flex-col">
          <div className="bg-gray-950 aspect-square flex items-center justify-center overflow-hidden">
            {p.preview_url ? (
              /\.(mp4|mov)$/i.test(p.original_name) ? (
                <video src={p.preview_url} className="w-full h-full object-cover" muted />
              ) : (
                <img
                  src={p.preview_url}
                  alt={p.original_name}
                  className="w-full h-full object-cover"
                />
              )
            ) : (
              <span className="text-gray-600 text-xs">No preview</span>
            )}
          </div>
          <div className="p-3 flex flex-col gap-2 flex-1">
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLE[p.status]}`}>
                {p.status}
              </span>
              <span className="text-xs text-gray-500 truncate flex-1">{p.original_name}</span>
            </div>
            {p.caption && <p className="text-xs text-gray-400 line-clamp-2">{p.caption}</p>}
            {p.status === 'posted' && p.post_url && (
              <a
                href={p.post_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-blue-400 hover:underline truncate"
              >
                View on Instagram
              </a>
            )}
            {p.status === 'posted' && p.posted_at && (
              <p className="text-xs text-gray-500">
                Posted {new Date(p.posted_at).toLocaleString()}
              </p>
            )}
            {p.status === 'error' && p.error && (
              <p className="text-xs text-red-400 truncate" title={p.error}>
                {p.error}
              </p>
            )}
            {p.status === 'error' && p.error_screenshot_url && (
              <a
                href={p.error_screenshot_url}
                target="_blank"
                rel="noreferrer"
                className="block rounded overflow-hidden border border-red-800 hover:border-red-500 transition-colors"
                title="Screenshot at the moment posting failed — click to view full size"
              >
                <img
                  src={p.error_screenshot_url}
                  alt="Failure screenshot"
                  className="w-full h-24 object-cover object-top"
                />
              </a>
            )}
            <div className="mt-auto flex justify-end gap-3">
              {p.status === 'error' && (
                <button
                  onClick={() => onRetry(p._id)}
                  className="text-xs text-gray-400 hover:text-blue-400 transition-colors"
                >
                  Retry
                </button>
              )}
              <button
                onClick={() => onDelete(p._id)}
                className="text-xs text-gray-500 hover:text-red-400 transition-colors"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
