'use client'
import type { Genre } from '@/types/song'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function StepGenre({ genres, value, onPick }: { genres: Genre[]; value: Genre | null; onPick: (g: Genre) => void }) {
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">What genre?</h2>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {genres.map(g => (
          <Card key={g.slug} onClick={() => onPick(g)} className={`cursor-pointer hover:bg-muted/30 ${value?.slug === g.slug ? 'border-foreground' : ''}`}>
            <CardHeader className="pb-1"><CardTitle className="text-base font-medium">{g.name}</CardTitle></CardHeader>
            <CardContent className="text-xs text-foreground/60">{g.typical_bpm_min}–{g.typical_bpm_max} BPM</CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
