import Link from 'next/link'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

export interface SongSummary {
  id: string
  title: string
  genre: string
  sub_genre: string
  songwriter_lens: string | null
  modified: string
}

export function SongCard({ song }: { song: SongSummary }) {
  return (
    <Link href={`/songs/${song.id}`}>
      <Card className="hover:bg-muted/30 transition-colors cursor-pointer h-full">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-medium">{song.title}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary" className="text-xs">{song.sub_genre}</Badge>
          {song.songwriter_lens && (
            <Badge variant="outline" className="text-xs">{song.songwriter_lens}</Badge>
          )}
          <span className="ml-auto text-xs text-foreground/50">
            {new Date(song.modified).toLocaleDateString()}
          </span>
        </CardContent>
      </Card>
    </Link>
  )
}
