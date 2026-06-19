import { DescriptorBrowser } from '@/components/browsers/descriptor-browser'

export default function DescriptorsPage() {
  return (
    <div className="space-y-3">
      <h1 className="font-serif text-3xl">Sonic Descriptors</h1>
      <p className="text-sm text-foreground/60">
        Cached vocal + production descriptors. Pinned ones are user-curated and never regenerate.
        Unverified ones came from auto-LLM generation — review and pin or regenerate as needed.
      </p>
      <DescriptorBrowser />
    </div>
  )
}
