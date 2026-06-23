// API client + types for the modular feature backend (server.py).
// Same-origin "/api/..." works in prod (FastAPI serves the UI) and in dev (Vite proxy).

export type ParamSpec = {
  name: string
  type: 'number' | 'bool' | 'select'
  default: any
  label: string
  min?: number | null
  max?: number | null
  step?: number | null
  choices?: string[] | null
}

export type FeatureSchema = {
  id: string
  name: string
  description: string
  inputs: string[]
  params: ParamSpec[]
}

export type RunResult = {
  job: string
  feature: string
  artifacts: Record<string, string> // name -> URL
}

export async function getFeatures(): Promise<FeatureSchema[]> {
  const r = await fetch('/api/features')
  if (!r.ok) throw new Error(`GET /api/features failed (${r.status})`)
  return r.json()
}

export async function getModelsStatus(): Promise<{ installed: boolean }> {
  try {
    const r = await fetch('/api/models/status')
    return r.ok ? r.json() : { installed: false }
  } catch {
    return { installed: false }
  }
}

export async function runFeature(
  id: string,
  file: File | null,
  params: Record<string, any>,
): Promise<RunResult> {
  const fd = new FormData()
  if (file) fd.append('file', file)
  fd.append('params', JSON.stringify(params))
  const r = await fetch(`/api/features/${id}/run`, { method: 'POST', body: fd })
  const j = await r.json().catch(() => ({}))
  if (!r.ok || j.error) throw new Error(j.error || `run failed (${r.status})`)
  return j as RunResult
}
