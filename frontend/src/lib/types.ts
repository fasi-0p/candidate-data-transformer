// Mirrors the engine's serialized shapes (src/serialize.py, validators/report.py).

export interface Conflict {
  value: unknown
  source: string
  reason: string
}

export interface Tracked<T = unknown> {
  value: T
  confidence: number
  source: string
  method: string
  sources: string[]
  malformed?: boolean
  conflicts?: Conflict[]
}

export interface LocationValue {
  city?: string
  region?: string
  country?: string
}

export interface LinkValue {
  kind: string
  url: string
  handle?: string
}

export interface EducationValue {
  institution?: string
  degree?: string
  field_of_study?: string
  start?: string
  end?: string
}

export interface Candidate {
  candidate_id: string
  full_name: Tracked<string> | null
  headline: Tracked<string> | null
  years_experience: Tracked<number> | null
  location: Tracked<LocationValue> | null
  emails: Tracked<string>[]
  phones: Tracked<string>[]
  skills: Tracked<string>[]
  links: Tracked<LinkValue>[]
  education: Tracked<EducationValue>[]
  record_confidence: number
}

export type Severity = 'error' | 'warning' | 'info'

export interface Issue {
  field: string
  code: string
  message: string
  severity: Severity
}

export interface ValidationReport {
  candidate_id: string
  is_valid: boolean
  issues: Issue[]
}

export interface RunStats {
  records_in: number
  clusters_out: number
  conflicts_found: number
}

export interface RunResult {
  run_id: string
  candidates: Candidate[]
  validation: ValidationReport[]
  timings_ms: Record<string, number>
  stats: RunStats
}

export interface ProjectionSummary {
  id: string
  name: string
  fields: string[]
}
