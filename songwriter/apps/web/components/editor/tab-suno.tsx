'use client'
import { useState } from 'react'
import { Copy, ExternalLink, Sparkles } from 'lucide-react'

import { Button, buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { Song } from '@/types/song'

export function TabSuno({ song }: { song: Song }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])
  const [sources, setSources] = useState<Record<string, string>>({})
  const text = song.suno_prompt.current
  const historyCount = song.suno_prompt.history?.length ?? 0

  const copy = () => navigator.clipboard.writeText(text)

  const generate = async () => {
    setBusy(true); setError(null); setWarnings([]); setSources({})
    try {
      const r = await api.buildSunoPrompt(song.id)
      setWarnings(r.warnings || [])
      setSources(r.sources || {})
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="text-xs space-y-2 p-2">
      <div className="flex items-center justify-between">
        <span className="text-foreground/40">
          {text ? `Suno prompt (${text.length} chars)` : 'No Suno prompt yet'}
        </span>
        {historyCount > 0 && (
          <span className="text-foreground/40">{historyCount} previous</span>
        )}
      </div>

      <pre className="whitespace-pre-wrap font-sans bg-muted/30 p-2 rounded text-[11px] leading-relaxed min-h-[140px]">
        {text || (
          <span className="text-foreground/40 italic">
            Click Generate to assemble a Suno prompt from the genre, lens, production
            fingerprint, and burn-list filtered output.
          </span>
        )}
      </pre>

      <div className="flex gap-1 flex-wrap">
        <Button size="sm" onClick={generate} disabled={busy}>
          <Sparkles className="h-3 w-3 mr-1" />
          {busy ? 'Generating…' : (text ? 'Regenerate' : 'Generate')}
        </Button>
        <Button size="sm" variant="secondary" onClick={copy} disabled={!text}>
          <Copy className="h-3 w-3 mr-1" />Copy
        </Button>
        <a
          href="https://suno.com/create"
          target="_blank"
          rel="noreferrer"
          className={cn(buttonVariants({ size: 'sm', variant: 'secondary' }), !text && 'pointer-events-none opacity-50')}
        >
          <ExternalLink className="h-3 w-3 mr-1" />Open Suno
        </a>
      </div>

      {error && <p className="text-destructive text-[11px]">{error}</p>}

      {sources.emotion_tempo === 'llm-fallback' && (
        <p className="text-[11px] text-sky-400">
          ℹ BPM range + anti-prompts came from Claude (no DB entry for this emotion × sub-genre).
        </p>
      )}

      {warnings.length > 0 && (
        <div className="rounded border border-amber-400/40 bg-amber-400/5 p-2 space-y-0.5">
          <p className="text-amber-400 text-[11px] font-medium">
            ⚠ Prompt assembled with {warnings.length} gap{warnings.length === 1 ? '' : 's'}:
          </p>
          <ul className="list-disc list-inside text-amber-400/90 text-[11px] leading-snug">
            {warnings.map((w, i) => <li key={i}>{w}</li>)}
          </ul>
        </div>
      )}

      <p className="text-[10px] text-foreground/40 pt-1">
        Generation is deterministic templating — no LLM call, no token cost. Pulls from the
        sub-genre&apos;s production fingerprint, the emotion-tempo BPM lock, your songwriter lens,
        and scrubs every burn-list word on the way out.
      </p>
    </div>
  )
}
