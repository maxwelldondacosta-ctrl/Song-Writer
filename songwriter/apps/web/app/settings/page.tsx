async function getHealth() {
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/healthz`, { cache: 'no-store' })
    return r.ok ? r.json() : null
  } catch { return null }
}

export default async function SettingsPage() {
  const h = await getHealth()
  return (
    <div className="space-y-3">
      <h1 className="font-serif text-3xl">Settings</h1>
      <dl className="text-sm grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1">
        <dt className="text-foreground/50">API status</dt>
        <dd>{h ? 'reachable' : 'not reachable — start `./start.sh`'}</dd>
        {h && (
          <>
            <dt className="text-foreground/50">DB</dt><dd className="font-mono text-xs">{h.db}</dd>
            <dt className="text-foreground/50">Songs dir</dt><dd className="font-mono text-xs">{h.songs_dir}</dd>
          </>
        )}
      </dl>
    </div>
  )
}
