# Songwriter Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a polished Next.js 15 web UI at `apps/web/` that pairs with the FastAPI backend and the Claude Code skill. The UI is the visual editing surface — it never makes LLM calls. It reads/writes song JSON via the API and live-updates over WebSocket. Phase 1 ships Home, Wizard, and Song Editor (with Vocab + Suno tabs); Songwriter Profiles / Descriptors / Vocab Browser are Phase 2.

**Architecture:** Next.js 15 (app router) + TypeScript + Tailwind v4 + shadcn/ui. Fonts: Geist for UI, EB Garamond for the lyric editor. Dark mode default. Server components for static pages; client components for the editor canvas. A typed API client at `lib/api.ts` wraps every endpoint. A `useSong(slug)` hook subscribes to the per-song WebSocket and keeps local state in sync. Vitest + Testing Library for unit tests.

**Tech Stack:** Next.js 15, TypeScript 5, Tailwind v4, shadcn/ui (Radix + Tailwind components), Lucide icons, Zod (response parsing), Vitest, @testing-library/react, jsdom, msw (mock service worker for component tests).

**Scope boundary:** Phase 1 ships Home + Wizard + Song Editor (with Vocab + Suno tabs). Songwriter profile browser, sonic descriptor library, vocab bank explorer pages are Phase 2 — placeholder routes that link out are fine.

**Sister plans:**
- ✅ `2026-04-30-songwriter-data-layer.md` — done
- ✅ `2026-04-30-songwriter-fastapi.md` — done
- ✅ `2026-04-30-songwriter-skill.md` — done

**Decisions baked in:**
- The API URL and WS URL are hardcoded to `http://localhost:8000` and `ws://localhost:8000` for Phase 1 (with override via `NEXT_PUBLIC_API_BASE` env var). No deployment story.
- The UI never makes LLM calls. Every "smart" thing routes to the API, which either returns DB data or routes through the skill via `claude --print`.
- The Song JSON shape is the cross-plan contract. We codegen TypeScript types from the Python pydantic models — but for Phase 1 we manually mirror the schema in `types/song.ts` and keep them in sync. (Future: generate from OpenAPI.)
- All UI mutations go through the API (`PUT /songs/{slug}`). The optimistic-update pattern: write to local state immediately, send the PUT, reconcile on response. WebSocket broadcasts that come back from the API are deduplicated against `last_modified_by === "ui"` so we don't loop.
- The skill writes JSON directly (file watcher catches it); those writes arrive via WebSocket as `{"type":"update","source":"external"}` and the UI accepts them wholesale.

---

## File Structure

```
songwriter/apps/web/
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── tailwind.config.ts
├── components.json                  # shadcn config
├── vitest.config.ts
├── .env.local.example               # NEXT_PUBLIC_API_BASE
├── app/
│   ├── globals.css
│   ├── layout.tsx                   # root layout, fonts, theme
│   ├── page.tsx                     # / Home / Song Library
│   ├── songs/
│   │   ├── new/
│   │   │   └── page.tsx             # /songs/new — wizard
│   │   └── [slug]/
│   │       └── page.tsx             # /songs/[slug] — editor (client component)
│   ├── songwriters/page.tsx         # placeholder (Phase 2)
│   ├── descriptors/page.tsx         # placeholder
│   ├── vocab/page.tsx               # placeholder
│   └── settings/page.tsx            # basic
├── components/
│   ├── ui/                          # shadcn-generated (button, card, input, etc.)
│   ├── nav.tsx                      # top nav
│   ├── song-card.tsx                # used on Home
│   ├── wizard/
│   │   ├── wizard.tsx               # orchestrator
│   │   ├── step-genre.tsx
│   │   ├── step-sub-genre.tsx
│   │   ├── step-topic.tsx
│   │   ├── step-emotion.tsx
│   │   ├── step-lens.tsx
│   │   └── step-review.tsx
│   ├── editor/
│   │   ├── editor.tsx               # 3-pane layout
│   │   ├── section-list.tsx         # left rail
│   │   ├── lyric-canvas.tsx         # center
│   │   ├── validation-chips.tsx     # per-section badges
│   │   ├── right-rail.tsx           # tabs container
│   │   ├── tab-vocab.tsx
│   │   ├── tab-suno.tsx
│   │   ├── tab-rhymes.tsx           # placeholder shell
│   │   ├── tab-cadence.tsx          # placeholder shell
│   │   ├── tab-notes.tsx
│   │   └── production-bar.tsx       # bottom bar
│   └── theme-provider.tsx
├── lib/
│   ├── api.ts                       # typed API client
│   ├── ws.ts                        # WebSocket helper
│   ├── use-song.ts                  # subscription hook
│   ├── slug.ts                      # title → slug helper
│   └── cn.ts                        # classnames helper (shadcn convention)
├── types/
│   └── song.ts                      # mirror of api/schemas.py
└── tests/
    ├── api.test.ts                  # api client unit tests (msw)
    ├── ws.test.ts                   # WS reconnect logic
    ├── slug.test.ts
    ├── components/
    │   ├── song-card.test.tsx
    │   ├── wizard.test.tsx
    │   └── lyric-canvas.test.tsx
    └── setup.ts                     # vitest setup (jest-dom)
```

---

## Conventions

- One commit per task. TDD where it pays: API client, WS hook, slug helper, key components. Visual styling tested via build + manual smoke.
- Commit message format: `feat(ui): <subject>`, `chore(ui): <subject>`, `test(ui): <subject>`.
- shadcn components are generated via `npx shadcn@latest add <name>`. Don't hand-write `components/ui/*` — let the generator put them there.
- TypeScript strict mode on. No `any` outside test mocks.
- Tailwind v4 (CSS-first config). Dark mode is default.

---

## Task 1: Next.js scaffold + Tailwind + shadcn/ui + Vitest

**Files:** create the entire `apps/web/` skeleton.

- [ ] **Step 1: Bootstrap Next.js**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
mkdir -p apps
cd apps
npx --yes create-next-app@latest web \
  --typescript --tailwind --app --eslint --src-dir=false \
  --import-alias "@/*" --no-turbopack --use-npm --yes
cd web
```

- [ ] **Step 2: Install shadcn/ui + dependencies**

```bash
npx --yes shadcn@latest init -d --yes --base-color zinc
npx --yes shadcn@latest add -y button card input label select textarea badge tabs dialog tooltip toast separator scroll-area
npm i lucide-react zod
npm i -D vitest @testing-library/react @testing-library/jest-dom jsdom msw @vitejs/plugin-react
```

- [ ] **Step 3: Configure Vitest**

File: `apps/web/vitest.config.ts`

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    globals: true,
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, '.') },
  },
})
```

File: `apps/web/tests/setup.ts`

```ts
import '@testing-library/jest-dom'
```

In `package.json` scripts:

```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "next lint",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

- [ ] **Step 4: Tailwind v4 dark-mode default + fonts**

File: `apps/web/app/globals.css` — add at top (preserve shadcn-generated content underneath):

```css
@import "tailwindcss";

