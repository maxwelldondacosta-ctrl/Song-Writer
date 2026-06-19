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
