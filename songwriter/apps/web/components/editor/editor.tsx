'use client'
import { useState } from 'react'
import { ClipboardCopy } from 'lucide-react'

import { useSong } from '@/lib/use-song'
import { api, type DraftResponse } from '@/lib/api'
import { Button } from '@/components/ui/button'
import type { Song, Section, RhymeScheme } from '@/types/song'

import { SectionList } from './section-list'
import { LyricCanvas } from './lyric-canvas'
import { RightRail } from './right-rail'
import { ProductionBar } from './production-bar'
import { CohesionBanner } from './cohesion-banner'
import { DraftAttempts } from './draft-attempts'
import { CoverageStrip } from './coverage-strip'

const SECTION_PRESETS: Array<{ label: string; cadence: string }> = [
  { label: 'Verse 1',    cadence: 'melodic-glide' },
  { label: 'Pre-Chorus', cadence: 'build-climb' },
  { label: 'Chorus',     cadence: 'pop-hook' },
  { label: 'Verse 2',    cadence: 'melodic-glide' },
  { label: 'Bridge',     cadence: 'storytelling' },
  { label: 'Outro',      cadence: 'melodic-glide' },
]

// Map label keywords → cadence so manually-added sections get the right default cadence
const LABEL_TO_CADENCE: Array<[RegExp, string]> = [
  [/chorus|hook|refrain/i, 'pop-hook'],
  [/bridge|breakdown/i,    'storytelling'],
  [/pre.?chorus|pre.?hook/i, 'build-climb'],
  [/outro|coda/i,          'melodic-glide'],
  [/intro/i,               'melodic-glide'],
  [/verse/i,               'melodic-glide'],
]

function cadenceForLabel(label: string): string {
  for (const [re, cadence] of LABEL_TO_CADENCE) {
    if (re.test(label)) return cadence
  }
  return 'melodic-glide'
}

function newSection(label: string): Section {
  return {
    id: `s${Date.now().toString(36)}`,
    label,
    lock_state: 'draft',
    lyrics: ['', '', '', ''],
    cadence_pattern: cadenceForLabel(label),
    validation: {
      singability: 'unrun',
      cadence: 'unrun',
      phonetic_texture: 'unrun',
      rhyme_cadence: 'unrun',
      story_sentence: 'unrun',
      warnings: [],
    },
    phonetic_overlay: [],
  }
}