@theme {
  --font-sans: 'Geist', ui-sans-serif, system-ui, sans-serif;
  --font-serif: 'EB Garamond', ui-serif, Georgia, serif;
}

html { color-scheme: dark; }
html, body { background: hsl(var(--background)); color: hsl(var(--foreground)); }
```

(Keep the shadcn-generated `:root` and `.dark` color variables. Set `class="dark"` on `<html>` in `app/layout.tsx`.)

- [ ] **Step 5: Sanity test**

File: `apps/web/tests/setup.test.ts`

```ts
import { describe, it, expect } from 'vitest'

describe('vitest setup', () => {
  it('runs', () => {
    expect(1 + 1).toBe(2)
  })
})
```

```bash
npm test -- --run
```

Expected: 1 test passing.

- [ ] **Step 6: Build sanity check**

```bash
npm run build
```

Expected: clean build, no type errors. Default Next.js home page renders.

- [ ] **Step 7: Commit (from repo root)**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web
git commit -m "chore(ui): scaffold Next.js + Tailwind + shadcn/ui + Vitest"
```

---

## Task 2: Song types + API client + slug helper

**Files:**
- Create: `apps/web/types/song.ts`
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/lib/slug.ts`
- Create: `apps/web/tests/api.test.ts`
- Create: `apps/web/tests/slug.test.ts`

A typed wrapper over `fetch` that mirrors every API endpoint. Tests use msw to mock HTTP.

- [ ] **Step 1: Types**

File: `apps/web/types/song.ts`

```ts
export type LockState = 'draft' | 'edited' | 'locked'
export type RuleResult = 'pass' | 'warn' | 'fail' | 'unrun'
export type Role =
  | 'pure-songwriter'
  | 'producer-songwriter'
  | 'singer-songwriter'
  | 'self-writing-artist'

export interface IntentStory { event: string; emotion: string; resolution: string }
export interface Intent { topic: string; emotion_arc: string; story: IntentStory }
export interface Production { bpm: number; structure_template: string; energy_curve: number[] }
export interface SectionValidation {
  singability: RuleResult
  cadence: RuleResult
  phonetic_texture: RuleResult
  rhyme_cadence: RuleResult
  story_sentence: RuleResult
  warnings: string[]
}
export interface Section {
  id: string
  label: string
  lock_state: LockState
  lyrics: string[]
  cadence_pattern: string
  validation: SectionValidation
  phonetic_overlay: unknown[]
}
export interface SunoPrompt { current: string; history: unknown[] }
export interface SongRequest {
  type: 'suggest_alternatives' | 'tighten_cadence' | 'rewrite_section' | 'regen_descriptor'
  section?: string
  line?: number
  count?: number
  constraint?: string
  payload?: Record<string, unknown>
}
export interface Song {
  id: string
  title: string
  created: string
  modified: string
  genre: string
  sub_genre: string
  songwriter_lens: string | null
  intent: Intent
  production: Production
  sections: Section[]
  suno_prompt: SunoPrompt
  requests: SongRequest[]
  notes: string
  last_modified_by: 'ui' | 'skill' | 'api'
}

export interface Genre {
  id: number
  slug: string
  name: string
  typical_bpm_min: number | null
  typical_bpm_max: number | null
  description: string | null
  sub_genres?: SubGenre[]
}
export interface SubGenre {
  id: number
  slug: string
  name: string
  typical_bpm_min: number | null
  typical_bpm_max: number | null
  parent_slug?: string
}
export interface SongwriterProfile {
  slug: string
  display_name: string
  role: Role
  primary_genre_slug: string
  craft_signature: string[]
  hook_style: string | null
  adoption_prompt: string
  vocab_fingerprint?: Record<string, unknown>
  preferred_cadences?: string[]
}
export interface CadencePattern {
  slug: string
  name: string
  syllable_template: string
  stress_template: string
  typical_genres: string[]
  example_lines: string[]
  rhyme_compatibility: { end?: string[]; internal?: string }
}
export interface VocabBankWord {
  word: string
  ipa: string
  syllables: number
  stress_pattern: string
  rhyme_class: string
  vowel_shape: string
  first_syllable_attack: string
  consonant_density: number
  emotional_weight: number | null
  imagery_class: string | null
  cliche_flag: number
  ai_bias_flag: number
}
export interface BurnListEntry {
  word: string
  severity: 'mild' | 'strong' | 'extreme'
  drift_direction: string | null
  alternatives: string[]
}
```

- [ ] **Step 2: Slug helper test**

File: `apps/web/tests/slug.test.ts`

```ts
import { describe, it, expect } from 'vitest'
import { slugifyTitle, datedSlug } from '@/lib/slug'

describe('slugifyTitle', () => {
  it('lowercases + dashes', () => {
    expect(slugifyTitle('Pull Me Deep')).toBe('pull-me-deep')
  })
  it('strips punctuation', () => {
    expect(slugifyTitle("Don't Look Back!")).toBe('dont-look-back')
  })
  it('collapses whitespace', () => {
    expect(slugifyTitle('  hello   world  ')).toBe('hello-world')
  })
})

describe('datedSlug', () => {
  it('prefixes with ISO date', () => {
    expect(datedSlug('My Song', new Date('2026-04-30T12:00:00Z'))).toBe('2026-04-30-my-song')
  })
  it('falls back to untitled with index', () => {
    expect(datedSlug('', new Date('2026-04-30'), 3)).toBe('2026-04-30-untitled-3')
  })
})
```

- [ ] **Step 3: Implement slug helper**

File: `apps/web/lib/slug.ts`

```ts
export function slugifyTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

export function datedSlug(title: string, date: Date = new Date(), untitledIndex = 1): string {
  const iso = date.toISOString().slice(0, 10)
  const slug = slugifyTitle(title)
  return slug ? `${iso}-${slug}` : `${iso}-untitled-${untitledIndex}`
}
```

- [ ] **Step 4: API client test (msw)**

File: `apps/web/tests/api.test.ts`

```ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { setupServer } from 'msw/node'
import { http, HttpResponse } from 'msw'
import { api, ApiError } from '@/lib/api'
import type { Genre, Song } from '@/types/song'

const BASE = 'http://localhost:8000'

const server = setupServer(
  http.get(`${BASE}/genres`, () =>
    HttpResponse.json<Genre[]>([
      { id: 1, slug: 'pop', name: 'Pop', typical_bpm_min: 90, typical_bpm_max: 130, description: null },
    ]),
  ),
  http.post(`${BASE}/songs`, async ({ request }) => {
    const body = (await request.json()) as Song
    return HttpResponse.json(body, { status: 201 })
  }),
  http.get(`${BASE}/songs/missing`, () => new HttpResponse('not found', { status: 404 })),
)

beforeAll(() => server.listen())
afterAll(() => server.close())

