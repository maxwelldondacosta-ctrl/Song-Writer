import { api } from '@/lib/api'
import type { SongwriterProfile, Genre } from '@/types/song'
import { SongwriterBrowser } from '@/components/browsers/songwriter-browser'

export default async function SongwritersPage() {
  let profiles: SongwriterProfile[] = []
  let genres: Genre[] = []
  try {
    [profiles, genres] = await Promise.all([
      api.getSongwriterProfiles(),
      api.getGenres(),
    ])
  } catch {
    // server unreachable — empty state shown by the client component
  }

  return (
    <div className="space-y-3">
      <h1 className="font-serif text-3xl">Songwriter Profiles</h1>
      <p className="text-sm text-foreground/60">
        Lenses applied during drafting. Filter by genre or role to find one for your next song.
      </p>
      <SongwriterBrowser initialProfiles={profiles} genres={genres} />
    </div>
  )
}
