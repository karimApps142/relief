// API client + types for Relief Studio. Same-origin "/api/..." (FastAPI serves the UI
// in prod; Vite proxies in dev). Everything the UI shows comes from these — no mocks.

export type Choice = { value: string; label: string }
export type ParamSpec = {
  name: string
  type: 'number' | 'bool' | 'select' | 'text'
  control: 'slider' | 'stepper' | 'seg' | 'select' | 'switch' | 'textarea'
  default: any
  label: string
  min?: number | null
  max?: number | null
  step?: number | null
  choices?: Array<Choice | string> | null
  group: 'basic' | 'advanced'
  help?: string
  suffix?: string
  placeholder?: string
  depends_on?: { param: string; value: any } | null
}

export type FeatureSchema = {
  id: string
  name: string
  description: string
  inputs: string[]
  needs_image: boolean
  needs_comfy: boolean
  engine: 'local' | 'comfy'
  est_runtime: string
  vram: string
  output_kinds: string[]
  icon: string
  params: ParamSpec[]
}

export type RunMeta = {
  duration_s: number
  dimensions: string
  file_size: string
  model: string
  seed: number | null
  params: Record<string, any>
}
export type RunRecord = {
  job: string
  feature: string
  name: string
  icon: string
  engine: string
  created_at: number
  duration_s: number
  artifacts: Record<string, string>
  thumb: string | null
  meta: RunMeta
}

export type Progress = {
  active: boolean
  engine: 'comfy' | 'local' | null
  value?: number
  max?: number
  node?: string | null
  label?: string
  percent?: number
  phases?: string[]
  phase_idx?: number
  tiles_total?: number
  elapsed?: number
}

export type SystemInfo = {
  available: boolean
  device: string
  vram_total: number
  vram_used: number
  vram_free: number
  vram_percent: number
  util: number
  temp: number
  power: number
  disk_free: number | null
  resident: 'relief' | 'image' | 'idle'
  model_loaded: string
}

export type ModelsStatus = {
  installed: boolean
  models?: Record<string, boolean>
  busy?: boolean
  log?: string[]
  error?: string | null
  done?: boolean
}

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

const j = async (r: Response) => {
  if (!r.ok) throw new Error(`${r.url} → ${r.status}`)
  return r.json()
}
const get = (p: string) => fetch(p).then(j)
const post = (p: string) => fetch(p, { method: 'POST' }).then(j)

export const getFeatures = (): Promise<FeatureSchema[]> => get('/api/features')
export const getProgress = (): Promise<Progress> => get('/api/progress')
export const getSystem = (): Promise<SystemInfo> => get('/api/system')
export const getJobs = (): Promise<RunRecord[]> => get('/api/jobs')

export const getModelsStatus = (): Promise<ModelsStatus> =>
  get('/api/models/status').catch(() => ({ installed: false }))
export const modelsDownload = () => post('/api/models/download')

export const getComfyStatus = (): Promise<ComfyStatus> => get('/api/comfy/status')
export const comfyInstall = () => post('/api/comfy/install')
export const comfyDownload = () => post('/api/comfy/download')
export const comfyStart = () => post('/api/comfy/start')

export async function runFeature(
  id: string,
  file: File | null,
  params: Record<string, any>,
  signal?: AbortSignal,
): Promise<RunRecord> {
  const fd = new FormData()
  if (file) fd.append('file', file)
  fd.append('params', JSON.stringify(params))
  const r = await fetch(`/api/features/${id}/run`, { method: 'POST', body: fd, signal })
  const data = await r.json().catch(() => ({}))
  if (!r.ok || data.error) throw new Error(data.error || `run failed (${r.status})`)
  return data as RunRecord
}

// choices may be ["a"] or [{value,label}] — normalize for rendering
export function choiceList(choices?: Array<Choice | string> | null): Choice[] {
  return (choices || []).map((c) => (typeof c === 'string' ? { value: c, label: c } : c))
}
export function choiceLabel(choices: Array<Choice | string> | null | undefined, value: any): string {
  const c = choiceList(choices).find((x) => x.value === value)
  return c ? c.label : String(value)
}

export function relativeTime(epochSec: number): string {
  const s = Math.max(0, Date.now() / 1000 - epochSec)
  if (s < 45) return 'just now'
  if (s < 90) return '1 min ago'
  if (s < 3600) return `${Math.round(s / 60)} min ago`
  if (s < 7200) return '1 hr ago'
  if (s < 86400) return `${Math.round(s / 3600)} hr ago`
  return `${Math.round(s / 86400)} d ago`
}
