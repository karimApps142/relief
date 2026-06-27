// useStudio — all app state wired to real endpoints: feature schemas, per-feature param
// values + image, the run state machine (submit → live progress → result/error), and
// background polling for comfy/models/system/jobs. No simulated data.
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  FeatureSchema, RunRecord, Progress, SystemInfo, ModelsStatus, ComfyStatus,
  getFeatures, getProgress, getSystem, getJobs, getModelsStatus, modelsDownload,
  getComfyStatus, comfyInstall, comfyDownload, comfyStart, comfyRestart, comfyInterrupt,
  runFeature, fmtDur,
} from './api'

export type RunState = 'idle' | 'submitting' | 'running' | 'result' | 'error'
export type Toast = { id: number; tone: string; msg: string }

function defaultsFor(f: FeatureSchema): Record<string, any> {
  const o: Record<string, any> = {}
  for (const p of f.params) o[p.name] = p.default
  return o
}

export function useStudio() {
  const [features, setFeatures] = useState<FeatureSchema[]>([])
  const [activeId, setActiveId] = useState('')
  const [values, setValues] = useState<Record<string, Record<string, any>>>({})
  const [files, setFiles] = useState<Record<string, File | null>>({})
  const [previews, setPreviews] = useState<Record<string, string>>({})
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [sysOpen, setSysOpen] = useState(false)

  const [runState, setRunState] = useState<RunState>('idle')
  const [record, setRecord] = useState<RunRecord | null>(null)
  const [error, setError] = useState('')
  const [progress, setProgress] = useState<Progress | null>(null)
  const [elapsed, setElapsed] = useState(0)

  const [comfy, setComfy] = useState<ComfyStatus | null>(null)
  const [models, setModels] = useState<ModelsStatus | null>(null)
  const [system, setSystem] = useState<SystemInfo | null>(null)
  const [jobs, setJobs] = useState<RunRecord[]>([])
  const [toasts, setToasts] = useState<Toast[]>([])
  const [bootErr, setBootErr] = useState('')

  const tid = useRef(0)
  const abortRef = useRef<AbortController | null>(null)
  const t0 = useRef(0)
  const runId = useRef(0)   // invalidates a superseded/cancelled in-flight run

  const addToast = useCallback((tone: string, msg: string) => {
    const id = ++tid.current
    setToasts((t) => [...t, { id, tone, msg }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4600)
  }, [])

  // ---- bootstrap: feature schemas ----
  useEffect(() => {
    getFeatures().then((fs) => {
      setFeatures(fs)
      setActiveId((a) => a || fs[0]?.id || '')
      const v: Record<string, Record<string, any>> = {}
      fs.forEach((f) => { v[f.id] = defaultsFor(f) })
      setValues(v)
    }).catch((e) => setBootErr(e.message))
    refreshJobs()
  }, [])

  const active = features.find((f) => f.id === activeId) || null

  // ---- background polling ----
  const refreshComfy = useCallback(() => { getComfyStatus().then(setComfy).catch(() => {}) }, [])
  const refreshModels = useCallback(() => { getModelsStatus().then(setModels).catch(() => {}) }, [])
  const refreshSystem = useCallback(() => { getSystem().then(setSystem).catch(() => {}) }, [])
  const refreshJobs = useCallback(() => { getJobs().then(setJobs).catch(() => {}) }, [])

  // one cheap poll loop for engine/models/system (stable deps → no interval churn)
  useEffect(() => {
    const tick = () => { refreshComfy(); refreshModels(); refreshSystem() }
    tick()
    const t = setInterval(tick, 2800)
    return () => clearInterval(t)
  }, [refreshComfy, refreshModels, refreshSystem])

  // ---- run flow ----
  const running = runState === 'submitting' || runState === 'running'

  useEffect(() => {
    if (!running) return
    let alive = true
    const tick = async () => {
      try {
        const p = await getProgress()
        if (!alive) return
        setProgress(p)
        if (p.active) setRunState((s) => (s === 'submitting' ? 'running' : s))
      } catch { /* ignore */ }
    }
    tick()
    const tp = setInterval(tick, 400)
    const te = setInterval(() => setElapsed((performance.now() - t0.current) / 1000), 100)
    return () => { alive = false; clearInterval(tp); clearInterval(te) }
  }, [running])

  const generate = useCallback(async () => {
    const f = active
    if (!f || running) return
    if (f.needs_image && !files[f.id]) return
    const myId = ++runId.current
    t0.current = performance.now()
    setError(''); setRecord(null); setProgress(null); setElapsed(0); setRunState('submitting')
    // fallback so fast jobs (no progress.active tick) still flip to 'running'
    setTimeout(() => { if (runId.current === myId) setRunState((s) => (s === 'submitting' ? 'running' : s)) }, 700)
    const ac = new AbortController(); abortRef.current = ac
    try {
      const rec = await runFeature(f.id, files[f.id] || null, values[f.id] || {}, ac.signal)
      if (runId.current !== myId) return        // cancelled/superseded → drop this result
      setRecord(rec); setRunState('result')
      addToast('success', `${f.name} complete · ${fmtDur(rec.meta.duration_s)}`)
      refreshJobs(); refreshSystem()
    } catch (e: any) {
      if (runId.current !== myId) return         // cancelled → ignore (cancel already reset)
      setError(e.message || String(e)); setRunState('error'); addToast('danger', `${f.name} failed`)
    }
  }, [active, running, files, values, addToast, refreshJobs, refreshSystem])

  const cancel = useCallback(() => {
    runId.current++                              // invalidate the in-flight run
    abortRef.current?.abort()
    comfyInterrupt().catch(() => {})             // stop the GPU work if it's a ComfyUI job
    setRunState('idle'); setError(''); setProgress(null)
    addToast('info', 'Run cancelled.')
  }, [addToast])

  // ---- actions ----
  const selectFeature = useCallback((id: string) => {
    if (id === activeId) return
    setActiveId(id); setAdvancedOpen(false); setRunState('idle'); setRecord(null); setError(''); setProgress(null)
  }, [activeId])

  const setVal = useCallback((name: string, v: any) => {
    setValues((s) => ({ ...s, [activeId]: { ...s[activeId], [name]: v } }))
  }, [activeId])

  const onUpload = useCallback((file: File) => {
    setFiles((s) => ({ ...s, [activeId]: file }))
    setPreviews((s) => {
      if (s[activeId]) URL.revokeObjectURL(s[activeId])   // free the prior preview
      return { ...s, [activeId]: URL.createObjectURL(file) }
    })
  }, [activeId])

  const downloadWeights = useCallback(() => {
    modelsDownload().then(() => { refreshModels(); addToast('info', 'Downloading depth weights…') }).catch(() => {})
  }, [refreshModels, addToast])

  const doComfy = useCallback((which: 'install' | 'download' | 'start' | 'restart') => {
    const fn = which === 'install' ? comfyInstall : which === 'download' ? comfyDownload
      : which === 'restart' ? comfyRestart : comfyStart
    fn().then(refreshComfy).catch(() => {})
  }, [refreshComfy])

  const rerun = useCallback((rec: RunRecord) => {
    setActiveId(rec.feature); setRunState('idle'); setRecord(null); setError(''); setProgress(null)
    if (rec.meta?.params) setValues((s) => ({ ...s, [rec.feature]: { ...s[rec.feature], ...rec.meta.params } }))
  }, [])

  return {
    features, active, activeId, values: values[activeId] || {}, allValues: values,
    file: files[activeId] || null, preview: previews[activeId] || '',
    advancedOpen, setAdvancedOpen, historyOpen, setHistoryOpen, sysOpen, setSysOpen,
    runState, record, error, progress, elapsed, running,
    comfy, models, system, jobs, toasts, bootErr,
    selectFeature, setVal, onUpload, generate, cancel, downloadWeights, doComfy, rerun, addToast,
  }
}

export type Studio = ReturnType<typeof useStudio>
