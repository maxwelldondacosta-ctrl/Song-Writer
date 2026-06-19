'use client'
import { Link2, AlertTriangle, CheckCircle2, XCircle, Circle } from 'lucide-react'

import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { CohesionValidation } from '@/types/song'

const VERDICT_STYLES = {
  pass: { bg: 'bg-green-700/20 border-green-700/30 text-green-200', Icon: CheckCircle2, label: 'cohesion: pass' },
  warn: { bg: 'bg-yellow-700/20 border-yellow-700/30 text-yellow-200', Icon: AlertTriangle, label: 'cohesion: warn' },
  fail: { bg: 'bg-red-700/20 border-red-700/30 text-red-200', Icon: XCircle, label: 'cohesion: fail' },
  unrun: { bg: 'bg-foreground/5 border-foreground/15 text-foreground/50', Icon: Circle, label: 'cohesion: not run' },
} as const

export function CohesionBanner({ cohesion }: { cohesion: CohesionValidation | undefined }) {
  if (!cohesion || cohesion.verdict === 'unrun') {
    return (
      <Card className="border-dashed">
        <CardContent className="flex items-center gap-2 py-2 px-3 text-xs text-foreground/50">
          <Link2 className="h-3.5 w-3.5" />
          <span>Cohesion not yet checked. Click Validate to check whether sections cohere as one track.</span>
        </CardContent>
      </Card>
    )
  }

  const style = VERDICT_STYLES[cohesion.verdict]
  return (
    <Card className={`border ${style.bg}`}>
      <CardContent className="py-2 px-3 space-y-1.5">
        <div className="flex items-baseline gap-2 text-xs">
          <style.Icon className="h-3.5 w-3.5 self-center" />
          <Badge variant="outline" className="text-[10px] uppercase">{style.label}</Badge>
          {cohesion.summary && (
            <span className="text-foreground/80">{cohesion.summary}</span>
          )}
        </div>
        {cohesion.issues.length > 0 && (
          <ul className="text-[11px] space-y-0.5 pl-5">
            {cohesion.issues.map((issue, i) => (
              <li key={i}>
                <span className="text-foreground/50">
                  {issue.section_ids.length > 0 ? `[${issue.section_ids.join(' → ')}] ` : ''}
                </span>
                {issue.note}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
