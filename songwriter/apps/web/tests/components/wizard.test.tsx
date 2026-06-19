import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Wizard } from '@/components/wizard/wizard'

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}))

describe('Wizard', () => {
  it('renders the genre step first', () => {
    render(<Wizard initialGenres={[{ id: 1, slug: 'pop', name: 'Pop', typical_bpm_min: 90, typical_bpm_max: 130, description: null }]} />)
    expect(screen.getByText('What genre?')).toBeInTheDocument()
    expect(screen.getByText('Pop')).toBeInTheDocument()
  })
})
