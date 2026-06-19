import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SongCard } from '@/components/song-card'

const sample = {
  id: '2026-04-30-pull-me-deep',
  title: 'Pull Me Deep',
  genre: 'rnb',
  sub_genre: 'alt-rnb',
  songwriter_lens: 'frank-ocean',
  modified: '2026-04-30T15:18:00Z',
}

describe('SongCard', () => {
  it('renders title + genre + lens chip', () => {
    render(<SongCard song={sample} />)
    expect(screen.getByText('Pull Me Deep')).toBeInTheDocument()
    expect(screen.getByText(/alt-rnb/)).toBeInTheDocument()
    expect(screen.getByText(/frank-ocean/)).toBeInTheDocument()
  })
})
