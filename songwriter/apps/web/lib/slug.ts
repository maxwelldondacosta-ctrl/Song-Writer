export function slugifyTitle(title: string): string {
  return title
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
}

export function datedSlug(title: string, date: Date = new Date(), untitledIndex = 1): string {
  const iso = date.toISOString().slice(0, 10)
  const slug = slugifyTitle(title)
  return slug ? `${iso}-${slug}` : `${iso}-untitled-${untitledIndex}`
}
