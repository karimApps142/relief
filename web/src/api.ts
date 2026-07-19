// API client + types for Relief Studio. Same-origin "/api/..." (FastAPI serves the UI
// in prod; Vite proxies in dev). Everything the UI shows comes from these — no mocks.

export type Choice = { value: string; label: string }
export type ParamSpec = {
  name: string
  type: 'number' | 'bool' | 'select' | 'text' | 'lora'
  control: 'slider' | 'stepper' | 'seg' | 'select' | 'switch' | 'textarea' | 'lora'
  default: any
  label: string
  min?: number | null
  max?: number | null
  step?: number | null
  choices?: Array<Choice | string> | null
  group: 'basic' | 'advanced' | 'hidden'
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
  needs_image2?: boolean
  input_labels?: Record<string, string>
  needs_mesh?: boolean
  needs_audio?: boolean
  needs_comfy: boolean
  engine: 'local' | 'comfy'
  est_runtime: string
  vram: string
  output_kinds: string[]
  icon: string
  guide?: Array<{ h: string; b: string }>
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
  total?: number
  done?: number
  phases?: string[]
  phase_idx?: number
  tiles_total?: number
  tiles_done?: number
  elapsed?: number
  preview?: string | null   // mid-run intermediate image (e.g. the 2.5D-Relief depth map)
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
  resident: 'relief' | 'image' | 'llm' | 'idle'
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
  relight_models?: Record<string, boolean>
  hunyuan3d_models?: Record<string, boolean>
  clarity_models?: Record<string, boolean>
  qwen_edit_models?: Record<string, boolean>
  krea2_edit_models?: Record<string, boolean>
  nodes?: Record<string, boolean>
  busy: boolean
  action: string | null
  log: string[]
  error: string | null
  done: boolean
}

// ---- Chat LLM (Bonsai / llama.cpp) ----
export type LlmModel = {
  key: string
  label: string
  repo: string
  file: string
  size_gb: number
  tag: string
  blurb: string
}
export type LlmSampling = { temperature: number; top_p: number; top_k: number; max_tokens: number }
/** Live byte counter for an in-flight weight download (key is null when idle). */
export type LlmProgress = { key: string | null; label: string | null; done: number; total: number; percent: number }
export type LlmStatus = {
  built: boolean
  running: boolean
  dir: string
  url: string
  loaded: string | null
  ctx: number
  catalog: LlmModel[]
  models: Record<string, boolean>
  progress: LlmProgress
  toolchain: { git: boolean; cmake: boolean; nvcc: boolean; compiler: boolean }
  defaults: LlmSampling & { system_prompt: string }
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
const postJson = (p: string, body: unknown) =>
  fetch(p, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(j)

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
export const comfyInstallKrea2Edit = () => post('/api/comfy/install-krea2-edit')
export const comfyStart = () => post('/api/comfy/start')
export const comfyRestart = () => post('/api/comfy/restart')
export const comfyInterrupt = () => post('/api/comfy/interrupt')

export const getLlmStatus = (): Promise<LlmStatus> => get('/api/llm/status')
export const llmInstall = () => post('/api/llm/install')
export const llmDownload = (models?: string[]) => postJson('/api/llm/download', { models })
export const llmStart = (model: string, ctx?: number) => postJson('/api/llm/start', { model, ctx })
export const llmStop = () => post('/api/llm/stop')

export type ChatMessage = { role: 'system' | 'user' | 'assistant'; content: string }
export type ChatDelta = { content?: string; reasoning?: string }
/** llama.cpp reports real timings on the final chunk — surfaced as the tok/s footer. */
export type ChatTimings = { predicted_n: number; predicted_per_second: number }

/**
 * Stream a completion, invoking `onDelta` per token chunk.
 *
 * SSE is read off `fetch`'s ReadableStream rather than via EventSource because
 * EventSource cannot issue a POST (and the message history has to go in a body).
 * Aborting the signal drops the socket, which is what stops generation server-side.
 */
export async function streamChat(
  messages: ChatMessage[],
  params: Partial<LlmSampling>,
  onDelta: (d: ChatDelta) => void,
  signal: AbortSignal,
): Promise<ChatTimings | null> {
  const r = await fetch('/api/llm/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, params }),
    signal,
  })
  if (!r.ok || !r.body) {
    const detail = await r.json().catch(() => ({}))
    throw new Error(detail.detail || detail.error || `chat failed (${r.status})`)
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let timings: ChatTimings | null = null

  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    // SSE frames are newline-delimited; keep the trailing partial line in the buffer.
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const data = line.slice(5).trim()
      if (!data || data === '[DONE]') continue
      let chunk: any
      try { chunk = JSON.parse(data) } catch { continue }   // ignore keep-alive/partial frames
      if (chunk.error) throw new Error(chunk.error)
      if (chunk.timings) timings = chunk.timings
      const delta = chunk.choices?.[0]?.delta
      if (!delta) continue
      // Thinking models emit reasoning either in its own field (newer llama.cpp) or
      // inline as <think> tags in content — the caller handles the inline case.
      if (delta.reasoning_content) onDelta({ reasoning: delta.reasoning_content })
      if (delta.content) onDelta({ content: delta.content })
    }
  }
  return timings
}

// Custom LoRAs: list the drop-in files, and upload a new .safetensors (drag-drop).
export const getLoras = (): Promise<string[]> =>
  get('/api/loras').then((d) => d.loras || []).catch(() => [])

export type UploadProgress = { loaded: number; total: number; pct: number; speed: number }

// XHR (not fetch) so we get real upload progress: bytes sent + a rolling MB/s.
export function uploadLora(
  file: File,
  onProgress?: (p: UploadProgress) => void,
): Promise<{ saved: string; loras: string[] }> {
  return new Promise((resolve, reject) => {
    const fd = new FormData()
    fd.append('file', file)
    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/loras')
    let lastT = performance.now(), lastLoaded = 0, speed = 0
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return
      const now = performance.now(), dt = now - lastT
      if (dt > 150) { speed = ((e.loaded - lastLoaded) / dt) * 1000; lastT = now; lastLoaded = e.loaded }  // bytes/s
      onProgress?.({ loaded: e.loaded, total: e.total, pct: (e.loaded / e.total) * 100, speed })
    }
    xhr.onload = () => {
      let data: any = {}
      try { data = JSON.parse(xhr.responseText) } catch { /* non-JSON */ }
      if (xhr.status >= 200 && xhr.status < 300 && !data.error && !data.detail) resolve(data)
      else reject(new Error(data.error || data.detail || `upload failed (${xhr.status})`))
    }
    xhr.onerror = () => reject(new Error('network error during upload'))
    xhr.onabort = () => reject(new Error('upload cancelled'))
    xhr.send(fd)
  })
}

export async function runFeature(
  id: string,
  file: File | null,
  params: Record<string, any>,
  signal?: AbortSignal,
  file2?: File | null,
): Promise<RunRecord> {
  const fd = new FormData()
  if (file) fd.append('file', file)
  if (file2) fd.append('file2', file2)
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

// human-friendly duration: 3.4s · 42s · 1m 13s · 1h 05m
export function fmtDur(sec: number): string {
  sec = Math.max(0, sec || 0)
  if (sec < 10) return `${sec.toFixed(1)}s`
  if (sec < 60) return `${Math.round(sec)}s`
  const m = Math.floor(sec / 60)
  if (m < 60) return `${m}m ${String(Math.round(sec % 60)).padStart(2, '0')}s`
  const h = Math.floor(m / 60)
  return `${h}h ${String(m % 60).padStart(2, '0')}m`
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
