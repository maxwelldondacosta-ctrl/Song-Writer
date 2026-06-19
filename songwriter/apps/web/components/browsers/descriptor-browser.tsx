'use client'
import { useEffect, useState } from 'react'
import { Pin, PinOff, RefreshCw, Trash2 } from 'lucide-react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { api, type DescriptorEntry } from '@/lib/api'

const QUALITY_FILTERS = ['', 'pinned', 'reviewed', 'unverified'] as const

export function DescriptorBrowser() {
  const [items, setItems] = useState<DescriptorEntry[]>([])
  const [filter, setFilter] = useState<typeof QUALITY_FILTERS[number]>('')
  const [active, setActive] = useState<DescriptorEntry | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [lookupName, setLookupName] = useState('')

  const refresh = async () => {
    try {
      const data = await api.listDescriptors(filter || undefined)
      setItems(data)
    } catch (e) {
      setError(String(e))
    }
  }

  useEffect(() => { refresh() /* eslint-disable-next-line */ }, [filter])

  const togglePin = async (d: DescriptorEntry) => {
    setBusy(d.normalized_name); setError(null)
    try {
      const fn = d.quality_state === 'pinned' ? api.unpinDescriptor : api.pinDescriptor
      await fn(d.normalized_name)
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }

  const regenerate = async (d: DescriptorEntry) => {
    setBusy(d.normalized_name); setError(null)
    try {
      await api.deleteDescriptor(d.normalized_name)
      await api.getDescriptor(d.canonical_name)  // triggers auto-LLM regenerate
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }

  const remove = async (d: DescriptorEntry) => {
    if (!confirm(`Delete cached descriptor for "${d.canonical_name}"? It'll be regenerated next time it's referenced.`)) return
    setBusy(d.normalized_name); setError(null)
    try {
      await api.deleteDescriptor(d.normalized_name)
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }

  const lookup = async () => {
    if (!lookupName.trim()) return
    setBusy('lookup'); setError(null)
    try {
      await api.getDescriptor(lookupName.trim())
      setLookupName('')
      await refresh()
    } catch (e) {
      setError(String(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 items-center">
        <select
          value={filter}
          onChange={e => setFilter(e.target.value as typeof QUALITY_FILTERS[number])}
          className="h-8 rounded-md bg-input/30 border border-input px-2 text-sm text-foreground"
        >
          <option value="">all states</option>
          <option value="pinned">pinned</option>
          <option value="reviewed">reviewed</option>
          <option value="unverified">unverified</option>
        </select>
        <span className="text-xs text-foreground/50">{items.length} cached</span>
        <div className="flex-1" />
        <Input
          value={lookupName}
          onChange={e => setLookupName(e.target.value)}
          placeholder="add a new artist (will LLM-generate)"
          className="h-8 max-w-xs"
        />
        <Button size="sm" onClick={lookup} disabled={busy !== null || !lookupName.trim()}>
          {busy === 'lookup' ? 'Generating…' : 'Add'}
        </Button>
      </div>

      {error && <p className="text-destructive text-xs">{error}</p>}

      <div className="rounded-md border border-foreground/10 overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-muted/30 text-foreground/60">
            <tr className="text-left">
              <th className="px-2 py-1.5">Name</th>
              <th className="px-2 py-1.5">Source</th>
              <th className="px-2 py-1.5">Quality</th>
              <th className="px-2 py-1.5 text-right">Uses</th>
              <th className="px-2 py-1.5"></th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr><td colSpan={5} className="px-2 py-6 text-center text-foreground/40 italic">
                No cached descriptors yet. Reference an artist by name during drafting and one will be generated.
              </td></tr>
            )}
            {items.map(d => (
              <tr
                key={d.id}
                className="border-t border-foreground/10 hover:bg-muted/20 cursor-pointer"
                onClick={() => setActive(d)}
              >
                <td className="px-2 py-1.5">
                  <div className="font-medium">{d.canonical_name}</div>
                  {d.era_label && <div className="text-[10px] text-foreground/50">{d.era_label}</div>}
                </td>
                <td className="px-2 py-1.5"><Badge variant="outline" className="text-[10px]">{d.source}</Badge></td>
                <td className="px-2 py-1.5">
                  <Badge variant={d.quality_state === 'pinned' ? 'default' : 'secondary'} className="text-[10px]">
                    {d.quality_state}
                  </Badge>
                </td>
                <td className="px-2 py-1.5 text-right text-foreground/60">{d.use_count}</td>
                <td className="px-2 py-1.5 text-right">
                  <div className="flex justify-end gap-0.5">
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={e => { e.stopPropagation(); togglePin(d) }}
                      disabled={busy === d.normalized_name}
                      title={d.quality_state === 'pinned' ? 'Unpin' : 'Pin'}
                    >
                      {d.quality_state === 'pinned' ? <PinOff className="h-3.5 w-3.5" /> : <Pin className="h-3.5 w-3.5" />}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={e => { e.stopPropagation(); regenerate(d) }}
                      disabled={busy === d.normalized_name}
                      title="Regenerate (deletes + re-fetches via LLM)"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={e => { e.stopPropagation(); remove(d) }}
                      disabled={busy === d.normalized_name}
                      title="Delete from cache"
                    >
                      <Trash2 className="h-3.5 w-3.5 text-foreground/50" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {active && <DescriptorDetailModal entry={active} onClose={() => setActive(null)} />}
    </div>
  )
}

function DescriptorDetailModal({ entry, onClose }: { entry: DescriptorEntry; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-40 flex items-center justify-center p-4" onClick={onClose}>
      <Card className="max-w-2xl w-full max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <CardHeader>
          <CardTitle className="text-xl flex items-baseline justify-between gap-2">
            <span>{entry.canonical_name}</span>
            <Badge variant={entry.quality_state === 'pinned' ? 'default' : 'secondary'}>
              {entry.quality_state}
            </Badge>
          </CardTitle>
          {entry.era_label && <p className="text-xs text-foreground/50">{entry.era_label}</p>}
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <section>
            <h3 className="text-xs uppercase text-foreground/50 mb-1">Short ({entry.descriptor_short.split(' ').length} words)</h3>
            <pre className="text-[12px] whitespace-pre-wrap bg-muted/30 rounded p-2 leading-relaxed">
              {entry.descriptor_short}
            </pre>
          </section>
          <section>
            <h3 className="text-xs uppercase text-foreground/50 mb-1">Long</h3>
            <pre className="text-[11px] whitespace-pre-wrap bg-muted/30 rounded p-2 leading-relaxed">
              {entry.descriptor_long}
            </pre>
          </section>
          {entry.vocal_attributes && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Vocal attributes</h3>
              <pre className="text-[11px] bg-muted/30 rounded p-2 overflow-x-auto">
                {JSON.stringify(entry.vocal_attributes, null, 2)}
              </pre>
            </section>
          )}
          {entry.production_attrs && (
            <section>
              <h3 className="text-xs uppercase text-foreground/50 mb-1">Production attributes</h3>
              <pre className="text-[11px] bg-muted/30 rounded p-2 overflow-x-auto">
                {JSON.stringify(entry.production_attrs, null, 2)}
              </pre>
            </section>
          )}
          <div className="flex justify-between items-center pt-2 text-xs text-foreground/50">
            <span>source: {entry.source} · {entry.use_count} uses</span>
            <Button variant="secondary" onClick={onClose}>Close</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
