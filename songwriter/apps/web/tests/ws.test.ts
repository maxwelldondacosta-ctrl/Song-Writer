import { describe, it, expect, vi, beforeEach } from 'vitest'
import { WSConnection, type WSEvent } from '@/lib/ws'

class FakeWS {
  static instances: FakeWS[] = []
  url: string
  onopen: ((e: Event) => void) | null = null
  onmessage: ((e: MessageEvent) => void) | null = null
  onclose: ((e: CloseEvent) => void) | null = null
  onerror: ((e: Event) => void) | null = null
  readyState = 0
  constructor(url: string) {
    this.url = url
    FakeWS.instances.push(this)
    queueMicrotask(() => { this.readyState = 1; this.onopen?.(new Event('open')) })
  }
  send() {}
  close() { this.readyState = 3; this.onclose?.(new CloseEvent('close')) }
}

beforeEach(() => {
  FakeWS.instances = []
  // @ts-expect-error monkey-patch
  globalThis.WebSocket = FakeWS
})

describe('WSConnection', () => {
  it('opens with the right URL', async () => {
    const events: WSEvent[] = []
    const conn = new WSConnection('alpha', e => events.push(e))
    conn.start()
    await new Promise(r => setTimeout(r, 5))
    expect(FakeWS.instances[0].url).toBe('ws://localhost:8000/ws/songs/alpha')
    expect(events.some(e => e.type === 'open')).toBe(true)
    conn.stop()
  })

  it('forwards snapshot messages', async () => {
    const events: WSEvent[] = []
    const conn = new WSConnection('beta', e => events.push(e))
    conn.start()
    await new Promise(r => setTimeout(r, 5))
    const fws = FakeWS.instances[0]
    fws.onmessage?.(new MessageEvent('message', {
      data: JSON.stringify({ type: 'snapshot', song: { id: 'beta' } }),
    }))
    expect(events.some(e => e.type === 'snapshot')).toBe(true)
    conn.stop()
  })
})
