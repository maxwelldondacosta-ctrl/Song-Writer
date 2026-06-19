'use client'
import { useEffect, useState } from 'react'
import { api, type AnchorPreview } from '@/lib/api'
import { Button } from '@/components/ui/button'
import type { Song } from '@/types/song'

const SOURCE_LABEL: Record<AnchorPreview['source'], { tag: string; tone: string; explain: string }> = {
  'exact':            { tag: 'exact bank',      tone: 'text-emerald-500',  explain: 'Direct match in vocab_banks for this genre + emotion.' },
  'sibling-genre':    { tag: 'nearest bank',    tone: 'text-amber-400',    explain: 'No exact match — picked the closest emotion bank within this genre.' },
  'sibling-emotion':  { tag: 'cross-genre',     tone: 'text-amber-400',    explain: 'No same-genre match — pulled the same emotion from another genre.' },
  'artist-corpus':    { tag: 'artist corpus',   tone: 'text-violet-400',   explain: 'Using distinctive vocabulary from this songwriter\'s real lyrics (TF-IDF).' },
  'corpus':           { tag: 'corpus bank',     tone: 'text-violet-400',   explain: 'No emotion match — using genre vocab derived from real song lyrics.' },
  'llm-fallback':     { tag: 'LLM-generated',   tone: 'text-sky-400',      explain: 'No bank matched. Claude generated anchor words for this combo.' },
  'none':             { tag: '⚠ no anchors',    tone: 'text-destructive',  explain: 'No bank matched. Click "Generate via LLM" to ask Claude.' },
}

export function TabVocab({ song }: { song: Song }) {
  const [preview, setPreview] = useState<AnchorPreview | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [generating, setGenerating] = useState(false)

  // Re-fetch whenever genre/emotion/topic changes. Debounce by 250ms so a
  // user typing into the topic field doesn't fire the endpoint per keystroke.
  useEffect(() => {
    let cancel = false
    setLoading(true)
    setError(null)
    const timer = setTimeout(() => {
      api.getAnchorPreview(song.id, false)
        .then(p => { if (!cancel) setPreview(p) })
        .catch(e => { if (!cancel) setError(String(e)) })
        .finally(() => { if (!cancel) setLoading(false) })
    }, 250)
    return () => { cancel = true; clearTimeout(timer) }
  }, [song.id, song.genre, song.intent.emotion_arc, song.intent.topic])

  const onGenerateLLM = async () => {
    setGenerating(true)
    setError(null)
    try {
      const p = await api.getAnchorPreview(song.id, true)
      setPreview(p)
    } catch (e) {
      setError(String(e))
    } finally {
      setGenerating(false)
    }
  }

  if (loading && !preview) return <div className="text-xs p-2 text-foreground/50">Resolving anchors…</div>
  if (error && !preview) return <div className="text-xs p-2 text-destructive">{error}</div>
  if (!preview) return null

  const meta = SOURCE_LABEL[preview.source] ?? { tag: preview.source, tone: 'text-foreground/60', explain: '' }

  return (
    <div className="text-xs space-y-3 p-2">
      <div>
        <div className="flex items-center justify-between gap-2">
          <span className={`font-medium ${meta.tone}`}>{meta.tag}</span>
          <span className="text-foreground/40">
            {preview.count} word{preview.count === 1 ? '' : 's'}
          </span>
        </div>
        <p className="text-foreground/50 mt-0.5 leading-snug">{meta.explain}</p>
        {preview.bank_slug && (
          <p className="text-foreground/40 mt-1 font-mono text-[10px]">
            {preview.bank_slug}
          </p>
        )}
        <p className="text-foreground/40 mt-0.5">
          For: <span className="text-foreground/70">{preview.genre}</span>
          {preview.emotion && <> · <span className="text-foreground/70">{preview.emotion}</span></>}
          {preview.topic && <> · <span className="text-foreground/70 italic">"{preview.topic}"</span></>}
        </p>
      </div>

      {preview.source === 'none' && (
        <Button
          size="sm"
          variant="secondary"
          onClick={onGenerateLLM}
          disabled={generating}
          className="w-full"
        >
          {generating ? 'Asking Claude…' : 'Generate via LLM'}
        </Button>
      )}

      {preview.words.length > 0 && (
        <ul className="space-y-0.5 border-t border-foreground/10 pt-2">
          {preview.words.map(w => (
            <li key={w} className="text-foreground/80">{w}</li>
          ))}
        </ul>
      )}

      {preview.source !== 'none' && preview.source !== 'llm-fallback' && (
        <Button
          size="sm"
          variant="ghost"
          onClick={onGenerateLLM}
          disabled={generating}
          className="w-full text-[11px]"
          title="Ask Claude for an alternative set of anchors tuned to your exact emotion + topic"
        >
          {generating ? 'Asking Claude…' : 'Regenerate via LLM'}
        </Button>
      )}
    </div>
  )
}