export function Editor({ slug }: { slug: string }) {
  const { song, setSong, status, error } = useSong(slug)
  const [busy, setBusy] = useState<null | 'save' | 'validate' | 'addSection' | 'draft' | string>(null)
  const [fixing, setFixing] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [lastDraft, setLastDraft] = useState<DraftResponse['draft'] | null>(null)

  if (status === 'loading') return <p className="text-foreground/60">Loading…</p>
  if (status === 'error') return <p className="text-destructive">Error: {error}</p>
  if (!song) return <p className="text-foreground/60">Song not found.</p>

  const flashFor = (msg: string) => {
    setFlash(msg)
    setTimeout(() => setFlash(null), 2500)
  }

  const persist = async (next: Song): Promise<Song> => {
    setBusy('save')
    try {
      const saved = await api.updateSong({ ...next, last_modified_by: 'ui' })
      setSong(saved)
      return saved
    } finally {
      setBusy(null)
    }
  }

  const onSectionChange = async (sectionId: string, lines: string[], label?: string, cadence?: string, rhymeScheme?: RhymeScheme) => {
    const next: Song = {
      ...song,
      sections: song.sections.map(s =>
        s.id === sectionId
          ? {
              ...s,
              lyrics: lines,
              label: label ?? s.label,
              cadence_pattern: cadence ?? s.cadence_pattern,
              rhyme_scheme: rhymeScheme !== undefined ? rhymeScheme : s.rhyme_scheme,
              lock_state: s.lock_state === 'locked' ? 'locked' : 'edited',
            }
          : s,
      ),
    }
    setSong(next) // optimistic
    try {
      await persist(next)
      flashFor('saved')
    } catch (e) {
      flashFor(`save failed: ${e}`)
    }
  }

  const onAddSection = async (label = 'Verse') => {
    const next: Song = { ...song, sections: [...song.sections, newSection(label)] }
    try {
      await persist(next)
      flashFor('section added')
    } catch (e) {
      flashFor(`add failed: ${e}`)
    }
  }

  const onDeleteSection = async (sectionId: string) => {
    const next: Song = { ...song, sections: song.sections.filter(s => s.id !== sectionId) }
    try {
      await persist(next)
      flashFor('section removed')
    } catch (e) {
      flashFor(`delete failed: ${e}`)
    }
  }

  const onDuplicateSection = async (sectionId: string) => {
    const idx = song.sections.findIndex(s => s.id === sectionId)
    if (idx === -1) return
    const src = song.sections[idx]
    const clone: Section = {
      ...src,
      id: `s${Date.now().toString(36)}`,
      label: src.label,
      lock_state: 'draft',
      // Reset validation since the clone is technically a new section
      validation: {
        singability: 'unrun',
        cadence: 'unrun',
        phonetic_texture: 'unrun',
        rhyme_cadence: 'unrun',
        story_sentence: 'unrun',
        warnings: [],
      },
      lyrics: [...src.lyrics],
      phonetic_overlay: [...(src.phonetic_overlay ?? [])],
    }
    const sections = [...song.sections]
    sections.splice(idx + 1, 0, clone)
    const next: Song = { ...song, sections }
    try {
      await persist(next)
      flashFor(`duplicated "${src.label}"`)
    } catch (e) {
      flashFor(`duplicate failed: ${e}`)
    }
  }

  const onProductionChange = async (patch: Partial<Song['production']>) => {
    const next: Song = { ...song, production: { ...song.production, ...patch } }
    setSong(next)
    try {
      await persist(next)
    } catch (e) {
      flashFor(`production update failed: ${e}`)
    }
  }

  const onReorderSections = async (orderedIds: string[]) => {
    const byId = new Map(song.sections.map(s => [s.id, s]))
    const reordered = orderedIds
      .map(id => byId.get(id))
      .filter((s): s is Section => Boolean(s))
    if (reordered.length !== song.sections.length) return
    const next: Song = { ...song, sections: reordered }
    setSong(next) // optimistic
    try {
      await persist(next)
    } catch (e) {
      flashFor(`reorder failed: ${e}`)
    }
  }

  const onDraft = async (sectionId?: string) => {
    setBusy(sectionId ? `draft:${sectionId}` : 'draft')
    try {
      const result = await api.draft(song.id, sectionId)
      setSong(result.song)
      setLastDraft(result.draft)
      const { best_attempt, attempts_used, best_score, all_pass, anchor_words } = result.draft
      const verdict = all_pass ? '✓ all rules pass' : `${best_score.fails} fail · ${best_score.warns} warn · ${best_score.passes} pass`
      const anchorMsg = anchor_words
        ? ({
            'exact':          ` · vocab: ${anchor_words.bank_slug}`,
            'sibling-genre':  ` · vocab: nearest bank ${anchor_words.bank_slug}`,
            'sibling-emotion':` · vocab: cross-genre ${anchor_words.bank_slug}`,
            'artist-corpus':  ` · vocab: artist corpus ${anchor_words.bank_slug}`,
            'corpus':         ` · vocab: corpus bank ${anchor_words.bank_slug}`,
            'llm-fallback':   ` · vocab: LLM-generated`,
            'none':           ` · ⚠ no vocab anchors`,
          }[anchor_words.source] ?? '')
        : ''
      flashFor(`drafted on attempt ${best_attempt}/${attempts_used} — ${verdict}${anchorMsg}`)
    } catch (e) {
      const msg = String(e)
      if (msg.includes('409')) {
        flashFor('nothing to draft — all sections have lyrics. Use the per-section Redraft button.')
      } else {
        flashFor(`draft failed: ${msg}`)
      }
    } finally {
      setBusy(null)
    }
  }

  const onFix = async (sectionId: string) => {
    setFixing(sectionId)
    try {
      const result = await api.draft(song.id, sectionId, 5, true)
      setSong(result.song)
      setLastDraft(result.draft)
      const { best_score, all_pass, attempts_used } = result.draft
      const verdict = all_pass
        ? '✓ fixed — all rules pass'
        : `fixed in ${attempts_used} attempt${attempts_used !== 1 ? 's' : ''} — ${best_score.fails} fail · ${best_score.warns} warn`
      flashFor(verdict)
    } catch (e) {
      flashFor(`fix failed: ${e}`)
    } finally {
      setFixing(null)
    }
  }

  const onValidate = async () => {
    setBusy('validate')
    try {
      // Always include LLM checks — runs Story Rule + cohesion alongside the
      // 4 deterministic engines. Single Validate button covers everything.
      const validated = await api.validate(song.id, true)
      setSong(validated)
      const failures = validated.sections.flatMap(s =>
        Object.entries(s.validation)
          .filter(([k, v]) => k !== 'warnings' && v === 'fail')
          .map(([k]) => `${s.label}:${k}`),
      )
      const cohVerdict = validated.cohesion?.verdict
      const cohMsg = cohVerdict && cohVerdict !== 'unrun' ? ` · cohesion: ${cohVerdict}` : ''
      flashFor((failures.length ? `${failures.length} fail(s): ${failures.join(', ')}` : 'all rules pass ✓') + cohMsg)
    } catch (e) {
      flashFor(`validate failed: ${e}`)
    } finally {
      setBusy(null)
    }
  }

  const copyForSuno = () => {
    const text = song.sections
      .map(s => {
        const lines = s.lyrics.filter(l => l.trim()).join('\n')
        return `[${s.label}]\n${lines}`
      })
      .join('\n\n')
    navigator.clipboard.writeText(text).catch(() => {})
    flashFor('Copied for Suno!')
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-end justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-serif text-3xl">{song.title}</h1>
          <p className="text-sm text-foreground/60">
            {song.sub_genre} · {song.production.bpm} BPM
            {song.songwriter_lens && (
              <>
                {' '}· lens: <span className="text-foreground/80">{song.songwriter_lens}</span>
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {flash && <span className="text-xs text-foreground/60 max-w-[18rem] truncate">{flash}</span>}
          <Button
            size="sm"
            variant="ghost"
            onClick={copyForSuno}
            disabled={song.sections.length === 0}
            title="Copy all lyrics in Suno format ([Section]\nlyrics…)"
          >
            <ClipboardCopy className="h-3.5 w-3.5 mr-1" />
            Copy for Suno
          </Button>
          <div className="flex items-center gap-1">
            {SECTION_PRESETS.map(p => (
              <Button
                key={p.label}
                size="sm"
                variant="ghost"
                onClick={() => onAddSection(p.label)}
                disabled={busy !== null}
                className="text-xs h-7 px-2 text-foreground/60 hover:text-foreground"
                title={`Add ${p.label}`}
              >
                +{p.label.split(' ')[0]}
              </Button>
            ))}
          </div>
          <Button
            size="sm"
            variant="secondary"
            onClick={onValidate}
            disabled={busy !== null}
            title="Run all 5 rules + cohesion check (~10-20s)"
          >
            {busy === 'validate' ? 'Validating…' : 'Validate'}
          </Button>
          <Button size="sm" onClick={() => onDraft()} disabled={busy !== null}>
            {busy === 'draft' ? 'Drafting…' : 'Generate draft'}
          </Button>
        </div>
      </header>
      <CoverageStrip
        songId={song.id}
        signature={`${song.genre}|${song.sub_genre}|${song.intent.emotion_arc}|${song.songwriter_lens || ''}|${song.sections.map(s => s.cadence_pattern).join(',')}`}
      />
      {lastDraft && <DraftAttempts draft={lastDraft} onDismiss={() => setLastDraft(null)} />}
      <CohesionBanner cohesion={song.cohesion} />

      <div className="grid grid-cols-12 gap-4">
        <aside className="col-span-3">
          <SectionList song={song} />
        </aside>
        <section className="col-span-6">
          <LyricCanvas
            song={song}
            onSectionChange={onSectionChange}
            onDeleteSection={onDeleteSection}
            onAddSection={onAddSection}
            onDraftAll={() => onDraft()}
            onDraftSection={onDraft}
            onFixSection={onFix}
            onDuplicateSection={onDuplicateSection}
            onReorderSections={onReorderSections}
            busy={busy}
            fixing={fixing}
          />
        </section>
        <aside className="col-span-3">
          <RightRail song={song} />
        </aside>
      </div>
      <ProductionBar song={song} onProductionChange={onProductionChange} />
    </div>
  )
}