describe('api.getGenres', () => {
  it('returns parsed genres', async () => {
    const g = await api.getGenres()
    expect(g[0].slug).toBe('pop')
  })
})

describe('api.createSong', () => {
  it('round-trips', async () => {
    const sample: Song = {
      id: '2026-04-30-x', title: 'X', created: '', modified: '',
      genre: 'pop', sub_genre: 'alt-pop', songwriter_lens: null,
      intent: { topic: 't', emotion_arc: 'surrender', story: { event: 'e', emotion: 'm', resolution: 'r' } },
      production: { bpm: 88, structure_template: 'pop.standard', energy_curve: [0.4] },
      sections: [], suno_prompt: { current: '', history: [] }, requests: [], notes: '', last_modified_by: 'ui',
    }
    const out = await api.createSong(sample)
    expect(out.id).toBe('2026-04-30-x')
  })
})

describe('api error handling', () => {
  it('throws ApiError on 404', async () => {
    await expect(api.getSong('missing')).rejects.toBeInstanceOf(ApiError)
  })
})
```

- [ ] **Step 5: Implement API client**

File: `apps/web/lib/api.ts`

```ts
import type {
  BurnListEntry, CadencePattern, Genre, Song, SongwriterProfile, SubGenre, VocabBankWord,
} from '@/types/song'

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  body: string
  constructor(status: number, body: string) {
    super(`API ${status}: ${body}`)
    this.status = status
    this.body = body
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
  })
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new ApiError(r.status, body)
  }
  if (r.status === 204) return undefined as T
  return (await r.json()) as T
}

export const api = {
  // lookups
  getGenres: () => request<Genre[]>('/genres'),
  getGenre: (slug: string) => request<Genre>(`/genres/${slug}`),
  getCadencePatterns: () => request<CadencePattern[]>('/cadence-patterns'),
  getVocabBankWords: (slug: string) => request<VocabBankWord[]>(`/vocab-banks/${slug}/words`),
  getRhymes: (word: string, limit = 50) =>
    request<{ rhyme_class: string; words: VocabBankWord[] }>(`/rhymes?word=${encodeURIComponent(word)}&limit=${limit}`),
  getBurnList: () => request<BurnListEntry[]>('/burn-list'),
  getSongwriterProfiles: (genre?: string, role?: string) => {
    const q = new URLSearchParams()
    if (genre) q.set('genre', genre)
    if (role) q.set('role', role)
    const qs = q.toString()
    return request<SongwriterProfile[]>(`/songwriter-profiles${qs ? '?' + qs : ''}`)
  },
  getSongwriterProfile: (slug: string) => request<SongwriterProfile>(`/songwriter-profiles/${slug}`),
  getStructureTemplates: () =>
    request<Array<{ slug: string; name: string; sections: Array<{ section: string; energy: number; syllable_target: number }>; genre_compatibility: string[] }>>('/structure-templates'),
  getProductionFingerprint: (subGenre: string) =>
    request<Record<string, unknown>>(`/production-fingerprints/${encodeURIComponent(subGenre)}`),
  getEmotionTempo: (emotion: string, subGenre: string) =>
    request<{ bpm_min: number; bpm_max: number; energy_curve: number[]; anti_prompts: string[] }>(
      `/emotion-tempo?emotion=${encodeURIComponent(emotion)}&sub_genre=${encodeURIComponent(subGenre)}`,
    ),
  // songs
  listSongs: () => request<Array<Pick<Song, 'id' | 'title' | 'genre' | 'sub_genre' | 'songwriter_lens' | 'modified'>>>('/songs'),
  getSong: (slug: string) => request<Song>(`/songs/${slug}`),
  createSong: (song: Song) => request<Song>('/songs', { method: 'POST', body: JSON.stringify(song) }),
  updateSong: (song: Song) => request<Song>(`/songs/${song.id}`, { method: 'PUT', body: JSON.stringify(song) }),
  validate: (slug: string, includeLLM = false) =>
    request<Song>(`/songs/${slug}/validate?include_llm=${includeLLM}`, { method: 'POST' }),
}
```

- [ ] **Step 6: Run tests, verify PASS**

```bash
cd apps/web
npm test -- --run
```

- [ ] **Step 7: Commit**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/types apps/web/lib apps/web/tests
git commit -m "feat(ui): types + API client + slug helper"
```

---

## Task 3: WebSocket helper + useSong hook

**Files:**
- Create: `apps/web/lib/ws.ts`
- Create: `apps/web/lib/use-song.ts`
- Create: `apps/web/tests/ws.test.ts`

The hook subscribes to `ws://localhost:8000/ws/songs/{slug}`, accepts `snapshot` and `update` messages, and exposes `{ song, status }`. Reconnects with exponential backoff on disconnect.

- [ ] **Step 1: Failing test**

File: `apps/web/tests/ws.test.ts`

```ts
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
```

- [ ] **Step 2: Implement WebSocket helper**

File: `apps/web/lib/ws.ts`

```ts
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
```

- [ ] **Step 3: Implement `useSong` hook**

File: `apps/web/lib/use-song.ts`

```ts
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
```

- [ ] **Step 4: Run tests, verify PASS. Commit**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/lib apps/web/tests/ws.test.ts
git commit -m "feat(ui): WebSocket connection + useSong hook with reconnect"
```

---

## Task 4: Layout, theme, top nav

**Files:**
- Modify: `apps/web/app/layout.tsx`
- Create: `apps/web/components/nav.tsx`
- Create: `apps/web/components/theme-provider.tsx`
- Modify: `apps/web/app/globals.css`

The app shell. Dark mode by default, top nav with links, content area.

- [ ] **Step 1: Replace `app/layout.tsx`**

```tsx
import type { Metadata } from 'next'
import { Geist, EB_Garamond } from 'next/font/google'

