import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { LyricCanvas } from '@/components/editor/lyric-canvas'
import type { Song } from '@/types/song'

const empty: Song = {
  id: 'x', title: 'X', created: '', modified: '',
  genre: 'pop', sub_genre: 'alt-pop', songwriter_lens: null,
  intent: { topic: '', emotion_arc: '', story: { event: '', emotion: '', resolution: '' } },
  production: { bpm: 88, structure_template: '', energy_curve: [] },
  sections: [], suno_prompt: { current: '', history: [] }, requests: [], notes: '',
  cohesion: { verdict: 'unrun', summary: '', issues: [] }, last_modified_by: 'ui',
}

const noop = vi.fn()
const baseProps = {
  onSectionChange: noop,
  onDeleteSection: noop,
  onAddSection: (_label?: string) => {},
  onDraftAll: noop,
  onDraftSection: noop,
  onFixSection: noop,
  onDuplicateSection: noop,
  onReorderSections: noop,
  busy: null as null | string,
  fixing: null as null | string,
}

describe('LyricCanvas', () => {
  it('shows the empty-state with Generate-draft + Add-section buttons', () => {
    render(<LyricCanvas song={empty} {...baseProps} />)
    expect(screen.getByRole('button', { name: /generate first draft/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /add blank section/i })).toBeInTheDocument()
  })

  it('renders sections with editable label + cadence inputs', () => {
    const s = { ...empty, sections: [{
      id: 'v1', label: 'Verse 1', lock_state: 'draft' as const, lyrics: ['hello world'],
      cadence_pattern: 'melodic-glide',
      validation: { singability: 'pass' as const, cadence: 'warn' as const, phonetic_texture: 'pass' as const, rhyme_cadence: 'pass' as const, story_sentence: 'unrun' as const, warnings: [] as string[] },
      phonetic_overlay: [],
    }] }
    render(<LyricCanvas song={s} {...baseProps} />)
    expect(screen.getByDisplayValue('Verse 1')).toBeInTheDocument()
    expect(screen.getByDisplayValue('melodic-glide')).toBeInTheDocument()
    expect(screen.getByDisplayValue('hello world')).toBeInTheDocument()
  })
})
