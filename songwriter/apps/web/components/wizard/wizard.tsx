'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

import { Button } from '@/components/ui/button'
import { api } from '@/lib/api'
import { datedSlug } from '@/lib/slug'
import type { Genre, Song, SubGenre, SongwriterProfile } from '@/types/song'

import { StepGenre } from './step-genre'
import { StepSubGenre } from './step-sub-genre'
import { StepTopic } from './step-topic'
import { StepEmotion } from './step-emotion'
import { StepLens } from './step-lens'
import { StepReview } from './step-review'

export interface WizardState {
  genre: Genre | null
  subGenre: SubGenre | null
  title: string
  topic: string
  emotionArc: string
  lens: SongwriterProfile | null
  storyEvent: string
  storyEmotion: string
  storyResolution: string
}

const empty: WizardState = {
  genre: null, subGenre: null, title: '', topic: '', emotionArc: '',
  lens: null, storyEvent: '', storyEmotion: '', storyResolution: '',
}

export function Wizard({ initialGenres }: { initialGenres: Genre[] }) {
  const router = useRouter()
  const [state, setState] = useState<WizardState>(empty)
  const [step, setStep] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const update = (patch: Partial<WizardState>) => setState(s => ({ ...s, ...patch }))

  const create = async () => {
    if (!state.genre || !state.subGenre) return
    setSubmitting(true); setError(null)
    const slug = datedSlug(state.title || state.topic)
    const song: Song = {
      id: slug,
      title: state.title || state.topic.slice(0, 60),
      created: new Date().toISOString(),
      modified: new Date().toISOString(),
      genre: state.genre.slug,
      sub_genre: state.subGenre.slug,
      songwriter_lens: state.lens?.slug ?? null,
      intent: {
        topic: state.topic,
        emotion_arc: state.emotionArc,
        story: { event: state.storyEvent, emotion: state.storyEmotion, resolution: state.storyResolution },
      },
      production: { bpm: state.subGenre.typical_bpm_min ?? 100, structure_template: '', energy_curve: [] },
      sections: [],
      suno_prompt: { current: '', history: [] },
      requests: [],
      notes: '',
      cohesion: { verdict: 'unrun', summary: '', issues: [] },
      last_modified_by: 'ui',
    }
    try {
      await api.createSong(song)
      router.push(`/songs/${slug}`)
    } catch (e) {
      setError(String(e))
      setSubmitting(false)
    }
  }

  const steps = [
    <StepGenre key="g" genres={initialGenres} value={state.genre} onPick={g => { update({ genre: g, subGenre: null }); setStep(1) }} />,
    <StepSubGenre key="sg" genre={state.genre} value={state.subGenre} onPick={sg => { update({ subGenre: sg }); setStep(2) }} />,
    <StepTopic key="t" value={state.topic} title={state.title} onChange={(topic, title) => update({ topic, title })} onNext={() => setStep(3)} />,
    <StepEmotion
      key="e"
      value={state.emotionArc}
      onChange={emotion => update({ emotionArc: emotion })}
      onNext={() => setStep(4)}
      story={{ event: state.storyEvent, emotion: state.storyEmotion, resolution: state.storyResolution }}
      onStoryChange={(field, v) => update({ [`story${field}`]: v } as Partial<WizardState>)}
    />,
    <StepLens key="l" genre={state.genre?.slug} value={state.lens} onPick={lens => { update({ lens }); setStep(5) }} />,
    <StepReview key="r" state={state} onSubmit={create} submitting={submitting} error={error} />,
  ]

  return (
    <div className="space-y-6">
      <div className="flex gap-1.5">
        {steps.map((_, i) => (
          <div key={i} className={`h-1 flex-1 rounded ${i <= step ? 'bg-foreground/80' : 'bg-foreground/15'}`} />
        ))}
      </div>
      {steps[step]}
      {step > 0 && step < 5 && (
        <Button variant="ghost" size="sm" onClick={() => setStep(s => Math.max(0, s - 1))}>← back</Button>
      )}
    </div>
  )
}
