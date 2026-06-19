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
  draft: (slug: string, sectionId?: string, maxAttempts = 1, fix = false) => {
    const qs = new URLSearchParams()
    if (sectionId) qs.set('section', sectionId)
    if (maxAttempts > 1) qs.set('max_attempts', String(maxAttempts))
    if (fix) qs.set('fix', 'true')
    const q = qs.toString()
    return request<DraftResponse>(`/songs/${slug}/draft${q ? `?${q}` : ''}`, { method: 'POST' })
  },
  buildSunoPrompt: (slug: string) =>
    request<{ song: Song; warnings: string[]; sources: Record<string, string> }>(
      `/songs/${slug}/suno-prompt`, { method: 'POST' },
    ),
  // anchor-word preview — what the resolver would feed into the next draft
  getAnchorPreview: (slug: string, includeLLM = false) =>
    request<AnchorPreview>(
      `/songs/${slug}/anchor-preview?include_llm=${includeLLM}`,
    ),
  // pre-flight DB coverage — which lookups will hit / silently degrade
  getCoverage: (slug: string) =>
    request<Coverage>(`/songs/${slug}/coverage`),
  // descriptors
  listDescriptors: (quality?: string, source?: string) => {
    const q = new URLSearchParams()
    if (quality) q.set('quality', quality)
    if (source) q.set('source', source)
    const qs = q.toString()
    return request<DescriptorEntry[]>(`/descriptors${qs ? '?' + qs : ''}`)
  },
  pinDescriptor: (name: string) => request<DescriptorEntry>(`/descriptors/${encodeURIComponent(name)}/pin`, { method: 'POST' }),
  unpinDescriptor: (name: string) => request<DescriptorEntry>(`/descriptors/${encodeURIComponent(name)}/unpin`, { method: 'POST' }),
  deleteDescriptor: (name: string) => request<{ deleted: string }>(`/descriptors/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  getDescriptor: (name: string) => request<DescriptorEntry>(`/descriptors/${encodeURIComponent(name)}`),
  // vocab
  listVocabBanks: () => request<Array<{ slug: string; name: string; description: string | null }>>('/vocab-banks'),
  // bulk word lookup for phonetic overlay
  lookupWords: (words: string[]) =>
    request<Record<string, VocabBankWord>>('/words/lookup', { method: 'POST', body: JSON.stringify({ words }) }),
  // per-line alternatives (synchronous — single payload at end)
  lineAlternatives: (slug: string, sectionId: string, lineIndex: number, count = 3, constraint = '') => {
    const q = new URLSearchParams({ count: String(count) })
    if (constraint) q.set('constraint', constraint)
    return request<{
      section_id: string
      line_index: number
      original: string
      alternatives: string[]
    }>(`/songs/${slug}/sections/${sectionId}/lines/${lineIndex}/alternatives?${q.toString()}`, { method: 'POST' })
  },
  // streaming line alternatives — returns an EventSource the caller listens to
  lineAlternativesStreamUrl: (slug: string, sectionId: string, lineIndex: number, count = 3, constraint = '') => {
    const q = new URLSearchParams({ count: String(count) })
    if (constraint) q.set('constraint', constraint)
    return `${API_BASE}/songs/${slug}/sections/${sectionId}/lines/${lineIndex}/alternatives/stream?${q.toString()}`
  },
}

export interface DescriptorEntry {
  id: number
  normalized_name: string
  canonical_name: string
  era_label: string | null
  descriptor: string
  descriptor_short: string
  descriptor_long: string
  vocal_attributes: Record<string, unknown> | null
  production_attrs: Record<string, unknown> | null
  genre_context: string | null
  source: 'auto-llm' | 'songwriter-profile-derived' | 'user-curated'
  quality_state: 'unverified' | 'reviewed' | 'pinned'
  use_count: number
  created_at: string
  last_used_at: string | null
}

export interface Coverage {
  song_id: string
  ready: boolean
  items: {
    production_fingerprint: 'ok' | 'missing' | 'missing-subgenre'
    emotion_tempo: 'ok' | 'missing' | 'missing-subgenre' | 'unset'
    songwriter_lens: 'ok' | 'missing' | 'unset'
    cadence_patterns: 'ok' | 'missing' | 'partial' | 'no-sections'
  }
  cadence_per_section: Array<{
    section_id: string
    label: string
    cadence: string | null
    status: 'ok' | 'missing' | 'unset'
  }>
  anchor_vocab: {
    source: 'exact' | 'sibling-genre' | 'sibling-emotion' | 'artist-corpus' | 'corpus' | 'llm-fallback' | 'none'
    bank_slug: string | null
    count: number
    would_use_llm: boolean
  }
}

export interface AnchorPreview {
  song_id: string
  genre: string
  emotion: string
  topic: string
  source: 'exact' | 'sibling-genre' | 'sibling-emotion' | 'artist-corpus' | 'corpus' | 'llm-fallback' | 'none'
  bank_slug: string | null
  count: number
  words: string[]
  include_llm: boolean
}

export interface DraftResponse {
  song: Song
  draft: {
    best_attempt: number
    attempts_used: number
    max_attempts: number
    best_score: { passes: number; warns: number; fails: number }
    all_pass: boolean
    anchor_words?: {
      source: 'exact' | 'sibling-genre' | 'sibling-emotion' | 'artist-corpus' | 'corpus' | 'llm-fallback' | 'none'
      bank_slug: string | null
      count: number
    }
    log: Array<{ attempt: number; score?: [number, number, number]; error?: string }>
  }
}
