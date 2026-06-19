'use client'
import { useEffect, useMemo, useState } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import type { Genre, Role, SongwriterProfile } from '@/types/song'

const ROLES: Array<{ slug: Role | ''; label: string }> = [
  { slug: '', label: 'all roles' },
  { slug: 'pure-songwriter', label: 'pure' },
  { slug: 'producer-songwriter', label: 'producer' },
  { slug: 'singer-songwriter', label: 'singer' },
  { slug: 'self-writing-artist', label: 'self-writing' },
]

export function SongwriterBrowser({
  initialProfiles,
  genres,
}: {
  initialProfiles: SongwriterProfile[]
  genres: Genre[]
}) {
  const [profiles, setProfiles] = useState<SongwriterProfile[]>(initialProfiles)
  const [genre, setGenre] = useState<string>('')
  const [role, setRole] = useState<string>('')
  const [q, setQ] = useState('')
  const [active, setActive] = useState<SongwriterProfile | null>(null)

  useEffect(() => {
    api.getSongwriterProfiles(genre || undefined, role || undefined)
      .then(setProfiles)
      .catch(() => setProfiles([]))
  }, [genre, role])

  const filtered = useMemo(() => {
    if (!q.trim()) return profiles
    const needle = q.toLowerCase()
    return profiles.filter(p =>
      p.display_name.toLowerCase().includes(needle) ||
      p.slug.toLowerCase().includes(needle) ||
      (p.craft_signature ?? []).some(s => s.toLowerCase().includes(needle))
    )
  }, [profiles, q])

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={genre}
          onChange={e => setGenre(e.target.value)}
          className="h-8 rounded-md bg-input/30 border border-input px-2 text-sm text-foreground"
        >
          <option value="">all genres</option>
          {genres.map(g => <option key={g.slug} value={g.slug}>{g.name}</option>)}
        </select>
        <select
          value={role}
          onChange={e => setRole(e.target.value)}
          className="h-8 rounded-md bg-input/30 border border-input px-2 text-sm text-foreground"
        >
          {ROLES.map(r => <option key={r.slug} value={r.slug}>{r.label}</option>)}
        </select>
        <Input
          value={q}
          onChange={e => setQ(e.target.value)}
          placeholder="search name or craft signature"
          className="h-8 max-w-xs"
        />
        <span className="text-xs text-foreground/50">{filtered.length} of {profiles.length}</span>
      </div>

      {profiles.length === 0 && (
        <Card><CardContent className="p-6 text-sm text-foreground/60">
          No profiles loaded. Make sure the API is running.
        </CardContent></Card>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map(p => (
          <Card
            key={p.slug}
            onClick={() => setActive(p)}
            className="cursor-pointer hover:bg-muted/30 transition-colors"
          >
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-medium flex items-baseline justify-between gap-2">
                <span>{p.display_name}</span>
                <span className="text-[10px] uppercase text-foreground/50 tracking-wider">{p.role}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              <Badge variant="outline" className="text-[10px]">{p.primary_genre_slug}</Badge>
              <p className="text-xs text-foreground/70 line-clamp-3">
                {p.craft_signature?.[0]}
              </p>
              {p.hook_style && (
                <p className="text-[11px] text-foreground/50 italic">hook: {p.hook_style}</p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {active && (
        <ProfileDetailModal profile={active} onClose={() => setActive(null)} />
      )}
    </div>
  )
}

function ProfileDetailModal({ profile, onClose }: { profile: SongwriterProfile; onClose: () => void }) {
  const adoption = profile.adoption_prompt
  const fingerprint = profile.vocab_fingerprint as Record<string, unknown> | undefined
  const cadences = profile.preferred_cadences ?? []
  return (
    <div
      className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <Card className="max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <CardHeader>
          <CardTitle className="text-xl flex items-baseline justify-between gap-2">
            {profile.display_name}
            <span className="text-xs uppercase text-foreground/50">{profile.role}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          {profile.craft_signature && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Craft signature</h3>
              <ul className="space-y-1">
                {profile.craft_signature.map((line, i) => (
                  <li key={i} className="text-foreground/80">· {line}</li>
                ))}
              </ul>
            </section>
          )}
          {cadences.length > 0 && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Preferred cadences</h3>
              <div className="flex flex-wrap gap-1">
                {cadences.map(c => <Badge key={c} variant="secondary">{c}</Badge>)}
              </div>
            </section>
          )}
          {fingerprint && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Vocab fingerprint</h3>
              <pre className="text-[11px] bg-muted/30 rounded p-2 overflow-x-auto">
                {JSON.stringify(fingerprint, null, 2)}
              </pre>
            </section>
          )}
          {adoption && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Adoption prompt</h3>
              <pre className="text-[11px] whitespace-pre-wrap bg-muted/30 rounded p-2 leading-relaxed">
                {adoption}
              </pre>
            </section>
          )}
          <div className="flex justify-end pt-2">
            <Button variant="secondary" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
