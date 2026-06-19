import type { Metadata } from 'next'
import { Geist, EB_Garamond } from 'next/font/google'

import { Nav } from '@/components/nav'
import './globals.css'

const geist = Geist({ subsets: ['latin'], variable: '--font-sans' })
const garamond = EB_Garamond({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-serif' })

export const metadata: Metadata = {
  title: 'Songwriter',
  description: 'A Claude-Code-native songwriting workspace',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${garamond.variable} dark`}>
      <body className="bg-background text-foreground min-h-screen">
        <Nav />
        <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
      </body>
    </html>
  )
}
