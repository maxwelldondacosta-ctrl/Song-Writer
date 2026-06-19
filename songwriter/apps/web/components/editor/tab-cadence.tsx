'use client'
import { useEffect, useState } from 'react'

import { api } from '@/lib/api'
import type { CadencePattern, Song } from '@/types/song'

export function TabCadence({ song }: { song?: Song }) {
  const [patterns, setPatterns] = useState<CadencePattern[]>([])
  useEffect(() => {
    api.getCadencePatterns().then(setPatterns).catch(() => setPatterns([]))
  }, [])

  if (!song) {
    return <p className="p-2 text-xs text-foreground/40 italic">no song loaded</p>
  }

  const used = new Set(song.sections.map(s => s.cadence_pattern))

  return (
    <div className="p-2 space-y-3 text-xs">
      <div>
        <div className="text-foreground/40 mb-1">Cadences in this song</div>
        <div className="space-y-2">
          {song.sections.map(s => {
            const cp = patterns.find(p => p.slug === s.cadence_pattern)
            return (
              <div key={s.id} className="border border-foreground/10 rounded p-2 space-y-1">
                <div className="flex items-baseline justify-between">
                  <span className="font-medium">{s.label}</span>
                  <span className="font-mono text-foreground/60">{s.cadence_pattern}</span>
                </div>
                {cp ? (
                  <>
                    <BeatGrid template={cp.stress_template} />
                    <div className="text-foreground/50 flex flex-wrap gap-x-3 gap-y-0.5">
                      <span>~{cp.syllable_template} syll/line</span>
                      {cp.rhyme_compatibility?.end && (
                        <span>end-rhyme: {cp.rhyme_compatibility.end.join(', ')}</span>
                      )}
                    </div>
                    {(cp.example_lines?.length ?? 0) > 0 && (
                      <div className="text-foreground/40 italic">
                        e.g. &quot;{cp.example_lines[0]}&quot;
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-foreground/40 italic">unknown cadence — try one of the patterns below</p>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div>
        <div className="text-foreground/40 mb-1">All cadence patterns ({patterns.length})</div>
        <div className="space-y-1.5">
          {patterns.map(p => (
            <div
              key={p.slug}
              className={`border rounded p-2 space-y-1 ${
                used.has(p.slug) ? 'border-foreground/30 bg-muted/20' : 'border-foreground/10'
              }`}
            >
              <div className="flex items-baseline justify-between">
                <span className="font-medium">{p.name}</span>
                <span className="font-mono text-foreground/50 text-[10px]">{p.slug}</span>
              </div>
              <BeatGrid template={p.stress_template} compact />
              <div className="text-foreground/40 flex flex-wrap gap-x-3 text-[10px]">
                <span>~{p.syllable_template}</span>
                <span>{(p.typical_genres || []).slice(0, 4).join(', ')}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-[11px] text-foreground/40">
        To change a section&apos;s cadence, edit the cadence input next to its label in the canvas.
      </p>
    </div>
  )
}

function BeatGrid({ template, compact = false }: { template: string; compact?: boolean }) {
  if (!template || template === '?') {
    return <div className="text-[10px] text-foreground/40 italic">flexible</div>
  }
  const cells = template.split('')
  const cellW = compact ? 'w-2' : 'w-3'
  const cellH = compact ? 'h-2' : 'h-3'
  return (
    <div className="flex gap-0.5 items-end">
      {cells.map((c, i) => (
        <div
          key={i}
          className={`${cellW} ${cellH} rounded-sm ${
            c === '1'
              ? 'bg-foreground/80'
              : c === '0'
              ? 'bg-foreground/20'
              : 'bg-foreground/40 ring-1 ring-foreground/10'
          }`}
          title={c === '1' ? 'stressed' : c === '0' ? 'unstressed' : 'wildcard'}
        />
      ))}
    </div>
  )
}
