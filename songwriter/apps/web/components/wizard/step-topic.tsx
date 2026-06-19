'use client'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Button } from '@/components/ui/button'

export function StepTopic({ topic = '', title = '', value, onChange, onNext }: { topic?: string; title?: string; value?: string; onChange: (topic: string, title: string) => void; onNext: () => void }) {
  return (
    <div className="space-y-3">
      <h2 className="font-serif text-2xl">What's it about?</h2>
      <Label className="text-xs">Title (optional)</Label>
      <Input value={title} onChange={e => onChange(value ?? '', e.target.value)} placeholder="Pull Me Deep" />
      <Label className="text-xs">Topic</Label>
      <Textarea value={value ?? ''} onChange={e => onChange(e.target.value, title)} placeholder="A late-night call from an ex you should know better than to answer." rows={3} />
      <Button onClick={onNext} disabled={!(value ?? '').trim()}>Next →</Button>
    </div>
  )
}
