'use client'
import { useEffect, useState } from 'react'
import { Copy, Flag } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import type { VocabBankWord } from '@/types/song'

interface Bank { slug: string; name: string; description: string | null }

export function VocabBrowser() {
  const [banks, setBanks] = useState<Bank[]>([])
  const [active, setActive] = useState<Bank | null>(null)
  const [words, setWords] = useState<VocabBankWord[]>([])
  const [q, setQ] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.listVocabBanks().then(setBanks).catch(e => setError(String(e)))
  }, [])

  useEffect(() => {
    if (!active) { setWords([]); return }
    api.getVocabBankWords(active.slug).then(setWords).catch(e => setError(String(e)))
  }, [active])

  // Group banks by genre prefix (slug looks like "pop.confession")
  const grouped = new Map<string, Bank[]>()
  for (const b of banks) {
    const [genre] = b.slug.split('.')
    const arr = grouped.get(genre) ?? []
    arr.push(b)
    grouped.set(genre, arr)
  }

  const visible = q.trim()
    ? words.filter(w => w.word.toLowerCase().includes(q.toLowerCase()))
    : words

  return (
    <div className="grid grid-cols-12 gap-4">
      <aside className="col-span-3">
        <Card><CardContent className="p-2 space-y-2">
          {error && <p className="text-destructive text-xs">{error}</p>}
          {Array.from(grouped.entries()).sort().map(([genre, list]) => (
            <div key={genre} className="space-y-0.5">
              <div className="text-[10px] uppercase tracking-wider text-foreground/50 px-2 pt-1">{genre}</div>
              {list.map(b => (
                <button
                  key={b.slug}
                  onClick={() => setActive(b)}
                  className={`w-full text-left text-xs px-2 py-1 rounded hover:bg-muted/40 ${
                    active?.slug === b.slug ? 'bg-muted/50 text-foreground' : 'text-foreground/70'
                  }`}
                >
                  {b.name.replace(/^[^/]+\/\s*/, '')}
                </button>
              ))}
            </div>
          ))}
          {banks.length === 0 && (
            <p className="px-2 py-3 text-xs text-foreground/50 italic">No vocab banks loaded.</p>
          )}
        </CardContent></Card>
      </aside>

      <section className="col-span-9">
        {!active ? (
          <Card><CardContent className="p-6 text-sm text-foreground/60">
            Pick a bank to browse its words and phonetic data.
          </CardContent></Card>
        ) : (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base font-medium flex items-baseline justify-between">
                {active.name}
                <span className="text-xs text-foreground/50">{visible.length} of {words.length} words</span>
              </CardTitle>
              {active.description && <p className="text-xs text-foreground/60">{active.description}</p>}
            </CardHeader>
            <CardContent className="space-y-2">
              <Input
                value={q}
                onChange={e => setQ(e.target.value)}
                placeholder="filter words…"
                className="h-7 max-w-xs"
              />
              <div className="rounded border border-foreground/10 overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-muted/30 text-foreground/60">
                    <tr className="text-left">
                      <th className="px-2 py-1.5">Word</th>
                      <th className="px-2 py-1.5">IPA</th>
                      <th className="px-2 py-1.5">Syllables</th>
                      <th className="px-2 py-1.5">Stress</th>
                      <th className="px-2 py-1.5">Vowel</th>
                      <th className="px-2 py-1.5">Attack</th>
                      <th className="px-2 py-1.5">Density</th>
                      <th className="px-2 py-1.5">Flags</th>
                      <th className="px-2 py-1.5"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map(w => (
                      <tr key={w.word} className="border-t border-foreground/10 hover:bg-muted/20">
                        <td className="px-2 py-1.5 font-medium">{w.word}</td>
                        <td className="px-2 py-1.5 font-mono text-foreground/70">{w.ipa || '—'}</td>
                        <td className="px-2 py-1.5 text-foreground/60">{w.syllables}</td>
                        <td className="px-2 py-1.5 font-mono text-foreground/60">{w.stress_pattern || '—'}</td>
                        <td className="px-2 py-1.5 text-foreground/60">{w.vowel_shape || '—'}</td>
                        <td className="px-2 py-1.5">
                          {w.first_syllable_attack && (
                            <Badge variant="outline" className="text-[10px]">{w.first_syllable_attack}</Badge>
                          )}
                        </td>
                        <td className="px-2 py-1.5 text-foreground/60">{w.consonant_density?.toFixed(2)}</td>
                        <td className="px-2 py-1.5">
                          {w.cliche_flag ? <Flag className="h-3 w-3 text-yellow-400 inline mr-1" /> : null}
                          {w.ai_bias_flag ? <Flag className="h-3 w-3 text-red-400 inline" /> : null}
                        </td>
                        <td className="px-2 py-1.5 text-right">
                          <button
                            onClick={() => navigator.clipboard.writeText(w.word)}
                            className="opacity-0 group-hover:opacity-100 hover:opacity-100 text-foreground/50"
                            title="Copy"
                          >
                            <Copy className="h-3 w-3" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  )
}
