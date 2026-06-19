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
      sections: [], suno_prompt: { current: '', history: [] }, requests: [], notes: '',
      cohesion: { verdict: 'unrun', summary: '', issues: [] }, last_modified_by: 'ui',
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
