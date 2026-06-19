import Link from 'next/link'
import { Music, Plus } from 'lucide-react'

import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function Nav() {
  return (
    <header className="border-b border-border/40">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-medium tracking-tight">
          <Music className="h-4 w-4 text-foreground/70" />
          Songwriter
        </Link>
        <nav className="flex items-center gap-2 text-sm">
          <Link href="/songwriters" className="text-foreground/70 hover:text-foreground">Profiles</Link>
          <Link href="/descriptors" className="text-foreground/70 hover:text-foreground">Descriptors</Link>
          <Link href="/vocab" className="text-foreground/70 hover:text-foreground">Vocab</Link>
          <Link href="/settings" className="text-foreground/70 hover:text-foreground">Settings</Link>
          <Link href="/songs/new" className={cn(buttonVariants({ size: 'sm' }), 'ml-2')}>
            <Plus className="h-3 w-3 mr-1" />New song
          </Link>
        </nav>
      </div>
    </header>
  )
}
