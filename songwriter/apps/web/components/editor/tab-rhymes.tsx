'use client'
import { useEffect, useMemo, useState } from 'react'
import { Copy } from 'lucide-react'

import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { api, ApiError } from '@/lib/api'
import type { Song, VocabBankWord } from '@/types/song'

interface RhymeResult { rhyme_class: string; words: VocabBankWord[] }

export function TabRhymes({ song }: { song?: Song }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<RhymeResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const lineEnds = useMemo(() => {
    if (!song) return [] as string[]
    const endings = new Set<string>()
    for (const s of song.sections) {
      for (const line of s.lyrics) {
        const last = line.trim().split(/\s+/).pop() || ''
        const cleaned = last.replace(/[^a-zA-Z']/g, '').toLowerCase()
        if (cleaned.length > 1) endings.add(cleaned)
      }
    }
    return Array.from(endings).slice(0, 16)
  }, [song])

  const fetchRhymes = async (word: string) => {
    if (!word.trim()) return
    setLoading(true); setError(null); setResults(null)
    try {
      const r = await api.getRhymes(word.trim().toLowerCase(), 80)
      setResults(r)
    } catch (e) {
      setError(e instanceof ApiError ? `${e.status}: ${e.body || 'no rhyme data'}` : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (lineEnds.length && !query) {
      setQuery(lineEnds[lineEnds.length - 1])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lineEnds.length])

  const grouped = useMemo(() => {
    if (!results) return new Map<number, VocabBankWord[]>()
    const m = new Map<number, VocabBankWord[]>()
    for (const w of results.words) {
      const arr = m.get(w.syllables) ?? []
      arr.push(w)
      m.set(w.syllables, arr)
    }
    return new Map(Array.from(m.entries()).sort((a, b) => a[0] - b[0]))
  }, [results])

  const copy = (w: string) => navigator.clipboard.writeText(w)

  return (
    <div className="p-2 space-y-2 text-xs">
      <form
        onSubmit={e => { e.preventDefault(); fetchRhymes(query) }}
        className="flex gap-1"
      >
        <Input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="type a word…"
          className="h-7 text-xs flex-1"
        />
        <Button type="submit" size="sm" disabled={loading || !query.trim()}>
          {loading ? '…' : 'Find'}
        </Button>
      </form>

      {lineEnds.length > 0 && (
        <div>
          <div className="text-foreground/40 mb-1">Line endings in this song</div>
          <div className="flex flex-wrap gap-1">
            {lineEnds.map(w => (
              <button
                key={w}
                onClick={() => { setQuery(w); fetchRhymes(w) }}
                className="text-[10px] px-1.5 py-0.5 rounded bg-muted/40 hover:bg-muted/60 text-foreground/70"
              >
                {w}
              </button>
            ))}
          </div>
        </div>
      )}

      {error && <p className="text-destructive text-[11px]">{error}</p>}

      {results && (
        <div className="space-y-2">
          <div className="text-foreground/40">
            Rhyme class: <span className="font-mono text-foreground/70">{results.rhyme_class}</span>
            <span className="ml-2">{results.words.length} matches</span>
          </div>
          {grouped.size === 0 ? (
            <p className="text-foreground/40 italic">no rhymes found</p>
          ) : (
            Array.from(grouped.entries()).map(([syl, words]) => (
              <div key={syl} className="space-y-1">
                <div className="text-foreground/50 text-[10px] uppercase tracking-wider">
                  {syl}-syll · {words.length}
                </div>
                <div className="flex flex-wrap gap-1">
                  {words.slice(0, 30).map(w => (
                    <button
                      key={w.word}
                      onClick={() => copy(w.word)}
                      className="group text-[11px] px-1.5 py-0.5 rounded bg-muted/30 hover:bg-muted/60 text-foreground/80 inline-flex items-center gap-1"
                      title={`${w.ipa} · ${w.first_syllable_attack || '?'} attack · density ${w.consonant_density?.toFixed(2)}`}
                    >
                      {w.word}
                      <Copy className="h-2.5 w-2.5 opacity-0 group-hover:opacity-60" />
                    </button>
                  ))}
                  {words.length > 30 && (
                    <span className="text-foreground/40 text-[10px] self-center">+{words.length - 30}</span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {!results && !loading && !error && (
        <p className="text-foreground/40 italic">
          Type a word or click a line-ending to find rhymes from the full English dictionary.
        </p>
      )}
    </div>
  )
}