import { Nav } from '@/components/nav'
import './globals.css'

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' })
const garamond = EB_Garamond({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-serif' })

export const metadata: Metadata = {
  title: 'Songwriter',
  description: 'A Claude-Code-native songwriting workspace',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${garamond.variable} dark`}>
      <body className="bg-background text-foreground min-h-screen">
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  )
}
```

- [ ] **Step 2: Create `components/nav.tsx`**

```tsx
import Link from 'next/link'
import { Music, Plus } from 'lucide-react'

import { Button } from '@/components/ui/button'

export function Nav() {
  return (
    <header className="border-b border-border/40">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-medium tracking-tight">
          <Music className="h-4 w-4 text-foreground/70" />
          Songwriter
        </Link>
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/songwriters" className="text-foreground/70 hover:text-foreground">Profiles</Link>
          <Link href="/descriptors" className="text-foreground/70 hover:text-foreground">Descriptors</Link>
          <Link href="/vocab" className="text-foreground/70 hover:text-foreground">Vocab</Link>
          <Link href="/settings" className="text-foreground/70 hover:text-foreground">Settings</Link>
          <Button asChild size="sm" className="ml-2">
            <Link href="/songs/new"><Plus className="h-3 w-3 mr-1" />New song</Link>
          </Button>
        </nav>
      </div>
    </header>
  )
}
```

- [ ] **Step 3: Run `npm run build`, verify clean**

- [ ] **Step 4: Commit**

```bash
git add apps/web/app/layout.tsx apps/web/app/globals.css apps/web/components/nav.tsx
git commit -m "feat(ui): app shell + dark theme + top nav"
```

---

## Task 5: Home / Song Library page

**Files:**
- Modify: `apps/web/app/page.tsx`
- Create: `apps/web/components/song-card.tsx`
- Create: `apps/web/tests/components/song-card.test.tsx`

Lists songs from the API. Each card shows title, genre, lens, last-modified. "Start a new song" hero card on top.

- [ ] **Step 1: SongCard component test**

File: `apps/web/tests/components/song-card.test.tsx`

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SongCard } from '@/components/song-card'

const sample = {
  id: '2026-04-30-pull-me-deep',
  title: 'Pull Me Deep',
  genre: 'rnb',
  sub_genre: 'alt-rnb',
  songwriter_lens: 'frank-ocean',
  modified: '2026-04-30T15:18:00Z',
}

describe('SongCard', () => {
  it('renders title + genre + lens chip', () => {
    render(<SongCard song={sample} />)
    expect(screen.getByText('Pull Me Deep')).toBeInTheDocument()
    expect(screen.getByText(/alt-rnb/)).toBeInTheDocument()
    expect(screen.getByText(/frank-ocean/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Implement `components/song-card.tsx`**

```tsx
import Link from 'next/link'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export interface SongSummary {
  id: string
  title: string
  genre: string
  sub_genre: string
  songwriter_lens: string | null
  modified: string
}

export function SongCard({ song }: { song: SongSummary }) {
  return (
    <Link href={`/songs/${song.id}`}>
      <Card className="hover:bg-muted/30 transition-colors cursor-pointer h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-medium">{song.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary" className="text-xs">{song.sub_genre}</Badge>
          {song.songwriter_lens && (
            <Badge variant="outline" className="text-xs">{song.songwriter_lens}</Badge>
          )}
          <span className="ml-auto text-xs text-foreground/50">
            {new Date(song.modified).toLocaleDateString()}
          </span>
        </CardContent>
      </Card>
    </Link>
  )
}
```

- [ ] **Step 3: Implement Home page**

File: `apps/web/app/page.tsx`

```tsx
import Link from 'next/link'

import { SongCard, type SongSummary } from '@/components/song-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus } from 'lucide-react'

async function fetchSongs(): Promise<SongSummary[]> {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/songs`, { cache: 'no-store' })
    if (!r.ok) return []
    return r.json()
  } catch { return [] }
}

export default async function Home() {
  const songs = await fetchSongs()
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="font-serif text-3xl">Songs</h1>
        <p className="text-foreground/60 text-sm">
          {songs.length === 0 ? 'No songs yet — start your first one.' : `${songs.length} song${songs.length === 1 ? '' : 's'}`}
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Link href="/songs/new" className="block">
          <Card className="hover:bg-muted/30 transition-colors h-full border-dashed">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base font-medium">
                <Plus className="h-4 w-4" /> Start a new song
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-foreground/60">
              Pick a genre, set a topic, optionally apply a songwriter lens.
            </CardContent>
          </Card>
        </Link>
        {songs.map(s => <SongCard key={s.id} song={s} />)}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests + build. Commit**

```bash
cd apps/web && npm test -- --run && npm run build
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/app/page.tsx apps/web/components/song-card.tsx apps/web/tests/components
git commit -m "feat(ui): home page + song-library grid"
```

---

## Task 6: New Song Wizard

**Files:**
- Create: `apps/web/app/songs/new/page.tsx`
- Create: `apps/web/components/wizard/*.tsx` (orchestrator + 6 step components)
- Create: `apps/web/tests/components/wizard.test.tsx`

A single-page wizard with 6 vertical steps, each with a guard so the user can't skip ahead. After "Create song", redirects to `/songs/[slug]`.

- [ ] **Step 1: Wizard orchestrator**

File: `apps/web/components/wizard/wizard.tsx`

```tsx
'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { datedSlug } from '@/lib/slug'
import type { Genre, Song, SubGenre, SongwriterProfile } from '@/types/song'

import { StepGenre } from './step-genre'
import { StepSubGenre } from './step-sub-genre'
import { StepTopic } from './step-topic'
import { StepEmotion } from './step-emotion'
import { StepLens } from './step-lens'
import { StepReview } from './step-review'

export interface WizardState {
  genre: Genre | null
  subGenre: SubGenre | null
  title: string
  topic: string
  emotionArc: string
  lens: SongwriterProfile | null
  storyEvent: string
  storyEmotion: string
  storyResolution: string
}

const empty: WizardState = {
  genre: null, subGenre: null, title: '', topic: '', emotionArc: '',
  lens: null, storyEvent: '', storyEmotion: '', storyResolution: '',
}

export function Wizard({ initialGenres }: { initialGenres: Genre[] }) {
  const router = useRouter()
  const [state, setState] = useState<WizardState>(empty)
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const update = (patch: Partial<WizardState>) => setState(s => ({ ...s, ...patch }))

  const create = async () => {
    if (!state.genre || !state.subGenre) return
    setSubmitting(true); setError(null)
    const slug = datedSlug(state.title || state.topic)
    const song: Song = {
      id: slug,
      title: state.title || state.topic.slice(0, 60),
      created: new Date().toISOString(),
      modified: new Date().toISOString(),
      genre: state.genre.slug,
      sub_genre: state.subGenre.slug,
      songwriter_lens: state.lens?.slug ?? null,
      intent: {
        topic: state.topic,
        emotion_arc: state.emotionArc,
        story: { event: state.storyEvent, emotion: state.storyEmotion, resolution: state.storyResolution },
      },
      production: { bpm: state.subGenre.typical_bpm_min ?? 100, structure_template: '', energy_curve: [] },
      sections: [],
      suno_prompt: { current: '', history: [] },
      requests: [],
      notes: '',
      last_modified_by: 'ui',
    }
    try {
      await api.createSong(song)
      router.push(`/songs/${slug}`)
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  const steps = [
    <StepGenre key="g" genres={initialGenres} value={state.genre} onPick={g => { update({ genre: g, subGenre: null }); setStep(1) }} />,
    <StepSubGenre key="sg" genre={state.genre} value={state.subGenre} onPick={sg => { update({ subGenre: sg }); setStep(2) }} />,
    <StepTopic key="t" value={state.topic} title={state.title} onChange={(topic, title) => update({ topic, title })} onNext={() => setStep(3)} />,
    <StepEmotion key="e" value={state.emotionArc} onPick={emotion => { update({ emotionArc: emotion }); setStep(4) }} story={{ event: state.storyEvent, emotion: state.storyEmotion, resolution: state.storyResolution }} onStoryChange={(field, v) => update({ [`story${field}`]: v } as Partial<WizardState>)} />,
    <StepLens key="l" genre={state.genre?.slug} value={state.lens} onPick={lens => { update({ lens }); setStep(5) }} />,
    <StepReview key="r" state={state} onSubmit={create} submitting={submitting} error={error} />,
  ]

  return (
    <div className="space-y-6">
      <div className="flex gap-1.5">
        {steps.map((_, i) => (
          <div key={i} className={`h-1 flex-1 rounded ${i <= step ? 'bg-foreground/80' : 'bg-foreground/15'}`} />
        ))}
      </div>
      {steps[step]}
      {step > 0 && step < 5 && (
        <Button variant="ghost" size="sm" onClick={() => setStep(s => Math.max(0, s - 1))}>← back</Button>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Step components (6 small files)**

Use this skeleton for each, varying the content. Each step file is short.

File: `apps/web/components/wizard/step-genre.tsx`

```tsx
'use client'
import type { Genre } from '@/types/song'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function StepGenre({ genres, value, onPick }: { genres: Genre[]; value: Genre | null; onPick: (g: Genre) => void }) {
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">What genre?</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {genres.map(g => (
          <Card key={g.slug} onClick={() => onPick(g)} className={`cursor-pointer hover:bg-muted/30 ${value?.slug === g.slug ? 'border-foreground' : ''}`}>
            <CardHeader className="pb-1"><CardTitle className="text-base font-medium">{g.name}</CardTitle></CardHeader>
            <CardContent className="text-xs text-foreground/60">{g.typical_bpm_min}–{g.typical_bpm_max} BPM</CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

File: `apps/web/components/wizard/step-sub-genre.tsx`

```tsx
'use client'
import { useEffect, useState } from 'react'
import type { Genre, SubGenre } from '@/types/song'
import { api } from '@/lib/api'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'

export function StepSubGenre({ genre, value, onPick }: { genre: Genre | null; value: SubGenre | null; onPick: (sg: SubGenre) => void }) {
  const [subs, setSubs] = useState<SubGenre[]>([])
  useEffect(() => {
    if (!genre) return
    api.getGenre(genre.slug).then(g => setSubs(g.sub_genres ?? []))
  }, [genre])
  if (!genre) return null
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">{genre.name} — pick a sub-genre</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {subs.map(sg => (
          <Card key={sg.slug} onClick={() => onPick(sg)} className={`cursor-pointer hover:bg-muted/30 ${value?.slug === sg.slug ? 'border-foreground' : ''}`}>
            <CardHeader className="pb-1"><CardTitle className="text-base font-medium">{sg.name}</CardTitle></CardHeader>
            <CardContent className="text-xs text-foreground/60">{sg.typical_bpm_min}–{sg.typical_bpm_max} BPM</CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
```

File: `apps/web/components/wizard/step-topic.tsx`

```tsx
'use client'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'

export function StepTopic({ topic = '', title = '', value, onChange, onNext }: { topic?: string; title?: string; value?: string; onChange: (topic: string, title: string) => void; onNext: () => void }) {
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">What's it about?</h2>
      <Label className="text-xs">Title (optional)</Label>
      <Input value={title} onChange={e => onChange(value ?? '', e.target.value)} placeholder="Pull Me Deep" />
      <Label className="text-xs">Topic</Label>
      <Textarea value={value ?? ''} onChange={e => onChange(e.target.value, title)} placeholder="A late-night call from an ex you should know better than to answer." rows={3} />
      <Button onClick={onNext} disabled={!(value ?? '').trim()}>Next →</Button>
    </div>
  )
}
```

File: `apps/web/components/wizard/step-emotion.tsx`

```tsx
'use client'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const ARCS = ['escalation', 'collapse', 'redemption', 'surrender', 'defiance', 'nostalgia']

export function StepEmotion({
  value, onPick, story, onStoryChange,
}: {
  value: string
  onPick: (v: string) => void
  story: { event: string; emotion: string; resolution: string }
  onStoryChange: (field: 'Event' | 'Emotion' | 'Resolution', v: string) => void
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-serif text-2xl">Emotion arc</h2>
        <div className="grid grid-cols-3 gap-2 mt-2">
          {ARCS.map(a => (
            <Card key={a} onClick={() => onPick(a)} className={`cursor-pointer hover:bg-muted/30 ${value === a ? 'border-foreground' : ''}`}>
              <CardContent className="py-3 text-sm font-medium capitalize">{a}</CardContent>
            </Card>
          ))}
        </div>
      </div>
      <div className="space-y-2">
        <h3 className="font-medium">Story (event → emotion → resolution)</h3>
        <Label className="text-xs">Event</Label>
        <Input value={story.event} onChange={e => onStoryChange('Event', e.target.value)} placeholder="she calls late, voice shaking" />
        <Label className="text-xs">Emotion</Label>
        <Input value={story.emotion} onChange={e => onStoryChange('Emotion', e.target.value)} placeholder="I should know better but I'm pulled in" />
        <Label className="text-xs">Resolution</Label>
        <Input value={story.resolution} onChange={e => onStoryChange('Resolution', e.target.value)} placeholder="I let her in anyway" />
      </div>
    </div>
  )
}
```

File: `apps/web/components/wizard/step-lens.tsx`

```tsx
'use client'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import type { SongwriterProfile } from '@/types/song'

export function StepLens({ genre, value, onPick }: { genre: string | undefined; value: SongwriterProfile | null; onPick: (lens: SongwriterProfile | null) => void }) {
  const [profiles, setProfiles] = useState<SongwriterProfile[]>([])
  useEffect(() => { if (genre) api.getSongwriterProfiles(genre).then(setProfiles) }, [genre])
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">Songwriter lens (optional)</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        {profiles.map(p => (
          <Card key={p.slug} onClick={() => onPick(p)} className={`cursor-pointer hover:bg-muted/30 ${value?.slug === p.slug ? 'border-foreground' : ''}`}>
            <CardHeader className="pb-1">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                {p.display_name}
                <span className="text-[10px] uppercase text-foreground/50">{p.role}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="text-xs text-foreground/70">
              {p.craft_signature?.[0]}
            </CardContent>
          </Card>
        ))}
      </div>
      <Button variant="ghost" onClick={() => onPick(null)}>Skip lens →</Button>
    </div>
  )
}
```

File: `apps/web/components/wizard/step-review.tsx`

```tsx
'use client'
import { Button } from '@/components/ui/button'
import type { WizardState } from './wizard'

export function StepReview({ state, onSubmit, submitting, error }: { state: WizardState; onSubmit: () => void; submitting: boolean; error: string | null }) {
  return (
    <div className="space-y-4">
      <h2 className="font-serif text-2xl">Review</h2>
      <dl className="grid grid-cols-2 gap-y-2 text-sm">
        <dt className="text-foreground/50">Genre</dt><dd>{state.genre?.name} → {state.subGenre?.name}</dd>
        <dt className="text-foreground/50">Title</dt><dd>{state.title || '(unset)'}</dd>
        <dt className="text-foreground/50">Topic</dt><dd>{state.topic}</dd>
        <dt className="text-foreground/50">Emotion arc</dt><dd className="capitalize">{state.emotionArc}</dd>
        <dt className="text-foreground/50">Lens</dt><dd>{state.lens?.display_name ?? 'none'}</dd>
      </dl>
      <Button onClick={onSubmit} disabled={submitting}>
        {submitting ? 'Creating…' : 'Create song'}
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
```

- [ ] **Step 3: Wizard page entry**

File: `apps/web/app/songs/new/page.tsx`

```tsx
import { Wizard } from '@/components/wizard/wizard'
import { api } from '@/lib/api'

export default async function NewSongPage() {
  const genres = await api.getGenres().catch(() => [])
  return <Wizard initialGenres={genres} />
}
```

- [ ] **Step 4: Wizard component test (smoke)**

File: `apps/web/tests/components/wizard.test.tsx`

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Wizard } from '@/components/wizard/wizard'

describe('Wizard', () => {
  it('renders the genre step first', () => {
    render(<Wizard initialGenres={[{ id: 1, slug: 'pop', name: 'Pop', typical_bpm_min: 90, typical_bpm_max: 130, description: null }]} />)
    expect(screen.getByText('What genre?')).toBeInTheDocument()
    expect(screen.getByText('Pop')).toBeInTheDocument()
  })
})
```

- [ ] **Step 5: Run tests + build. Commit**

```bash
cd apps/web && npm test -- --run && npm run build
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/app/songs/new apps/web/components/wizard apps/web/tests/components/wizard.test.tsx
git commit -m "feat(ui): 6-step new-song wizard"
```

---

## Task 7: Song Editor — 3-pane shell with sections + canvas + tabs

**Files:**
- Create: `apps/web/app/songs/[slug]/page.tsx`
- Create: `apps/web/components/editor/*.tsx` (8 files)
- Create: `apps/web/tests/components/lyric-canvas.test.tsx`

This is the meat of the UI. A client component reads the song via `useSong(slug)` and renders three panes plus a production bar.

- [ ] **Step 1: Editor shell**

File: `apps/web/components/editor/editor.tsx`

```tsx
'use client'
import { useSong } from '@/lib/use-song'

import { SectionList } from './section-list'
import { LyricCanvas } from './lyric-canvas'
import { RightRail } from './right-rail'
import { ProductionBar } from './production-bar'

export function Editor({ slug }: { slug: string }) {
  const { song, status, error } = useSong(slug)

  if (status === 'loading') return <p className="text-foreground/60">Loading…</p>
  if (status === 'error') return <p className="text-destructive">Error: {error}</p>
  if (!song) return <p className="text-foreground/60">Song not found.</p>

  return (
    <div className="flex flex-col gap-4">
      <header className="space-y-1">
        <h1 className="font-serif text-3xl">{song.title}</h1>
        <p className="text-sm text-foreground/60">
          {song.sub_genre} · {song.production.bpm} BPM
          {song.songwriter_lens && <> · lens: <span className="text-foreground/80">{song.songwriter_lens}</span></>}
        </p>
      </header>
      <div className="grid grid-cols-12 gap-4">
        <aside className="col-span-3"><SectionList song={song} /></aside>
        <section className="col-span-6"><LyricCanvas song={song} /></section>
        <aside className="col-span-3"><RightRail song={song} /></aside>
      </div>
      <ProductionBar song={song} />
    </div>
  )
}
```

- [ ] **Step 2: Editor page**

File: `apps/web/app/songs/[slug]/page.tsx`

```tsx
import { Editor } from '@/components/editor/editor'

export default async function SongEditorPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  return <Editor slug={slug} />
}
```

- [ ] **Step 3: SectionList**

File: `apps/web/components/editor/section-list.tsx`

```tsx
'use client'
import { Lock, Pencil, FileText } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import type { Song } from '@/types/song'

const ICON = { draft: FileText, edited: Pencil, locked: Lock } as const

export function SectionList({ song }: { song: Song }) {
  return (
    <Card><CardContent className="p-2 space-y-1">
      {song.sections.length === 0 && <p className="text-xs text-foreground/50 p-2">No sections yet — run /song draft.</p>}
      {song.sections.map(s => {
        const Icon = ICON[s.lock_state]
        return (
          <div key={s.id} className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/30 cursor-pointer">
            <Icon className="h-3 w-3 text-foreground/50" />
            <span className="text-sm flex-1 truncate">{s.label}</span>
            <span className="text-[10px] text-foreground/40">{s.cadence_pattern}</span>
          </div>
        )
      })}
    </CardContent></Card>
  )
}
```

- [ ] **Step 4: LyricCanvas**

File: `apps/web/components/editor/lyric-canvas.tsx`

```tsx
'use client'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { ValidationChips } from './validation-chips'
import type { Song } from '@/types/song'

export function LyricCanvas({ song }: { song: Song }) {
  if (song.sections.length === 0) {
    return (
      <Card><CardContent className="p-6 text-foreground/60 text-sm">
        No drafted sections yet. Run <code>/song draft</code> in Claude Code to generate the first pass.
      </CardContent></Card>
    )
  }
  return (
    <div className="space-y-3">
      {song.sections.map(s => (
        <Card key={s.id}>
          <CardHeader className="pb-2 flex flex-row items-center justify-between">
            <CardTitle className="text-sm font-medium">{s.label}</CardTitle>
            <ValidationChips validation={s.validation} />
          </CardHeader>
          <CardContent className="font-serif text-lg leading-loose">
            {s.lyrics.length === 0 && <p className="text-foreground/40 italic font-sans text-sm">empty</p>}
            {s.lyrics.map((line, i) => <p key={i}>{line || <span className="text-foreground/30">·</span>}</p>)}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
```

File: `apps/web/components/editor/validation-chips.tsx`

```tsx
import { Badge } from '@/components/ui/badge'
import type { SectionValidation } from '@/types/song'

const RULES: Array<{ key: keyof SectionValidation; label: string }> = [
  { key: 'singability', label: 'sing' },
  { key: 'cadence', label: 'cadence' },
  { key: 'phonetic_texture', label: 'phon' },
  { key: 'rhyme_cadence', label: 'rhyme' },
  { key: 'story_sentence', label: 'story' },
]

const COLOR = {
  pass: 'bg-green-700/30 text-green-300 border-green-700/40',
  warn: 'bg-yellow-700/30 text-yellow-300 border-yellow-700/40',
  fail: 'bg-red-700/30 text-red-300 border-red-700/40',
  unrun: 'bg-foreground/10 text-foreground/40 border-foreground/15',
}

export function ValidationChips({ validation }: { validation: SectionValidation }) {
  return (
    <div className="flex gap-1">
      {RULES.map(r => (
        <Badge key={r.key} variant="outline" className={`text-[10px] px-1.5 ${COLOR[validation[r.key] as keyof typeof COLOR]}`}>
          {r.label}
        </Badge>
      ))}
    </div>
  )
}
```

File: `apps/web/tests/components/lyric-canvas.test.tsx`

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LyricCanvas } from '@/components/editor/lyric-canvas'
import type { Song } from '@/types/song'

const empty: Song = {
  id: 'x', title: 'X', created: '', modified: '',
  genre: 'pop', sub_genre: 'alt-pop', songwriter_lens: null,
  intent: { topic: '', emotion_arc: '', story: { event: '', emotion: '', resolution: '' } },
  production: { bpm: 88, structure_template: '', energy_curve: [] },
  sections: [], suno_prompt: { current: '', history: [] }, requests: [], notes: '', last_modified_by: 'ui',
}

describe('LyricCanvas', () => {
  it('shows the empty-state hint when no sections', () => {
    render(<LyricCanvas song={empty} />)
    expect(screen.getByText(/draft/)).toBeInTheDocument()
  })

  it('renders sections with validation chips', () => {
    const s = { ...empty, sections: [{
      id: 'v1', label: 'Verse 1', lock_state: 'draft' as const, lyrics: ['hello world'],
      cadence_pattern: 'melodic-glide',
      validation: { singability: 'pass', cadence: 'warn', phonetic_texture: 'pass', rhyme_cadence: 'pass', story_sentence: 'unrun', warnings: [] },
      phonetic_overlay: [],
    }] }
    render(<LyricCanvas song={s} />)
    expect(screen.getByText('Verse 1')).toBeInTheDocument()
    expect(screen.getByText('hello world')).toBeInTheDocument()
  })
})
```

- [ ] **Step 5: RightRail with tabs (Vocab + Suno + shell tabs)**

File: `apps/web/components/editor/right-rail.tsx`

```tsx
'use client'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TabVocab } from './tab-vocab'
import { TabSuno } from './tab-suno'
import { TabRhymes } from './tab-rhymes'
import { TabCadence } from './tab-cadence'
import { TabNotes } from './tab-notes'
import type { Song } from '@/types/song'

export function RightRail({ song }: { song: Song }) {
  return (
    <Tabs defaultValue="vocab" className="w-full">
      <TabsList className="grid grid-cols-5 w-full">
        <TabsTrigger value="vocab">Vocab</TabsTrigger>
        <TabsTrigger value="rhymes">Rhymes</TabsTrigger>
        <TabsTrigger value="cadence">Cadence</TabsTrigger>
        <TabsTrigger value="suno">Suno</TabsTrigger>
        <TabsTrigger value="notes">Notes</TabsTrigger>
      </TabsList>
      <TabsContent value="vocab"><TabVocab song={song} /></TabsContent>
      <TabsContent value="rhymes"><TabRhymes /></TabsContent>
      <TabsContent value="cadence"><TabCadence /></TabsContent>
      <TabsContent value="suno"><TabSuno song={song} /></TabsContent>
      <TabsContent value="notes"><TabNotes notes={song.notes} /></TabsContent>
    </Tabs>
  )
}
```

File: `apps/web/components/editor/tab-vocab.tsx`

```tsx
'use client'
import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import type { Song, VocabBankWord } from '@/types/song'

export function TabVocab({ song }: { song: Song }) {
  const [bankSlug, setBankSlug] = useState<string>('')
  const [words, setWords] = useState<VocabBankWord[]>([])
  useEffect(() => {
    if (!bankSlug) {
      // pick a default bank from the song's genre + first emotion arc keyword
      const guess = `${song.genre}.${song.intent.emotion_arc || 'confession'}`
      setBankSlug(guess)
    }
  }, [song, bankSlug])
  useEffect(() => {
    if (!bankSlug) return
    api.getVocabBankWords(bankSlug).then(setWords).catch(() => setWords([]))
  }, [bankSlug])
  return (
    <div className="text-xs space-y-2 p-2">
      <div className="text-foreground/50">{bankSlug}</div>
      <ul className="space-y-0.5">
        {words.slice(0, 40).map(w => (
          <li key={w.word} className="flex justify-between">
            <span>{w.word}</span>
            <span className="text-foreground/40">{w.ipa}</span>
          </li>
        ))}
        {words.length === 0 && <li className="text-foreground/40 italic">no words for this bank</li>}
      </ul>
    </div>
  )
}
```

File: `apps/web/components/editor/tab-suno.tsx`

```tsx
'use client'
import { Button } from '@/components/ui/button'
import { Copy, ExternalLink } from 'lucide-react'
import type { Song } from '@/types/song'

export function TabSuno({ song }: { song: Song }) {
  const text = song.suno_prompt.current
  const copy = () => navigator.clipboard.writeText(text)
  return (
    <div className="text-xs space-y-2 p-2">
      <pre className="whitespace-pre-wrap font-sans bg-muted/30 p-2 rounded text-[11px] leading-relaxed min-h-[120px]">
        {text || <span className="text-foreground/40 italic">no Suno prompt yet — run /song prompt</span>}
      </pre>
      <div className="flex gap-1">
        <Button size="sm" variant="secondary" onClick={copy} disabled={!text}>
          <Copy className="h-3 w-3 mr-1" />Copy
        </Button>
        <Button size="sm" variant="secondary" disabled={!text} asChild>
          <a href="https://suno.com/create" target="_blank" rel="noreferrer">
            <ExternalLink className="h-3 w-3 mr-1" />Open Suno
          </a>
        </Button>
      </div>
      <div className="text-foreground/40">{text.length} chars</div>
    </div>
  )
}
```

File: `apps/web/components/editor/tab-rhymes.tsx`

```tsx
export function TabRhymes() {
  return <div className="p-3 text-xs text-foreground/50 italic">Rhyme inspector — Phase 2</div>
}
```

File: `apps/web/components/editor/tab-cadence.tsx`

```tsx
export function TabCadence() {
  return <div className="p-3 text-xs text-foreground/50 italic">Cadence inspector — Phase 2</div>
}
```

File: `apps/web/components/editor/tab-notes.tsx`

```tsx
'use client'
export function TabNotes({ notes }: { notes: string }) {
  return (
    <div className="p-2 text-xs">
      <textarea
        defaultValue={notes}
        readOnly
        className="w-full h-32 bg-muted/30 rounded p-2 text-foreground/80 resize-none"
        placeholder="The skill reads notes from here on next run."
      />
    </div>
  )
}
```

- [ ] **Step 6: ProductionBar**

File: `apps/web/components/editor/production-bar.tsx`

```tsx
'use client'
import { Card, CardContent } from '@/components/ui/card'
import type { Song } from '@/types/song'

export function ProductionBar({ song }: { song: Song }) {
  return (
    <Card><CardContent className="flex items-center gap-4 p-3 text-xs">
      <div className="flex items-baseline gap-1">
        <span className="text-foreground/50">BPM</span>
        <span className="text-foreground/80 text-sm">{song.production.bpm}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span className="text-foreground/50">Structure</span>
        <span className="text-foreground/80">{song.production.structure_template || '(unset)'}</span>
      </div>
      <div className="flex items-baseline gap-1 flex-1">
        <span className="text-foreground/50">Energy</span>
        <div className="flex gap-0.5 items-end h-4">
          {song.production.energy_curve.map((v, i) => (
            <div key={i} className="w-1.5 bg-foreground/40 rounded-sm" style={{ height: `${v * 100}%` }} />
          ))}
        </div>
      </div>
    </CardContent></Card>
  )
}
```

- [ ] **Step 7: Run tests + build. Commit**

```bash
cd apps/web && npm test -- --run && npm run build
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/app/songs/[slug] apps/web/components/editor apps/web/tests/components/lyric-canvas.test.tsx
git commit -m "feat(ui): song editor — sections + canvas + right-rail tabs + production bar"
```

---

## Task 8: Placeholder pages + settings + final verification

**Files:**
- Create: `apps/web/app/songwriters/page.tsx`
- Create: `apps/web/app/descriptors/page.tsx`
- Create: `apps/web/app/vocab/page.tsx`
- Create: `apps/web/app/settings/page.tsx`
- Update: `songwriter/start.sh` (also boots web)

Three placeholder pages so the nav links don't 404. Settings shows the API base + songs dir from `/healthz`.

- [ ] **Step 1: Placeholder pages**

File: `apps/web/app/songwriters/page.tsx`

```tsx
export default function SongwritersPage() {
  return (
    <div className="space-y-2">
      <h1 className="font-serif text-3xl">Songwriter Profiles</h1>
      <p className="text-foreground/60 text-sm">
        Browser coming in Phase 2. For now, profiles are accessed via the API:
        <code className="ml-1">curl http://localhost:8000/songwriter-profiles</code>
      </p>
    </div>
  )
}
```

File: `apps/web/app/descriptors/page.tsx`

```tsx
export default function DescriptorsPage() {
  return (
    <div className="space-y-2">
      <h1 className="font-serif text-3xl">Sonic Descriptors</h1>
      <p className="text-foreground/60 text-sm">Browser coming in Phase 2.</p>
    </div>
  )
}
```

File: `apps/web/app/vocab/page.tsx`

```tsx
export default function VocabPage() {
  return (
    <div className="space-y-2">
      <h1 className="font-serif text-3xl">Vocab Bank Explorer</h1>
      <p className="text-foreground/60 text-sm">Browser coming in Phase 2.</p>
    </div>
  )
}
```

File: `apps/web/app/settings/page.tsx`

```tsx
async function getHealth() {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/healthz`, { cache: 'no-store' })
    return r.ok ? r.json() : null
  } catch { return null }
}

export default async function SettingsPage() {
  const h = await getHealth()
  return (
    <div className="space-y-3">
      <h1 className="font-serif text-3xl">Settings</h1>
      <dl className="text-sm grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
        <dt className="text-foreground/50">API status</dt>
        <dd>{h ? 'reachable' : 'not reachable — start `./start.sh`'}</dd>
        {h && (
          <>
            <dt className="text-foreground/50">DB</dt><dd className="font-mono text-xs">{h.db}</dd>
            <dt className="text-foreground/50">Songs dir</dt><dd className="font-mono text-xs">{h.songs_dir}</dd>
          </>
        )}
      </dl>
    </div>
  )
}
```

- [ ] **Step 2: Update `start.sh` to boot the web UI too**

Modify `songwriter/start.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -f data/songwriter.db ]; then
  echo "DB missing — running songwriter-build..."
  ./.venv/bin/songwriter-build
fi

trap 'jobs -p | xargs -r kill 2>/dev/null' EXIT

./.venv/bin/uvicorn songwriter.api.main:app --port 8000 &
API_PID=$!
echo "API → http://localhost:8000 (pid $API_PID)"

if [ -d apps/web/node_modules ]; then
  ( cd apps/web && npm run dev ) &
  WEB_PID=$!
  echo "Web → http://localhost:3000 (pid $WEB_PID)"
else
  echo "Web UI deps not installed — run: cd apps/web && npm install"
fi

wait
```

- [ ] **Step 3: Final test sweep**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
source .venv/bin/activate
pytest -q
cd apps/web
npm test -- --run
npm run build
```

Expected: every backend test passes (~237), every UI test passes, Next.js build is clean.

- [ ] **Step 4: Commit**

```bash
cd "/Users/mdacosta/Desktop/Song Writing/songwriter"
git add apps/web/app/songwriters apps/web/app/descriptors apps/web/app/vocab apps/web/app/settings start.sh
git commit -m "feat(ui): placeholder pages + settings + start.sh boots web"
```

---

## Self-review summary

**Spec coverage (UI scope):**

| Spec deliverable | Task |
|---|---|
| Next.js + Tailwind + shadcn/ui scaffold | 1 |
| Typed API client | 2 |
| WebSocket sync hook | 3 |
| Layout + dark theme + nav | 4 |
| Home / Song Library | 5 |
| 6-step New Song Wizard | 6 |
| 3-pane Song Editor (sections, canvas, right rail) | 7 |
| Validation chips per section | 7 |
| Vocab + Suno tabs | 7 |
| Bottom production bar | 7 |
| Placeholder pages for Phase 2 routes | 8 |
| Settings page (basic) | 8 |
| `start.sh` boots both API + web | 8 |

**Out of scope (Phase 2):**
- Songwriter profile browser
- Sonic descriptor library
- Vocab bank explorer
- Phonetic overlay coloring
- Drag-to-reorder sections
- Cadence beat-grid visualization
- Rhyme inspector

**Decisions baked in (recap):**
- Next.js 15 + Tailwind v4 + shadcn/ui + Vitest. Dark mode default.
- API base configurable via `NEXT_PUBLIC_API_BASE`; defaults to `http://localhost:8000`.
- WebSocket reconnect with exponential backoff (capped at 10s).
- Song JSON shape mirrored manually in `types/song.ts`. Future task: codegen from OpenAPI.
- Placeholders for Songwriters / Descriptors / Vocab pages so nav doesn't 404.

**Critical assertions tested:**
- Slug helper covers title-with-punctuation, whitespace, untitled fallback.
- API client correctly handles 200 / 201 / 404.
- WebSocket forwards `snapshot` and `update` messages.
- SongCard renders required fields.
- Wizard renders the genre step first.
- LyricCanvas shows empty-state hint and renders drafted sections with chips.
- Build passes cleanly (TS strict).

---

## Execution handoff

8 tasks. Mostly TypeScript + React with shadcn primitives. Each task is bigger than a skill task but smaller than the heaviest API tasks. Subagent-driven execution recommended.

After this plan executes, the full Phase 1 stack is shippable — DB + API + skill + UI all coexisting in one repo.
