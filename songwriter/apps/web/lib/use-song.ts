'use client'

import { useEffect, useRef, useState } from 'react'

import { api, ApiError } from '@/lib/api'
import { WSConnection } from '@/lib/ws'
import type { Song } from '@/types/song'

export type UseSongStatus = 'loading' | 'ready' | 'error' | 'disconnected'

export function useSong(slug: string | null) {
  const [song, setSong] = useState<Song | null>(null)
  const [status, setStatus] = useState<UseSongStatus>('loading')
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WSConnection | null>(null)

  useEffect(() => {
    if (!slug) return
    let cancelled = false
    setStatus('loading')

    api.getSong(slug)
      .then(s => { if (!cancelled) { setSong(s); setStatus('ready') } })
      .catch(err => { if (!cancelled) { setError(err instanceof ApiError ? err.message : String(err)); setStatus('error') } })

    const conn = new WSConnection(slug, e => {
      if (cancelled) return
      if (e.type === 'snapshot' && e.song) setSong(e.song)
      if (e.type === 'update') setSong(e.song)
      if (e.type === 'closed') setStatus('disconnected')
      if (e.type === 'open') setStatus(prev => (prev === 'disconnected' ? 'ready' : prev))
    })
    conn.start()
    wsRef.current = conn

    return () => {
      cancelled = true
      conn.stop()
    }
  }, [slug])

  return { song, setSong, status, error }
}
