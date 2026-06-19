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
export type RhymeScheme = 'AABB' | 'ABAB' | 'ABCB' | 'AAAA' | 'ABBA' | 'free'

export interface Section {
  id: string
  label: string
  lock_state: LockState
  lyrics: string[]
  cadence_pattern: string
  rhyme_scheme?: RhymeScheme
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
export interface CohesionIssue {
  section_ids: string[]
  note: string
}
export interface CohesionValidation {
  verdict: RuleResult
  summary: string
  issues: CohesionIssue[]
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
  cohesion: CohesionValidation
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
