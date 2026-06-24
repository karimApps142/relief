// API client + types for the modular feature backend (server.py).
// Same-origin "/api/..." works in prod (FastAPI serves the UI) and in dev (Vite proxy).

export type ParamSpec = {
  name: string
  type: 'number' | 'bool' | 'select' | 'text'
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
  needs_comfy?: boolean
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

// ---- ComfyUI engine management (install / download / launch from the UI) ----
export type ComfyStatus = {
  installed: boolean
  running: boolean
  dir: string
  url: string
  models: Record<string, boolean>
  busy: boolean
  action: string | null
  log: string[]
  error: string | null
  done: boolean
}

export async function getComfyStatus(): Promise<ComfyStatus> {
  const r = await fetch('/api/comfy/status')
  if (!r.ok) throw new Error(`GET /api/comfy/status failed (${r.status})`)
  return r.json()
}

const post = (path: string) => fetch(path, { method: 'POST' }).then((r) => r.json())
export const comfyInstall = () => post('/api/comfy/install')
export const comfyDownload = () => post('/api/comfy/download')
export const comfyStart = () => post('/api/comfy/start')

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
