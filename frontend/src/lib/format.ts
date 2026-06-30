import type { EducationValue, LinkValue, LocationValue } from './types'

export function formatValue(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>)
      .filter(([, val]) => val !== null && val !== undefined && val !== '')
      .map(([, val]) => String(val))
      .join(', ')
  }
  return String(v)
}

export function formatLocation(v: LocationValue | unknown): string {
  if (!v || typeof v !== 'object') return formatValue(v)
  const loc = v as LocationValue
  return [loc.city, loc.region, loc.country].filter(Boolean).join(', ') || '—'
}

export function formatLink(v: LinkValue | unknown): string {
  if (!v || typeof v !== 'object') return formatValue(v)
  const link = v as LinkValue
  return link.handle ? `${link.kind} · ${link.handle}` : link.url
}

export function formatEducation(v: EducationValue | unknown): string {
  if (!v || typeof v !== 'object') return formatValue(v)
  const e = v as EducationValue
  const head = [e.degree, e.field_of_study, e.institution]
    .filter(Boolean)
    .join(', ')
  const dates = [e.start, e.end].filter(Boolean).join(' – ')
  if (!head && !dates) return '—'
  return dates ? `${head} (${dates})` : head
}

export function confidenceTone(c: number): 'high' | 'mid' | 'low' {
  if (c >= 0.9) return 'high'
  if (c >= 0.75) return 'mid'
  return 'low'
}
