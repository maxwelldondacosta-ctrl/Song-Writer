import { describe, it, expect } from 'vitest'
import { slugifyTitle, datedSlug } from '@/lib/slug'

describe('slugifyTitle', () => {
  it('lowercases + dashes', () => {
    expect(slugifyTitle('Pull Me Deep')).toBe('pull-me-deep')
  })
  it('strips punctuation', () => {
    expect(slugifyTitle("Don't Look Back!")).toBe('dont-look-back')
  })
  it('collapses whitespace', () => {
    expect(slugifyTitle('  hello   world  ')).toBe('hello-world')
  })
})

describe('datedSlug', () => {
  it('prefixes with ISO date', () => {
    expect(datedSlug('My Song', new Date('2026-04-30T12:00:00Z'))).toBe('2026-04-30-my-song')
  })
  it('falls back to untitled with index', () => {
    expect(datedSlug('', new Date('2026-04-30'), 3)).toBe('2026-04-30-untitled-3')
  })
})
