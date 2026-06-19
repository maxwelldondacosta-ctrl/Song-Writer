'use client'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

const PRESET_ARCS = [
  { slug: 'escalation', hint: 'tension building toward a climax' },
  { slug: 'collapse', hint: 'falling apart, things getting worse' },
  { slug: 'redemption', hint: 'finding a way back / forgiveness' },
  { slug: 'surrender', hint: 'giving in, letting it happen' },
  { slug: 'defiance', hint: 'pushing back, claiming power' },
  { slug: 'nostalgia', hint: 'looking backward, longing for then' },
]

export function StepEmotion({
  value, onChange, onNext, story, onStoryChange,
}: {
  value: string
  onChange: (v: string) => void
  onNext: () => void
  story: { event: string; emotion: string; resolution: string }
  onStoryChange: (field: 'Event' | 'Emotion' | 'Resolution', v: string) => void
}) {
  const isPreset = PRESET_ARCS.some(a => a.slug === value)
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-serif text-2xl">Emotion arc</h2>
        <p className="text-sm text-foreground/60 mt-1">
          Pick a preset (these get tighter phonetic-texture validation) or type your own — anything works.
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 mt-3">
          {PRESET_ARCS.map(a => (
            <Card
              key={a.slug}
              onClick={() => onChange(a.slug)}
              className={`cursor-pointer hover:bg-muted/30 ${value === a.slug ? 'border-foreground' : ''}`}
            >
              <CardContent className="py-2.5 px-3">
                <div className="text-sm font-medium capitalize">{a.slug}</div>
                <div className="text-[11px] text-foreground/60 leading-tight">{a.hint}</div>
              </CardContent>
            </Card>
          ))}
        </div>
        <div className="mt-3 space-y-1">
          <Label className="text-xs">Or describe it your way</Label>
          <Input
            value={isPreset ? '' : value}
            onChange={e => onChange(e.target.value)}
            placeholder="e.g. quiet vindication, manic relief, slow-burn confession"
          />
          {value && !isPreset && (
            <p className="text-[11px] text-foreground/50">
              Custom arcs are classified soft/hard/neutral by Claude on first use (cached per session)
              so the phonetic-texture check still runs against your exact emotion.
            </p>
          )}
        </div>
      </div>
      <div className="space-y-2 pt-2 border-t border-foreground/10">
        <h3 className="font-medium">Story (event → emotion → resolution)</h3>
        <p className="text-xs text-foreground/60">
          The skill uses these to keep narrative consistent across sections. One short phrase each.
        </p>
        <Label className="text-xs">Event</Label>
        <Input value={story.event} onChange={e => onStoryChange('Event', e.target.value)} placeholder="she calls late, voice shaking" />
        <Label className="text-xs">Emotion</Label>
        <Input value={story.emotion} onChange={e => onStoryChange('Emotion', e.target.value)} placeholder="I should know better but I'm pulled in" />
        <Label className="text-xs">Resolution</Label>
        <Input value={story.resolution} onChange={e => onStoryChange('Resolution', e.target.value)} placeholder="I let her in anyway" />
      </div>
      <Button onClick={onNext} disabled={!value.trim()}>Next →</Button>
    </div>
  )
}
