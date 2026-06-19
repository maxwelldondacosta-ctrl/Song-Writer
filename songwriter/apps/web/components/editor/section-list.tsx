'use client'
import { useMemo } from 'react'
import { Lock, Pencil, FileText, Link2 } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import type { Song } from '@/types/song'

const ICON = { draft: FileText, edited: Pencil, locked: Lock } as const

export function SectionList({ song }: { song: Song }) {
  // Build a map of section_id → list of cohesion issue notes that mention it
  const cohesionIssuesBySection = useMemo(() => {
    const m = new Map<string, string[]>()
    for (const issue of song.cohesion?.issues ?? []) {
      for (const id of issue.section_ids) {
        const arr = m.get(id) ?? []
        arr.push(issue.note)
        m.set(id, arr)
      }
    }
    return m
  }, [song.cohesion])

  return (
    <Card><CardContent className="p-2 space-y-1">
      {song.sections.length === 0 && <p className="text-xs text-foreground/50 p-2">No sections yet — run /song draft.</p>}
      {song.sections.map(s => {
        const Icon = ICON[s.lock_state]
        const issues = cohesionIssuesBySection.get(s.id) ?? []
        const verdict = song.cohesion?.verdict
        const dotColor = verdict === 'fail' ? 'bg-red-400' : 'bg-yellow-400'
        return (
          <div
            key={s.id}
            className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-muted/30 cursor-pointer relative"
            title={issues.length > 0 ? issues.join(' · ') : undefined}
          >
            <Icon className="h-3 w-3 text-foreground/50" />
            <span className="text-sm flex-1 truncate">{s.label}</span>
            {issues.length > 0 && (
              <span
                className={`flex items-center gap-1 text-[10px] ${
                  verdict === 'fail' ? 'text-red-300' : 'text-yellow-300'
                }`}
                aria-label={`${issues.length} cohesion issue(s)`}
              >
                <Link2 className="h-2.5 w-2.5" />
                <span className={`h-1.5 w-1.5 rounded-full ${dotColor}`} />
              </span>
            )}
            <span className="text-[10px] text-foreground/40">{s.cadence_pattern}</span>
          </div>
        )
      })}
    </CardContent></Card>
  )
}
