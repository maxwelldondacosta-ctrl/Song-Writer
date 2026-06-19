'use client'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Trash2, Sparkles, Copy, GripVertical, Eye, EyeOff, Wand2, X, Wrench } from 'lucide-react'
import {
  DndContext,
  closestCenter,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'
import { ValidationChips } from './validation-chips'
import { api } from '@/lib/api'
import type { Section, Song, VocabBankWord, RhymeScheme } from '@/types/song'

type OverlayMode = 'off' | 'attack' | 'density' | 'vowel'

const OVERLAY_LABELS: Record<OverlayMode, string> = {
  off: 'overlay: off',
  attack: 'overlay: attack',
  density: 'overlay: density',
  vowel: 'overlay: vowel',
}

const OVERLAY_NEXT: Record<OverlayMode, OverlayMode> = {
  off: 'attack',
  attack: 'density',
  density: 'vowel',
  vowel: 'off',
}

interface Props {
  song: Song
  onSectionChange: (sectionId: string, lines: string[], label?: string, cadence?: string, rhymeScheme?: RhymeScheme) => void | Promise<void>
  onDeleteSection: (sectionId: string) => void | Promise<void>
  onAddSection: (label?: string) => void | Promise<void>
  onDraftAll: () => void | Promise<void>
  onDraftSection: (sectionId: string) => void | Promise<void>
  onFixSection: (sectionId: string) => void | Promise<void>
  onDuplicateSection: (sectionId: string) => void | Promise<void>
  onReorderSections: (orderedIds: string[]) => void | Promise<void>
  busy: null | string
  fixing: string | null
}

export function LyricCanvas({
  song,
  onSectionChange,
  onDeleteSection,
  onAddSection,
  onDraftAll,
  onDraftSection,
  onFixSection,
  onDuplicateSection,
  onReorderSections,
  busy,
  fixing,
}: Props) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
  )

  const [overlay, setOverlay] = useState<OverlayMode>('off')
  const [phonetic, setPhonetic] = useState<Record<string, VocabBankWord>>({})

  // Collect every unique lyric word and bulk-fetch phonetics when overlay is active.
  const allWords = useMemo(() => {
    const set = new Set<string>()
    for (const s of song.sections) {
      for (const line of s.lyrics) {
        for (const w of line.split(/\s+/)) {
          const cleaned = w.toLowerCase().replace(/[^a-z']/g, '')
          if (cleaned.length > 1) set.add(cleaned)
        }
      }
    }
    return Array.from(set)
  }, [song.sections])

  useEffect(() => {
    if (overlay === 'off' || allWords.length === 0) return
    const missing = allWords.filter(w => !(w in phonetic))
    if (missing.length === 0) return
    api.lookupWords(missing).then(map => {
      setPhonetic(prev => ({ ...prev, ...map }))
    }).catch(() => { /* swallow — overlay is non-critical */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [overlay, allWords.join(',')])

  const handleDragEnd = (e: DragEndEvent) => {
    const { active, over } = e
    if (!over || active.id === over.id) return
    const ids = song.sections.map(s => s.id)
    const oldIdx = ids.indexOf(String(active.id))
    const newIdx = ids.indexOf(String(over.id))
    if (oldIdx < 0 || newIdx < 0) return
    onReorderSections(arrayMove(ids, oldIdx, newIdx))
  }

  if (song.sections.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="space-y-1">
            <h2 className="text-base font-medium">No sections yet</h2>
            <p className="text-sm text-foreground/70">
              Two ways to start: have the AI write a first draft for you, or add a blank section
              and write it yourself.
            </p>
          </div>
          <div className="flex gap-2">
            <Button onClick={onDraftAll} disabled={busy !== null}>
              <Sparkles className="h-3.5 w-3.5 mr-1" />
              {busy === 'draft' ? 'Drafting…' : 'Generate first draft'}
            </Button>
            <Button variant="secondary" onClick={onAddSection} disabled={busy !== null}>
              + Add blank section
            </Button>
          </div>
          <p className="text-xs text-foreground/50">
            "Generate first draft" scaffolds 4 sections (verse / chorus / verse / chorus) and asks
            Claude to write lyrics that fit your topic, emotion arc, lens, and genre.
          </p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button
          size="sm"
          variant="ghost"
          onClick={() => setOverlay(OVERLAY_NEXT[overlay])}
          title="Cycle phonetic overlay: off → attack → density → vowel"
          className="text-xs h-7"
        >
          {overlay === 'off' ? <EyeOff className="h-3 w-3 mr-1" /> : <Eye className="h-3 w-3 mr-1" />}
          {OVERLAY_LABELS[overlay]}
        </Button>
      </div>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={song.sections.map(s => s.id)} strategy={verticalListSortingStrategy}>
          <div className="space-y-3">
            {song.sections.map(s => (
              <SortableSection
                key={s.id}
                section={s}
                onChange={onSectionChange}
                onDelete={onDeleteSection}
                onDraft={onDraftSection}
                onFix={onFixSection}
                onDuplicate={onDuplicateSection}
                drafting={busy === `draft:${s.id}` || busy === 'draft'}
                fixingThis={fixing === s.id}
                anyBusy={busy !== null || fixing !== null}
                overlay={overlay}
                phonetic={phonetic}
                songId={song.id}
              />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  )
}

function SortableSection(props: {
  section: Section
  onChange: Props['onSectionChange']
  onDelete: Props['onDeleteSection']
  onDraft: (sectionId: string) => void | Promise<void>
  onFix: (sectionId: string) => void | Promise<void>
  onDuplicate: (sectionId: string) => void | Promise<void>
  drafting: boolean
  fixingThis: boolean
  anyBusy: boolean
  overlay: OverlayMode
  phonetic: Record<string, VocabBankWord>
  songId: string
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: props.section.id,
  })

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
    zIndex: isDragging ? 10 : 0,
  }

  return (
    <div ref={setNodeRef} style={style}>
      <SectionEditor
        section={props.section}
        onChange={props.onChange}
        onDelete={props.onDelete}
        onDraft={props.onDraft}
        onFix={props.onFix}
        onDuplicate={props.onDuplicate}
        drafting={props.drafting}
        fixingThis={props.fixingThis}
        anyBusy={props.anyBusy}
        overlay={props.overlay}
        phonetic={props.phonetic}
        songId={props.songId}
        dragHandleProps={{ attributes, listeners }}
      />
    </div>
  )
}

interface DragHandleProps {
  attributes: ReturnType<typeof useSortable>['attributes']
  listeners: ReturnType<typeof useSortable>['listeners']
}

const RHYME_SCHEMES: Array<{ value: RhymeScheme; label: string; title: string }> = [
  { value: 'free',  label: 'free',  title: 'No enforced rhyme scheme' },
  { value: 'AABB', label: 'AABB', title: 'Pairs: lines 1&2 rhyme, 3&4 rhyme' },
  { value: 'ABAB', label: 'ABAB', title: 'Alternating: lines 1&3 rhyme, 2&4 rhyme' },
  { value: 'ABCB', label: 'ABCB', title: 'Only lines 2&4 rhyme (common in folk/rap)' },
  { value: 'AAAA', label: 'AAAA', title: 'All 4 lines share one rhyme (hook-heavy)' },
  { value: 'ABBA', label: 'ABBA', title: 'Envelope: lines 1&4 rhyme, 2&3 rhyme' },
]

function SectionEditor({
  section,
  onChange,
  onDelete,
  onDraft,
  onFix,
  onDuplicate,
  drafting,
  fixingThis,
  anyBusy,
  dragHandleProps,
  overlay,
  phonetic,
  songId,
}: {
  section: Section
  onChange: Props['onSectionChange']
  onDelete: Props['onDeleteSection']
  onDraft: (sectionId: string) => void | Promise<void>
  onFix: (sectionId: string) => void | Promise<void>
  onDuplicate: (sectionId: string) => void | Promise<void>
  drafting: boolean
  fixingThis: boolean
  anyBusy: boolean
  dragHandleProps: DragHandleProps
  overlay: OverlayMode
  phonetic: Record<string, VocabBankWord>
  songId: string
}) {
  const [label, setLabel] = useState(section.label)
  const [cadence, setCadence] = useState(section.cadence_pattern)
  const [rhymeScheme, setRhymeScheme] = useState<RhymeScheme>(section.rhyme_scheme ?? 'free')
  const [text, setText] = useState(section.lyrics.join('\n'))
  const [dirty, setDirty] = useState(false)
  const [altPicker, setAltPicker] = useState<null | { lineIndex: number }>(null)
  const [cursorLine, setCursorLine] = useState(0)
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Compute current cursor line whenever the textarea selection changes
  const updateCursorLine = () => {
    const el = textareaRef.current
    if (!el) return
    const pos = el.selectionStart ?? 0
    const upTo = (text.slice(0, pos).match(/\n/g) || []).length
    setCursorLine(upTo)
  }

  useEffect(() => {
    setLabel(section.label)
    setCadence(section.cadence_pattern)
    setRhymeScheme(section.rhyme_scheme ?? 'free')
    setText(section.lyrics.join('\n'))
    setDirty(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section.id, section.lyrics.join('\n'), section.label, section.cadence_pattern, section.rhyme_scheme])

  const save = () => {
    const lines = text.split('\n').map(l => l.replace(/\s+$/, ''))
    onChange(section.id, lines, label.trim() || section.label, cadence.trim() || section.cadence_pattern, rhymeScheme)
    setDirty(false)
  }

  const locked = section.lock_state === 'locked'
  const empty = !section.lyrics.length || section.lyrics.every(l => !l.trim())
  const hasFails = Object.entries(section.validation)
    .some(([k, v]) => k !== 'warnings' && v === 'fail')

  return (
    <Card>
      {/* Header: only drag handle + label + action buttons — kept narrow so delete is always visible */}
      <CardHeader className="pb-1 flex flex-row items-center gap-2">
        <button
          type="button"
          className="cursor-grab active:cursor-grabbing text-foreground/40 hover:text-foreground/80 px-1 -ml-1 touch-none shrink-0"
          title="Drag to reorder"
          {...dragHandleProps.attributes}
          {...dragHandleProps.listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <Input
          value={label}
          onChange={e => { setLabel(e.target.value); setDirty(true) }}
          disabled={locked}
          className="h-7 text-sm flex-1 min-w-0"
        />
        <div className="flex items-center gap-0.5 shrink-0">
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onDuplicate(section.id)}
            disabled={anyBusy}
            title="Duplicate this section (great for choruses)"
          >
            <Copy className="h-3.5 w-3.5 text-foreground/50" />
          </Button>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onDelete(section.id)}
            disabled={locked || anyBusy}
            title="Delete section"
          >
            <Trash2 className="h-3.5 w-3.5 text-foreground/50" />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-2 pt-1">
        {/* Sub-row: cadence, rhyme scheme, validation chips */}
        <div className="flex items-center gap-2 flex-wrap">
          <Input
            value={cadence}
            onChange={e => { setCadence(e.target.value); setDirty(true) }}
            disabled={locked}
            placeholder="cadence"
            className="h-6 text-xs w-36 font-mono text-foreground/60"
          />
          <select
            value={rhymeScheme}
            onChange={e => { setRhymeScheme(e.target.value as RhymeScheme); setDirty(true) }}
            disabled={locked}
            title="Rhyme scheme — tells the AI how end-lines should rhyme"
            className="h-6 text-xs rounded-md border border-input bg-background px-1.5 font-mono text-foreground/60 focus:outline-none focus:ring-1 focus:ring-ring"
          >
            {RHYME_SCHEMES.map(s => (
              <option key={s.value} value={s.value} title={s.title}>{s.label}</option>
            ))}
          </select>
          <ValidationChips validation={section.validation} />
        </div>
        {overlay !== 'off' && !dirty ? (
          <PhoneticPreview
            text={text}
            mode={overlay}
            phonetic={phonetic}
            onClick={() => { /* clicking overlay swaps to edit */ }}
          />
        ) : (
          <Textarea
            ref={textareaRef}
            value={text}
            onChange={e => { setText(e.target.value); setDirty(true); updateCursorLine() }}
            onSelect={updateCursorLine}
            onClick={updateCursorLine}
            onKeyUp={updateCursorLine}
            disabled={locked}
            rows={Math.max(4, text.split('\n').length + 1)}
            className="font-serif text-lg leading-loose"
            placeholder="One line per row. Empty rows are blank lines."
          />
        )}
        <div className="flex items-center justify-between gap-2">
          {section.validation.warnings.length > 0 ? (
            <ul className="text-xs text-yellow-300/80 space-y-0.5 flex-1">
              {section.validation.warnings.slice(0, 4).map((w, i) => (
                <li key={i}>· {w}</li>
              ))}
            </ul>
          ) : <span className="flex-1" />}
          {hasFails && !empty && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onFix(section.id)}
              disabled={locked || anyBusy}
              title="Re-draft up to 3 times, feeding each validation failure back to Claude until it passes"
              className="text-amber-400 hover:text-amber-300"
            >
              <Wrench className="h-3 w-3 mr-1" />
              {fixingThis ? 'Fixing…' : 'Fix'}
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            onClick={() => onDraft(section.id)}
            disabled={locked || anyBusy}
            title={empty ? 'Generate this section' : 'Redraft this section'}
          >
            <Sparkles className="h-3 w-3 mr-1" />
            {drafting ? 'Drafting…' : (empty ? 'Draft' : 'Redraft')}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              const lyricsLines = text.split('\n')
              const target = Math.min(cursorLine, Math.max(0, lyricsLines.length - 1))
              setAltPicker({ lineIndex: target })
            }}
            disabled={locked || anyBusy || section.lyrics.length === 0}
            title="Get alternatives for the line your cursor is on"
          >
            <Wand2 className="h-3 w-3 mr-1" />
            Line alts {section.lyrics.length > 0 && <span className="text-foreground/40 ml-1">L{cursorLine + 1}</span>}
          </Button>
          <Button
            size="sm"
            variant={dirty ? 'default' : 'secondary'}
            onClick={save}
            disabled={!dirty || locked}
          >
            {dirty ? 'Save' : 'Saved'}
          </Button>
        </div>

        {altPicker && (
          <LineAlternatives
            section={section}
            songId={songId}
            initialIndex={altPicker.lineIndex}
            onClose={() => setAltPicker(null)}
            onPick={(lineIndex, replacement) => {
              const lines = text.split('\n')
              lines[lineIndex] = replacement
              const next = lines.join('\n')
              setText(next)
              const cleanLines = next.split('\n').map(l => l.replace(/\s+$/, ''))
              onChange(section.id, cleanLines, label.trim() || section.label, cadence.trim() || section.cadence_pattern)
              setDirty(false)
              setAltPicker(null)
            }}
          />
        )}
      </CardContent>
    </Card>
  )
}

function LineAlternatives({
  section,
  songId,
  initialIndex,
  onClose,
  onPick,
}: {
  section: Section
  songId: string
  initialIndex: number
  onClose: () => void
  onPick: (lineIndex: number, replacement: string) => void
}) {
  const lineIndex = initialIndex
  const original = section.lyrics[lineIndex] ?? ''
  const [constraint, setConstraint] = useState('')
  const [alts, setAlts] = useState<string[]>([])  // grows as candidates stream in
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const esRef = useRef<EventSource | null>(null)

  const fetchAlts = () => {
    esRef.current?.close()
    setLoading(true); setError(null); setAlts([]); setDone(false)
    const url = api.lineAlternativesStreamUrl(songId, section.id, lineIndex, 3, constraint)
    const es = new EventSource(url)
    esRef.current = es

    es.addEventListener('alt', e => {
      try {
        const payload = JSON.parse((e as MessageEvent).data) as { index: number; text: string }
        setAlts(prev => {
          const next = [...prev]
          next[payload.index] = payload.text
          return next
        })
      } catch { /* ignore malformed event */ }
    })
    es.addEventListener('done', () => {
      setLoading(false); setDone(true)
      es.close(); esRef.current = null
    })
    es.addEventListener('error', e => {
      try {
        const payload = JSON.parse((e as MessageEvent).data) as { message?: string }
        if (payload?.message) setError(payload.message)
      } catch { /* ignore */ }
      setLoading(false)
      es.close(); esRef.current = null
    })
    es.onerror = () => {
      // Network-level error (server gone, CORS, etc.)
      setError(prev => prev ?? 'connection lost')
      setLoading(false)
      es.close(); esRef.current = null
    }
  }

  // Auto-fetch on open
  useEffect(() => {
    fetchAlts()
    return () => { esRef.current?.close(); esRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineIndex])

  // Close on Esc
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="rounded-lg border border-foreground/15 bg-muted/10 px-3 py-2 space-y-2">
      <div className="flex items-baseline justify-between gap-2 text-xs">
        <span className="text-foreground/50">
          Replacing line {lineIndex + 1}:
        </span>
        <Button size="icon" variant="ghost" onClick={onClose} title="Close (Esc)" className="h-6 w-6">
          <X className="h-3 w-3" />
        </Button>
      </div>

      <div className="font-serif text-base text-foreground/60 italic line-through px-1">
        {original || <span className="not-italic">(blank line)</span>}
      </div>

      <div className="flex items-center gap-1.5 pt-1">
        <Input
          value={constraint}
          onChange={e => setConstraint(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') fetchAlts() }}
          placeholder="optional steer: 'more vulnerable', 'sharper image', 'less abstract'"
          className="h-7 text-xs flex-1"
        />
        <Button size="sm" variant="secondary" onClick={fetchAlts} disabled={loading}>
          {loading ? '…' : 'Try again'}
        </Button>
      </div>

      {error && <p className="text-destructive text-xs">{error}</p>}

      <ul className="space-y-0.5 pt-1">
        {[0, 1, 2].map(i => {
          const alt = alts[i]
          if (alt) {
            return (
              <li
                key={i}
                onClick={() => onPick(lineIndex, alt)}
                className="group font-serif text-lg leading-loose text-foreground/55 hover:text-foreground rounded px-2 py-0.5 cursor-pointer hover:bg-foreground/10 transition-colors flex items-baseline gap-2 animate-in fade-in duration-200"
                title="Click to replace"
              >
                <span className="text-[10px] uppercase tracking-wider text-foreground/30 group-hover:text-foreground/60 -mt-0.5 self-center">
                  ⇢
                </span>
                <span className="flex-1">{alt}</span>
              </li>
            )
          }
          // Placeholder slot — visible while we wait for this candidate
          if (loading) {
            return (
              <li
                key={i}
                className="font-serif text-lg leading-loose text-foreground/25 italic px-2 py-0.5 flex items-baseline gap-2"
              >
                <span className="text-[10px] uppercase tracking-wider text-foreground/20 -mt-0.5 self-center animate-pulse">
                  ⇢
                </span>
                <span className="animate-pulse">summoning candidate {i + 1}…</span>
              </li>
            )
          }
          return null
        })}
      </ul>

      {done && alts.filter(Boolean).length === 0 && (
        <p className="text-xs text-foreground/40 italic">no candidates returned</p>
      )}
    </div>
  )
}

function classForWord(w: VocabBankWord | undefined, mode: OverlayMode): string {
  if (!w || mode === 'off') return ''
  if (mode === 'attack') {
    if (w.first_syllable_attack === 'hard') return 'text-orange-300'
    if (w.first_syllable_attack === 'soft') return 'text-sky-300'
    if (w.first_syllable_attack === 'vowel') return 'text-fuchsia-300'
    return ''
  }
  if (mode === 'density') {
    const d = w.consonant_density ?? 0
    if (d >= 0.5) return 'text-orange-300/90'
    if (d >= 0.3) return 'text-orange-200/70'
    if (d >= 0.15) return 'text-foreground/80'
    return 'text-sky-300/80'
  }
  if (mode === 'vowel') {
    const v = w.vowel_shape || ''
    if (v.startsWith('long-') || v.startsWith('diphthong')) return 'text-sky-300'
    if (v.startsWith('short-')) return 'text-orange-300/80'
    if (v === 'rhotic') return 'text-fuchsia-300/80'
    return ''
  }
  return ''
}

function PhoneticPreview({
  text,
  mode,
  phonetic,
  onClick,
}: {
  text: string
  mode: OverlayMode
  phonetic: Record<string, VocabBankWord>
  onClick: () => void
}) {
  const lines = text.split('\n')
  return (
    <div
      onClick={onClick}
      className="font-serif text-lg leading-loose min-h-16 rounded-lg border border-input bg-input/30 px-2.5 py-2"
      title="Toggle overlay off (top-right) to edit"
    >
      {lines.map((line, li) => (
        <div key={li}>
          {line.split(/(\s+)/).map((tok, ti) => {
            if (/^\s+$/.test(tok)) return <span key={ti}>{tok}</span>
            const cleaned = tok.toLowerCase().replace(/[^a-z']/g, '')
            const w = phonetic[cleaned]
            const cls = classForWord(w, mode)
            const stressed = w?.stress_pattern?.includes('1')
            return (
              <span
                key={ti}
                className={`${cls} ${stressed ? 'underline decoration-foreground/40 decoration-1 underline-offset-4' : ''}`}
                title={w ? `${w.ipa} · ${w.first_syllable_attack || '?'} · density ${w.consonant_density?.toFixed(2)}` : 'unknown word'}
              >
                {tok}
              </span>
            )
          })}
          {!line && <span>&nbsp;</span>}
        </div>
      ))}
    </div>
  )
}
