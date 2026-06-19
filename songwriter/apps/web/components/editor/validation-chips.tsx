import { Badge } from '@/components/ui/badge'
import type { SectionValidation } from '@/types/song'

const RULES: Array<{ key: keyof SectionValidation; label: string }> = [
  { key: 'singability', label: 'sing' },
  { key: 'cadence', label: 'cadence' },
  { key: 'phonetic_texture', label: 'phon' },
  { key: 'rhyme_cadence', label: 'rhyme' },
  { key: 'story_sentence', label: 'story' },
]

const COLOR = {
  pass: 'bg-green-700/30 text-green-300 border-green-700/40',
  warn: 'bg-yellow-700/30 text-yellow-300 border-yellow-700/40',
  fail: 'bg-red-700/30 text-red-300 border-red-700/40',
  unrun: 'bg-foreground/10 text-foreground/40 border-foreground/15',
}

export function ValidationChips({ validation }: { validation: SectionValidation }) {
  return (
    <div className="flex gap-1">
      {RULES.map(r => (
        <Badge key={r.key} variant="outline" className={`text-[10px] px-1.5 ${COLOR[validation[r.key] as keyof typeof COLOR]}`}>
          {r.label}
        </Badge>
      ))}
    </div>
  )
}
