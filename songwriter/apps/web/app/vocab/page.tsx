import { VocabBrowser } from '@/components/browsers/vocab-browser'

export default function VocabPage() {
  return (
    <div className="space-y-3">
      <h1 className="font-serif text-3xl">Vocab Bank Explorer</h1>
      <p className="text-sm text-foreground/60">
        Curated word lists per genre + theme. Each word carries phonetic data (IPA, stress,
        rhyme class, attack, consonant density) and emotion-shaping flags.
      </p>
      <VocabBrowser />
    </div>
  )
}
