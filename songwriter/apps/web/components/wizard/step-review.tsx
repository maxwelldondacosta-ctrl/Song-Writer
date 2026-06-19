'use client'
import { Button } from '@/components/ui/button'
import type { WizardState } from './wizard'

export function StepReview({ state, onSubmit, submitting, error }: { state: WizardState; onSubmit: () => void; submitting: boolean; error: string | null }) {
  return (
    <div className="space-y-4">
      <h2 className="font-serif text-2xl">Review</h2>
      <dl className="grid grid-cols-2 gap-y-2 text-sm">
        <dt className="text-foreground/50">Genre</dt><dd>{state.genre?.name} → {state.subGenre?.name}</dd>
        <dt className="text-foreground/50">Title</dt><dd>{state.title || '(unset)'}</dd>
        <dt className="text-foreground/50">Topic</dt><dd>{state.topic}</dd>
        <dt className="text-foreground/50">Emotion arc</dt><dd className="capitalize">{state.emotionArc}</dd>
        <dt className="text-foreground/50">Lens</dt><dd>{state.lens?.display_name ?? 'none'}</dd>
      </dl>
      <Button onClick={onSubmit} disabled={submitting}>
        {submitting ? 'Creating…' : 'Create song'}
      </Button>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  )
}
