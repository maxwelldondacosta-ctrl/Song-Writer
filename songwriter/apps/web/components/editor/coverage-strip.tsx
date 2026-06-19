'use client'
import { useEffect, useState } from 'react'
import { api, type Coverage } from '@/lib/api'

const TONE: Record<string, { dot: string; tag: string }> = {
  ok:       { dot: 'bg-emerald-500', tag: 'text-emerald-500' },
  missing:  { dot: 'bg-destructive', tag: 'text-destructive' },
  partial:  { dot: 'bg-amber-400',   tag: 'text-amber-400' },
  unset:    { dot: 'bg-foreground/20', tag: 'text-foreground/40' },
  'missing-subgenre': { dot: 'bg-destructive', tag: 'text-destructive' },
  'no-sections': { dot: 'bg-foreground/20', tag: 'text-foreground/40' },
}

function Chip({ label, status }: { label: string; status: string }) {
  const tone = TONE[status] || TONE.unset
  const display = status === 'ok' ? '✓'
    : status === 'unset' ? '·'
    : status === 'no-sections' ? '·'
    : status === 'partial' ? '◐'
    : '⚠'
  return (
    <span className="inline-flex items-center gap-1 text-[11px]" title={status}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${tone.dot}`} />
      <span className="text-foreground/70">{label}</span>
      <span className={tone.tag}>{display}</span>
    </span>
  )
}

export function CoverageStrip({
  songId,
  // re-fetch trigger when song changes
  signature,
}: {
  songId: string
  signature: string
}) {
  const [cov, setCov] = useState<Coverage | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancel = false
    const t = setTimeout(() => {
      api.getCoverage(songId)
        .then(c => { if (!cancel) setCov(c) })
        .catch(e => { if (!cancel) setError(String(e)) })
    }, 250)
    return () => { cancel = true; clearTimeout(t) }
  }, [songId, signature])

  if (error) return null  // silent — nothing useful to surface for a coverage fetch error
  if (!cov) return null

  const items = [
    { key: 'production_fingerprint', label: 'production' },
    { key: 'emotion_tempo',          label: 'emotion-tempo' },
    { key: 'songwriter_lens',        label: 'lens' },
    { key: 'cadence_patterns',       label: 'cadence' },
  ] as const

  const anchorTone = cov.anchor_vocab.source === 'exact' ? TONE.ok
    : cov.anchor_vocab.source === 'none' ? (cov.anchor_vocab.would_use_llm ? TONE.partial : TONE.missing)
    : TONE.partial
  const anchorDisplay = cov.anchor_vocab.source === 'exact' ? '✓'
    : cov.anchor_vocab.source === 'none' ? (cov.anchor_vocab.would_use_llm ? '◐' : '⚠')
    : '◐'
  const anchorLabel = `vocab: ${
    cov.anchor_vocab.source === 'exact' ? 'exact'
      : cov.anchor_vocab.source === 'sibling-genre' ? 'nearest'
      : cov.anchor_vocab.source === 'sibling-emotion' ? 'cross-genre'
      : cov.anchor_vocab.would_use_llm ? 'LLM-fallback' : 'none'
  }`

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded border border-foreground/10 bg-muted/20">
      <span className="text-[11px] text-foreground/50">Coverage:</span>
      {items.map(({ key, label }) => (
        <Chip key={key} label={label} status={cov.items[key]} />
      ))}
      <span className="inline-flex items-center gap-1 text-[11px]" title={cov.anchor_vocab.bank_slug || cov.anchor_vocab.source}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${anchorTone.dot}`} />
        <span className="text-foreground/70">{anchorLabel}</span>
        <span className={anchorTone.tag}>{anchorDisplay}</span>
      </span>
      {!cov.ready && (
        <span className="text-[11px] text-amber-400 ml-auto">
          generation will degrade — see warnings on Suno tab
        </span>
      )}
    </div>
  )
}
