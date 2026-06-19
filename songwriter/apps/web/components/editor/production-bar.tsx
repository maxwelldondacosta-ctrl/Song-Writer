'use client'
import { useEffect, useRef, useState } from 'react'
import { Plus, Minus } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import type { Song } from '@/types/song'

interface Props {
  song: Song
  onProductionChange?: (patch: Partial<Song['production']>) => void | Promise<void>
}

export function ProductionBar({ song, onProductionChange }: Props) {
  const curve = song.production.energy_curve
  const [bpm, setBpm] = useState(String(song.production.bpm ?? 100))

  useEffect(() => {
    setBpm(String(song.production.bpm ?? 100))
  }, [song.production.bpm])

  const commitBpm = () => {
    const n = parseInt(bpm, 10)
    if (Number.isFinite(n) && n >= 30 && n <= 240 && n !== song.production.bpm) {
      onProductionChange?.({ bpm: n })
    } else {
      setBpm(String(song.production.bpm ?? 100))
    }
  }

  const updatePoint = (i: number, value: number) => {
    const clamped = Math.max(0, Math.min(1, value))
    const next = [...curve]
    next[i] = Number(clamped.toFixed(2))
    onProductionChange?.({ energy_curve: next })
  }

  const addPoint = () => {
    const last = curve[curve.length - 1] ?? 0.5
    onProductionChange?.({ energy_curve: [...curve, last] })
  }

  const removePoint = () => {
    if (curve.length <= 1) return
    onProductionChange?.({ energy_curve: curve.slice(0, -1) })
  }

  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-3 text-xs">
        <div className="flex items-center gap-1.5">
          <span className="text-foreground/50">BPM</span>
          <Input
            type="number"
            min={30}
            max={240}
            value={bpm}
            onChange={e => setBpm(e.target.value)}
            onBlur={commitBpm}
            onKeyDown={e => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }}
            className="h-7 w-16 text-sm text-center"
            disabled={!onProductionChange}
          />
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-foreground/50">Structure</span>
          <span className="text-foreground/80">{song.production.structure_template || '(unset)'}</span>
        </div>
        <div className="flex items-center gap-1.5 flex-1">
          <span className="text-foreground/50">Energy</span>
          <EnergyCurveEditor
            curve={curve}
            onChange={(i, v) => updatePoint(i, v)}
            disabled={!onProductionChange}
          />
          {onProductionChange && (
            <div className="flex gap-0.5">
              <Button size="icon" variant="ghost" onClick={removePoint} disabled={curve.length <= 1} title="Remove last point">
                <Minus className="h-3 w-3" />
              </Button>
              <Button size="icon" variant="ghost" onClick={addPoint} title="Add point">
                <Plus className="h-3 w-3" />
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function EnergyCurveEditor({
  curve,
  onChange,
  disabled,
}: {
  curve: number[]
  onChange: (index: number, value: number) => void
  disabled?: boolean
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [dragging, setDragging] = useState<number | null>(null)

  useEffect(() => {
    if (dragging === null) return
    const move = (e: PointerEvent) => {
      const el = ref.current
      if (!el) return
      const rect = el.getBoundingClientRect()
      const y = e.clientY - rect.top
      const v = 1 - y / rect.height
      onChange(dragging, v)
    }
    const up = () => setDragging(null)
    window.addEventListener('pointermove', move)
    window.addEventListener('pointerup', up)
    return () => {
      window.removeEventListener('pointermove', move)
      window.removeEventListener('pointerup', up)
    }
  }, [dragging, onChange])

  return (
    <div
      ref={ref}
      className="flex gap-0.5 items-end h-8 relative select-none"
      style={{ minWidth: `${curve.length * 8}px` }}
    >
      {curve.map((v, i) => (
        <div
          key={i}
          onPointerDown={() => !disabled && setDragging(i)}
          className={`w-1.5 rounded-sm ${disabled ? 'cursor-default' : 'cursor-ns-resize hover:bg-foreground/70'} ${
            dragging === i ? 'bg-foreground/80' : 'bg-foreground/40'
          }`}
          style={{ height: `${Math.max(4, v * 100)}%` }}
          title={`${(v * 100).toFixed(0)}%`}
        />
      ))}
    </div>
  )
}
