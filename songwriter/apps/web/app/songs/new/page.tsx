import { Wizard } from '@/components/wizard/wizard'
import { api } from '@/lib/api'

export default async function NewSongPage() {
  const genres = await api.getGenres().catch(() => [])
  return <Wizard initialGenres={genres} />
}
