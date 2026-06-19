'use client'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import type { SongwriterProfile } from '@/types/song'

export function StepLens({
  genre,
  value,
  onPick,
}: {
  genre: string | undefined
  value: SongwriterProfile | null
  onPick: (lens: SongwriterProfile | null) => void
}) {
  const [profiles, setProfiles] = useState<SongwriterProfile[] | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [allProfiles, setAllProfiles] = useState<SongwriterProfile[]>([])

  useEffect(() => {
    if (!genre) return
    api
      .getSongwriterProfiles(genre)
      .then(setProfiles)
      .catch(() => setProfiles([]))
  }, [genre])

  useEffect(() => {
    if (!showAll || allProfiles.length) return
    api
      .getSongwriterProfiles()
      .then(setAllProfiles)
      .catch(() => setAllProfiles([]))
  }, [showAll, allProfiles.length])

  const list = showAll ? allProfiles : profiles ?? []
  const loading = profiles === null

  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">Songwriter lens (optional)</h2>
      <p className="text-sm text-foreground/60">
        A lens shapes drafting style — strict rhymes, conversational verses, percussive hooks, etc.
      </p>

      {loading && <p className="text-sm text-foreground/40">Loading profiles…</p>}

      {!loading && list.length === 0 && !showAll && (
        <div className="rounded-lg border border-foreground/10 p-4 space-y-2">
          <p className="text-sm">
            No profiles seeded for <span className="font-mono">{genre}</span> yet — Phase 1 ships
            Pop and R&amp;B; the rest land in Phase 2.
          </p>
          <Button variant="secondary" size="sm" onClick={() => setShowAll(true)}>
            Show all profiles anyway
          </Button>
        </div>
      )}

      {list.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {list.map(p => (
            <Card
              key={p.slug}
              onClick={() => onPick(p)}
              className={`cursor-pointer hover:bg-muted/30 ${
                value?.slug === p.slug ? 'border-foreground' : ''
              }`}
            >
              <CardHeader className="pb-1">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  {p.display_name}
                  <span className="text-[10px] uppercase text-foreground/50">{p.role}</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-foreground/70">
                {p.craft_signature?.[0]}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Button variant="ghost" onClick={() => onPick(null)}>
        Skip lens →
      </Button>
    </div>
  )
}
