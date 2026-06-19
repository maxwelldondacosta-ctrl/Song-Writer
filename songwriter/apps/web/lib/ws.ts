import type { Song } from '@/types/song'

export const WS_BASE = (process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000').replace(/^http/, 'ws')

export type WSEvent =
  | { type: 'open' }
  | { type: 'snapshot'; song: Song | null }
  | { type: 'update'; song: Song; source?: 'external' | 'api' }
  | { type: 'closed' }
  | { type: 'error'; message: string }

export class WSConnection {
  private ws: WebSocket | null = null
  private retry = 0
  private stopped = false
  constructor(private slug: string, private onEvent: (e: WSEvent) => void) {}

  start() {
    this.stopped = false
    this.connect()
  }

  stop() {
    this.stopped = true
    this.ws?.close()
    this.ws = null
  }

  private connect() {
    const url = `${WS_BASE}/ws/songs/${this.slug}`
    const ws = new WebSocket(url)
    this.ws = ws
    ws.onopen = () => {
      this.retry = 0
      this.onEvent({ type: 'open' })
    }
    ws.onmessage = e => {
      try {
        const payload = JSON.parse(e.data)
        if (payload.type === 'snapshot' || payload.type === 'update') {
          this.onEvent(payload as WSEvent)
        }
      } catch {
        /* ignore */
      }
    }
    ws.onerror = () => this.onEvent({ type: 'error', message: 'ws error' })
    ws.onclose = () => {
      this.onEvent({ type: 'closed' })
      if (this.stopped) return
      const delay = Math.min(1000 * Math.pow(2, this.retry++), 10000)
      setTimeout(() => !this.stopped && this.connect(), delay)
    }
  }
}
