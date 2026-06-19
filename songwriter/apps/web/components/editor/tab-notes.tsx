'use client'
export function TabNotes({ notes }: { notes: string }) {
  return (
    <div className="p-2 text-xs">
      <textarea
        defaultValue={notes}
        readOnly
        className="w-full h-32 bg-muted/30 rounded p-2 text-foreground/80 resize-none"
        placeholder="The skill reads notes from here on next run."
      />
    </div>
  )
}
