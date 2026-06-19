'use client'
import type { DraftResponse } from '@/lib/api'

const SOURCE_TONE: Record<string, string> = {
  'exact':           'text-emerald-500',
  'sibling-genre':   'text-amber-400',
  'sibling-emotion': 'text-amber-400',
  'llm-fallback':    'text-sky-400',
  'none':            'text-destructive',
}

export function DraftAttempts({
  draft,
  onDismiss,
}: {
  draft: DraftResponse['draft']
  onDismiss: () => void
}) {
  const { best_attempt, attempts_used, max_attempts, best_score, all_pass, anchor_words, log } = draft
  const verdictTone = all_pass
    ? 'border-emerald-500/40 bg-emerald-500/5'
    : best_score.fails > 0
      ? 'border-destructive/40 bg-destructive/5'
      : 'border-amber-400/40 bg-amber-400/5'

  return (
    <details className={`rounded border ${verdictTone} text-xs`}>
      <summary className="cursor-pointer flex items-center justify-between gap-3 px-3 py-2 list-none">
        <div className="flex items-center gap-3 flex-wrap">
          <span className="font-medium">Last draft</span>
          <span className="text-foreground/60">
            attempt {best_attempt} of {attempts_used} (cap {max_attempts})
          </span>
          <span className="text-foreground/60">
            {all_pass ? '✓ all rules pass' : `${best_score.fails} fail · ${best_score.warns} warn · ${best_score.passes} pass`}
          </span>
          {anchor_words && (
            <span className={`text-[11px] ${SOURCE_TONE[anchor_words.source] || 'text-foreground/60'}`}>
              vocab: {anchor_words.source}{anchor_words.bank_slug ? ` (${anchor_words.bank_slug})` : ''} — {anchor_words.count} words
            </span>
          )}
        </div>
        <button
          onClick={(e) => { e.preventDefault(); e.stopPropagation(); onDismiss() }}
          className="text-foreground/40 hover:text-foreground/80 px-1"
          title="Dismiss"
          type="button"
        >
          ×
        </button>
      </summary>

      <div className="border-t border-foreground/10 px-3 py-2 space-y-1">
        {log.length === 0 ? (
          <p className="text-foreground/50 italic">No attempt log recorded.</p>
        ) : (
          <ul className="space-y-0.5 font-mono text-[11px]">
            {log.map((entry, i) => (
              <li key={i} className="flex gap-3">
                <span className="text-foreground/50 w-20">attempt {String(entry.attempt)}</span>
                {entry.score && (
                  <span className="text-foreground/80">
                    pass={entry.score[0]} warn={entry.score[1]} fail={entry.score[2]}
                  </span>
                )}
                {entry.error && (
                  <span className="text-destructive">⚠ {entry.error}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  )
}
