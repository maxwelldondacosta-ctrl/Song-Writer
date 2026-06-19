import Link from 'next/link'

import { SongCard, type SongSummary } from '@/components/song-card'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Plus } from 'lucide-react'

async function fetchSongs(): Promise<SongSummary[]> {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/songs`, { cache: 'no-store' })
    if (!r.ok) return []
    return r.json()
  } catch { return [] }
}

export default async function Home() {
  const songs = await fetchSongs()
  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <h1 className="font-serif text-3xl">Songs</h1>
        <p className="text-foreground/60 text-sm">
          {songs.length === 0 ? 'No songs yet — start your first one.' : `${songs.length} song${songs.length === 1 ? '' : 's'}`}
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        <Link href="/songs/new" className="block">
          <Card className="hover:bg-muted/30 transition-colors h-full border-dashed">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base font-medium">
                <Plus className="h-4 w-4" /> Start a new song
              </CardTitle>
            </CardHeader>
            <CardContent className="text-sm text-foreground/60">
              Pick a genre, set a topic, optionally apply a songwriter lens.
            </CardContent>
          </Card>
        </Link>
        {songs.map(s => <SongCard key={s.id} song={s} />)}
      </div>
    </div>
  )
}
