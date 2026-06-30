// Typed wrappers over the FastAPI engine (src/api/app.py). The UI's only job is
// to render the engine's explainability — these helpers keep fetch noise out of
// the components.

import type { ProjectionSummary, RunResult } from './types'

export interface RunInput {
  csv: File[]
  resume: File[]
  ats: File[]
  notes: File[]
  github: string
  linkedin: string
}

async function asError(resp: Response): Promise<never> {
  let detail = resp.statusText
  try {
    const body = await resp.json()
    if (body?.detail) detail = body.detail
  } catch {
    /* non-JSON error body — keep statusText */
  }
  throw new Error(detail)
}

export async function fetchProjections(): Promise<ProjectionSummary[]> {
  const resp = await fetch('/api/projections')
  if (!resp.ok) return asError(resp)
  const data = await resp.json()
  return data.projections ?? []
}

export async function runPipeline(input: RunInput): Promise<RunResult> {
  const form = new FormData()
  for (const f of input.csv) form.append('csv', f)
  for (const f of input.resume) form.append('resume', f)
  for (const f of input.ats) form.append('ats', f)
  for (const f of input.notes) form.append('notes', f)
  if (input.github.trim()) form.append('github', input.github.trim())
  if (input.linkedin.trim()) form.append('linkedin', input.linkedin.trim())

  const resp = await fetch('/api/run', { method: 'POST', body: form })
  if (!resp.ok) return asError(resp)
  return resp.json()
}

export async function applyProjection(
  runId: string,
  projectionId: string,
): Promise<unknown[]> {
  const resp = await fetch('/api/project', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, projection_id: projectionId }),
  })
  if (!resp.ok) return asError(resp)
  const data = await resp.json()
  return data.output ?? []
}
