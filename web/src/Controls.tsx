import { useEffect, useRef, useState } from 'react'
import type { Studio } from './studio'
import type { ParamSpec, RunRecord, UploadProgress } from './api'
import { choiceList, choiceLabel, getLoras, uploadLora, fmtDur } from './api'
import { Button, Switch, Slider, Segmented, Select } from './ds'
import { Icon, featureIcon } from './icons'

const eyebrow: React.CSSProperties = { font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }

// ---- Clarity live time estimate (mirrors features/clarity._estimate_runs) -------------------
// Predicts wall-clock from the settings so it updates as you drag a slider, and self-calibrates
// from your real runs: cost = (tiles × passes × steps) × tile² ≈ total pixel-steps the GPU does;
// `c` (seconds per pixel-step) is learned per machine and stored in localStorage.
const clarityPasses = (scale: number): number[] => {
  let s = scale; const out: number[] = []
  while (s > 2.0 + 1e-6) { out.push(2); s /= 2 }
  out.push(Math.round(s * 1e4) / 1e4)
  return out
}
const clarityRuns = (W: number, H: number, scale: number, tile: number, seamFix: boolean): number => {
  let runs = 0, tiles = 1, w = W, h = H
  for (const m of clarityPasses(scale)) {
    w *= m; h *= m
    tiles = Math.max(1, Math.ceil(w / tile)) * Math.max(1, Math.ceil(h / tile))
    runs += tiles
  }
  return seamFix ? runs + tiles : runs
}
const srcAfterLimit = (W: number, H: number, limit: number) => {
  const m = Math.max(W, H)
  return m > limit ? { w: (W * limit) / m, h: (H * limit) / m } : { w: W, h: H }
}
const CLARITY_C_KEY = 'relief.clarity.secPerPixelStep'
const CLARITY_C_DEFAULT = 4e-7         // ~RTX 3060 starting guess; recalibrated after the first run
const clarityOverhead = (finalUp: boolean) => 6 + (finalUp ? 8 : 0)   // model load + final UltraSharp
const clarityC = () => Number(localStorage.getItem(CLARITY_C_KEY)) || CLARITY_C_DEFAULT

function clarityEstimateSec(values: Record<string, any>, dims: { w: number; h: number } | null): number | null {
  if (!dims) return null
  const tile = Number(values.tile ?? 1024), steps = Number(values.steps ?? 18)
  const src = srcAfterLimit(dims.w, dims.h, Number(values.source_limit ?? 1536))
  const runs = clarityRuns(src.w, src.h, Number(values.scale ?? 2), tile, values.seam_fix !== false)
  const cost = runs * steps * tile * tile
  return cost * clarityC() + clarityOverhead(values.final_upscale !== false)
}

// Learn `c` from a finished Clarity run. Reconstructs the source size the run actually used from
// its OUTPUT dimensions (robust even if the loaded image changed since), so the next estimate fits.
function calibrateClarity(rec: RunRecord, fallbackDims: { w: number; h: number } | null) {
  const p = rec?.meta?.params; const actual = Number(rec?.meta?.duration_s)
  if (!p || !(actual > 3)) return
  const scale = Number(p.scale ?? 2), tile = Number(p.tile ?? 1024), steps = Number(p.steps ?? 18)
  const finalUp = p.final_upscale !== false
  let srcW: number, srcH: number
  const dm = String(rec.meta.dimensions || '').match(/(\d+)\D+(\d+)/)
  if (dm) {                                   // output = src × scale × (finalUp?4:1) → back it out
    let oW = +dm[1], oH = +dm[2]
    if (finalUp) { oW /= 4; oH /= 4 }
    srcW = oW / scale; srcH = oH / scale
  } else if (fallbackDims) {
    const s = srcAfterLimit(fallbackDims.w, fallbackDims.h, Number(p.source_limit ?? 1536))
    srcW = s.w; srcH = s.h
  } else return
  const cost = clarityRuns(srcW, srcH, scale, tile, p.seam_fix !== false) * steps * tile * tile
  if (cost <= 0) return
  const newC = Math.max(1e-8, (actual - clarityOverhead(finalUp)) / cost)
  const prev = Number(localStorage.getItem(CLARITY_C_KEY)) || CLARITY_C_DEFAULT
  localStorage.setItem(CLARITY_C_KEY, String(prev * 0.5 + newC * 0.5))   // EMA → converges in a few runs
}

// Clarity presets are a UI quick-start: picking one fills the (always-visible) sliders, and
// nudging a slider flips the Preset to 'Custom'. Mirrors features/clarity.py's documented values.
const CLARITY_PRESETS: Record<string, Record<string, any>> = {
  subtle: { creativity: 0.2, resemblance: 0.85, hdr: 5, detail_lora: 'more_details.safetensors' },
  balanced: { creativity: 0.35, resemblance: 0.6, hdr: 6, detail_lora: 'more_details.safetensors' },
  creative: { creativity: 0.55, resemblance: 0.45, hdr: 7, detail_lora: 'add_detail.safetensors' },
  max: { creativity: 0.7, resemblance: 0.35, hdr: 8, detail_lora: 'add_detail.safetensors' },
}
const CLARITY_PRESET_KEYS = ['creativity', 'resemblance', 'hdr', 'detail_lora']

function valueText(p: ParamSpec, v: any): string {
  if (p.control === 'slider' || p.control === 'stepper') {
    const n = Number(v)
    const t = Number.isInteger(n) ? String(n) : String(parseFloat(n.toFixed(2)))
    return t + (p.suffix || '')
  }
  if (p.control === 'seg' || p.control === 'select') return choiceLabel(p.choices, v)
  return ''
}

function ParamField({ p, value, onChange }: { p: ParamSpec; value: any; onChange: (v: any) => void }) {
  if (p.control === 'switch') {
    return (
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 14 }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <span style={{ font: '600 13px var(--hf-font-sans)', color: 'var(--hf-text-primary)' }}>{p.label}</span>
          {p.help && <span style={{ font: '400 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', lineHeight: 1.4 }}>{p.help}</span>}
        </div>
        <div style={{ flexShrink: 0, paddingTop: 1 }}><Switch checked={!!value} onChange={onChange} /></div>
      </div>
    )
  }
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: '600 13px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>{p.label}</span>
        {valueText(p, value) && (
          <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-primary)', background: 'var(--hf-fill-soft)', padding: '2px 8px', borderRadius: 7 }}>{valueText(p, value)}</span>
        )}
      </div>
      {p.control === 'slider' && (
        <div style={{ padding: '2px 0 0' }}>
          <Slider value={Number(value)} min={p.min ?? 0} max={p.max ?? 1} step={p.step ?? 0.01} onChange={onChange} />
        </div>
      )}
      {p.control === 'seg' && <Segmented options={choiceList(p.choices)} value={value} onChange={onChange} />}
      {p.control === 'select' && <Select options={choiceList(p.choices)} value={value} onChange={onChange} />}
      {p.control === 'stepper' && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', height: 40, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)', borderRadius: 12, padding: '0 12px' }}>
            <input type="number" value={value} onChange={(e) => onChange(Number(e.target.value))}
              style={{ flex: 1, minWidth: 0, background: 'none', border: 'none', outline: 'none', color: 'var(--hf-text-primary)', font: '400 14px var(--hf-font-mono)' }} />
          </div>
          <button title="Randomize" onClick={() => onChange(Math.floor(Math.random() * 2147483647))}
            style={{ width: 40, height: 40, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 12, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}>
            <Icon name="shuffle" size={17} sw={1.8} />
          </button>
        </div>
      )}
      {p.control === 'textarea' && (
        <textarea value={value || ''} onChange={(e) => onChange(e.target.value)} placeholder={p.placeholder} rows={4}
          style={{ width: '100%', resize: 'vertical', minHeight: 104, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)', borderRadius: 12, padding: '12px 14px', color: 'var(--hf-text-primary)', font: '400 14px var(--hf-font-sans)', lineHeight: 1.55, outline: 'none' }} />
      )}
      {p.help && (
        <span style={{ font: '400 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', lineHeight: 1.4 }}>{p.help}</span>
      )}
    </div>
  )
}

const loraLabel = (name: string) => name.replace(/\.safetensors$/i, '')
const fmtSpeed = (bps: number) =>
  bps >= 1e6 ? `${(bps / 1e6).toFixed(1)} MB/s` : bps >= 1e3 ? `${Math.round(bps / 1e3)} KB/s` : `${Math.round(bps)} B/s`

// Self-contained LoRA control: a dropdown of drop-in LoRAs, a drag-drop/click uploader
// (POST /api/loras), and a strength slider shown once a LoRA is picked. Reads/writes the
// feature's `lora` + `lora_strength` params directly, so no per-feature wiring is needed.
type LoraEntry = { name: string; strength: number }

function LoraField({ s }: { s: Studio }) {
  const [pool, setPool] = useState<string[]>([])          // available .safetensors files
  const [busy, setBusy] = useState(false)
  const [prog, setProg] = useState<UploadProgress | null>(null)
  const [drag, setDrag] = useState(false)
  const [err, setErr] = useState('')
  const stack: LoraEntry[] = Array.isArray(s.values.loras) ? s.values.loras : []

  useEffect(() => { getLoras().then(setPool) }, [])

  const setStack = (next: LoraEntry[]) => s.setVal('loras', next)
  const addRow = (name?: string) => setStack([...stack, { name: name ?? pool[0] ?? '', strength: 0.8 }])
  const updateRow = (i: number, patch: Partial<LoraEntry>) =>
    setStack(stack.map((e, idx) => (idx === i ? { ...e, ...patch } : e)))
  const removeRow = (i: number) => setStack(stack.filter((_, idx) => idx !== i))
  const opts = pool.map((l) => ({ value: l, label: loraLabel(l) }))

  const handleFile = async (file?: File | null) => {
    if (!file) return
    if (!/\.safetensors$/i.test(file.name)) { setErr('LoRA must be a .safetensors file'); return }
    setErr(''); setBusy(true); setProg({ loaded: 0, total: file.size, pct: 0, speed: 0 })
    try {
      const { saved, loras: list } = await uploadLora(file, setProg)
      setPool(list); setStack([...stack, { name: saved, strength: 0.8 }])   // auto-add to the stack
      s.addToast('success', `LoRA added · ${loraLabel(saved)}`)
    } catch (e: any) {
      setErr(e.message || 'upload failed'); s.addToast('danger', 'LoRA upload failed')
    } finally { setBusy(false); setProg(null) }
  }

  const iconBtn: React.CSSProperties = { display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
        <span style={{ font: '600 13px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>LoRAs</span>
        {stack.length > 0 && (
          <span style={{ font: '500 11px var(--hf-font-mono)', color: 'var(--hf-text-primary)', background: 'var(--hf-fill-soft)', padding: '2px 8px', borderRadius: 7 }}>{stack.length} stacked</span>
        )}
      </div>

      {/* the LoRA stack — one row per LoRA: file · strength · remove (chained on the model line) */}
      {stack.map((e, i) => (
        <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 7, padding: '10px 11px', border: '1px solid var(--hf-border)', borderRadius: 11, background: 'var(--hf-surface-2)' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <Select options={opts.length ? opts : [{ value: '', label: '— upload a LoRA below —' }]} value={e.name} onChange={(v) => updateRow(i, { name: v })} />
            </div>
            <button onClick={() => removeRow(i)} title="Remove LoRA" style={{ ...iconBtn, width: 34, height: 34, flexShrink: 0 }}>
              <Icon name="x" size={14} sw={2.2} />
            </button>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ flex: 1 }}><Slider value={e.strength} min={0} max={1.5} step={0.05} onChange={(v) => updateRow(i, { strength: v })} /></div>
            <span style={{ font: '500 11.5px var(--hf-font-mono)', color: 'var(--hf-text-primary)', minWidth: 36, textAlign: 'right' }}>{e.strength.toFixed(2)}×</span>
          </div>
        </div>
      ))}

      <button onClick={() => addRow()} disabled={!pool.length}
        style={{ height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, borderRadius: 10, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', color: pool.length ? 'var(--hf-text-secondary)' : 'var(--hf-text-tertiary)', font: '600 12.5px var(--hf-font-sans)', cursor: pool.length ? 'pointer' : 'not-allowed', opacity: pool.length ? 1 : 0.6 }}>
        <Icon name="plus" size={14} sw={2.2} /> Add LoRA
      </button>

      {/* drag-drop / click to add a .safetensors LoRA — uploads it and appends it to the stack */}
      <label
        onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files?.[0]) }}
        style={{ border: `1.5px dashed ${drag ? 'var(--hf-action)' : 'var(--hf-border-strong)'}`, background: drag ? 'var(--hf-fill-soft)' : 'var(--hf-surface-1)', borderRadius: 12, padding: '11px 14px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, cursor: busy ? 'wait' : 'pointer', color: 'var(--hf-text-tertiary)' }}>
        <Icon name={busy ? 'clock' : 'upload'} size={16} sw={1.7} />
        <span style={{ fontSize: 12.5, fontWeight: 500 }}>
          {busy
            ? (prog && prog.pct >= 99.5 ? 'Saving…' : prog ? `Uploading ${Math.round(prog.pct)}%` : 'Uploading…')
            : 'Drop a .safetensors LoRA or click to add'}
        </span>
        <input type="file" accept=".safetensors" style={{ display: 'none' }} disabled={busy}
          onChange={(e) => handleFile(e.target.files?.[0])} />
      </label>

      {/* real upload progress: bar + bytes + rolling MB/s (XHR upload.onprogress) */}
      {busy && prog && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <div style={{ position: 'relative', height: 6, borderRadius: 99, background: 'var(--hf-fill-strong)', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${prog.pct}%`, borderRadius: 99, background: 'var(--hf-accent)', transition: 'width .15s linear' }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', font: '500 10.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>
            <span>{(prog.loaded / 1e6).toFixed(1)} / {(prog.total / 1e6).toFixed(1)} MB</span>
            <span>{prog.speed > 0 && prog.pct < 99.5 ? fmtSpeed(prog.speed) : '…'}</span>
          </div>
        </div>
      )}
      {err && <span style={{ fontSize: 11.5, color: 'var(--hf-danger)' }}>{err}</span>}
      <span style={{ font: '400 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', lineHeight: 1.4 }}>
        Stack custom Krea-2 LoRAs (UNet-only), each with its own strength. Files live in ComfyUI/models/loras.
      </span>
    </div>
  )
}

export default function Controls({ s }: { s: Studio }) {
  const f = s.active
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null)
  const [guideOpen, setGuideOpen] = useState(false)
  const calibratedJob = useRef<string | null>(null)

  useEffect(() => {
    setDims(null)
    if (!s.file) return
    const url = URL.createObjectURL(s.file)
    const img = new Image()
    img.onload = () => setDims({ w: img.naturalWidth, h: img.naturalHeight })
    img.src = url
    return () => URL.revokeObjectURL(url)
  }, [s.file])

  // learn the Clarity time-estimate constant from each finished Clarity run (once per job)
  useEffect(() => {
    if (f?.id === 'clarity' && s.record?.feature === 'clarity' && s.record.job !== calibratedJob.current) {
      calibratedJob.current = s.record.job
      calibrateClarity(s.record, dims)
    }
  }, [f?.id, s.record, dims])

  if (!f) return null
  const visible = (p: ParamSpec) => !p.depends_on || s.values[p.depends_on.param] === p.depends_on.value
  const basic = f.params.filter((p) => p.group === 'basic' && visible(p))
  const advanced = f.params.filter((p) => p.group === 'advanced' && visible(p))

  // Clarity: a Preset pick fills the sliders; touching a preset-driven slider switches to Custom.
  const onParam = (p: ParamSpec, v: any) => {
    if (f.id === 'clarity' && p.name === 'preset') {
      s.setVal('preset', v)
      const preset = CLARITY_PRESETS[v]
      if (preset) Object.entries(preset).forEach(([k, val]) => s.setVal(k, val))
      return
    }
    if (f.id === 'clarity' && CLARITY_PRESET_KEYS.includes(p.name) && s.values.preset !== 'custom') {
      s.setVal('preset', 'custom')
    }
    s.setVal(p.name, v)
  }
  const liteRelief = f.id === 'relief' && s.models && !s.models.installed
  const px = Number(s.values.pixel_mm ?? 0.1) || 0.1
  const finalSize = dims ? `${Math.round(dims.w * px)} × ${Math.round(dims.h * px)} mm` : '—'

  // Clarity: a live, self-calibrating time estimate that reacts to every setting change.
  const clarityEstSec = f.id === 'clarity' ? clarityEstimateSec(s.values, dims) : null
  const estLabel = clarityEstSec ? `~${fmtDur(clarityEstSec)} est.` : f.est_runtime

  return (
    <section style={{ borderRight: '1px solid var(--hf-border)', display: 'flex', flexDirection: 'column', minHeight: 0, background: 'var(--hf-bg-base)' }}>
      {/* panel header */}
      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 11, padding: '13px 20px', borderBottom: '1px solid var(--hf-border)' }}>
        <span style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 10, background: 'var(--hf-fill-medium)', color: 'var(--hf-text-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Icon name={featureIcon(f.icon)} size={19} />
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <strong style={{ fontSize: 15, letterSpacing: '-.01em' }}>{f.name}</strong>
            {liteRelief && <span style={{ font: '700 9px var(--hf-font-sans)', letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--hf-warning)', background: 'var(--hf-warning-dim)', padding: '2px 7px', borderRadius: 99 }}>Lite</span>}
          </div>
          <span style={{ display: 'block', fontSize: 11.5, color: 'var(--hf-text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 2 }}>{f.description}</span>
        </div>
      </div>

      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '16px 22px 14px', display: 'flex', flexDirection: 'column', gap: 15 }}>
        {/* image input */}
        {f.needs_image && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={eyebrow}>{f.input_labels?.image || 'Input image'}</span>
            {s.preview ? (
              <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--hf-border)', background: 'var(--hf-surface-inset)', aspectRatio: '16/9' }}>
                <img src={s.preview} style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
                <div style={{ position: 'absolute', inset: 0, background: 'var(--hf-grad-scrim)', opacity: 0.5 }} />
                <div style={{ position: 'absolute', left: 11, bottom: 11, display: 'flex', alignItems: 'center', gap: 6, height: 24, padding: '0 9px', borderRadius: 99, background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', border: '1px solid var(--hf-glass-border)', font: '500 11px var(--hf-font-mono)', color: '#fff' }}>{s.file?.name}</div>
                <label style={{ position: 'absolute', right: 11, bottom: 11, height: 28, padding: '0 12px', display: 'flex', alignItems: 'center', borderRadius: 99, background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', border: '1px solid var(--hf-glass-border)', color: '#fff', font: '600 12px var(--hf-font-sans)', cursor: 'pointer' }}>
                  Replace<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
                </label>
              </div>
            ) : (
              <label style={{ border: '1.5px dashed var(--hf-border-strong)', background: 'var(--hf-surface-1)', borderRadius: 14, aspectRatio: '16/6.5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, cursor: 'pointer', color: 'var(--hf-text-tertiary)' }}>
                <Icon name="upload" size={22} sw={1.7} />
                <span style={{ fontSize: 13, fontWeight: 500 }}>Drop an image or click to upload</span>
                <span style={{ fontSize: 11 }}>PNG · JPG</span>
                <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
              </label>
            )}
          </div>
        )}

        {/* optional second image (e.g. Room Mockup: the CNC design placed into the room photo) */}
        {f.needs_image2 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={eyebrow}>{f.input_labels?.image2 || 'Second image'}</span>
            {s.preview2 ? (
              <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid var(--hf-border)', background: 'var(--hf-surface-inset)', aspectRatio: '16/9' }}>
                <img src={s.preview2} style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
                <div style={{ position: 'absolute', inset: 0, background: 'var(--hf-grad-scrim)', opacity: 0.5 }} />
                <div style={{ position: 'absolute', left: 11, bottom: 11, display: 'flex', alignItems: 'center', gap: 6, height: 24, padding: '0 9px', borderRadius: 99, background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', border: '1px solid var(--hf-glass-border)', font: '500 11px var(--hf-font-mono)', color: '#fff' }}>{s.file2?.name}</div>
                <label style={{ position: 'absolute', right: 11, bottom: 11, height: 28, padding: '0 12px', display: 'flex', alignItems: 'center', borderRadius: 99, background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', border: '1px solid var(--hf-glass-border)', color: '#fff', font: '600 12px var(--hf-font-sans)', cursor: 'pointer' }}>
                  Replace<input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload2(e.target.files[0])} />
                </label>
              </div>
            ) : (
              <label style={{ border: '1.5px dashed var(--hf-border-strong)', background: 'var(--hf-surface-1)', borderRadius: 14, aspectRatio: '16/6.5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, cursor: 'pointer', color: 'var(--hf-text-tertiary)' }}>
                <Icon name="upload" size={22} sw={1.7} />
                <span style={{ fontSize: 13, fontWeight: 500 }}>Drop the {(f.input_labels?.image2 || 'second image').toLowerCase()} or click to upload</span>
                <span style={{ fontSize: 11 }}>PNG · JPG</span>
                <input type="file" accept="image/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload2(e.target.files[0])} />
              </label>
            )}
          </div>
        )}

        {/* 3D-model input (Mesh → Relief) */}
        {f.needs_mesh && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={eyebrow}>3D model</span>
            {s.file ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', border: '1px solid var(--hf-border)', borderRadius: 14, background: 'var(--hf-surface-2)' }}>
                <span style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 9, background: 'var(--hf-fill-medium)', color: 'var(--hf-text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="box" size={18} /></span>
                <span style={{ flex: 1, minWidth: 0, font: '500 12px var(--hf-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.file.name}</span>
                <label style={{ flexShrink: 0, height: 30, padding: '0 12px', display: 'flex', alignItems: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', font: '600 12px var(--hf-font-sans)', cursor: 'pointer' }}>
                  Replace<input type="file" accept=".obj,.stl,.glb,.gltf,.ply,.off,.3mf" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
                </label>
              </div>
            ) : (
              <label style={{ border: '1.5px dashed var(--hf-border-strong)', background: 'var(--hf-surface-1)', borderRadius: 14, aspectRatio: '16/6.5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, cursor: 'pointer', color: 'var(--hf-text-tertiary)' }}>
                <Icon name="box" size={22} sw={1.7} />
                <span style={{ fontSize: 13, fontWeight: 500 }}>Drop a 3D model or click to upload</span>
                <span style={{ fontSize: 11 }}>OBJ · STL · GLB · PLY</span>
                <input type="file" accept=".obj,.stl,.glb,.gltf,.ply,.off,.3mf" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
              </label>
            )}
          </div>
        )}

        {/* reference-voice input (Text → Speech cloning) — optional, so it never gates Generate */}
        {f.needs_audio && s.values.mode !== 'design' && s.values.mode !== 'preset' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={eyebrow}>Reference voice</span>
            {s.file ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px', border: '1px solid var(--hf-border)', borderRadius: 14, background: 'var(--hf-surface-2)' }}>
                <span style={{ width: 34, height: 34, flexShrink: 0, borderRadius: 9, background: 'var(--hf-fill-medium)', color: 'var(--hf-text-secondary)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="mic" size={18} /></span>
                <span style={{ flex: 1, minWidth: 0, font: '500 12px var(--hf-font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.file.name}</span>
                <label style={{ flexShrink: 0, height: 30, padding: '0 12px', display: 'flex', alignItems: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', font: '600 12px var(--hf-font-sans)', cursor: 'pointer' }}>
                  Replace<input type="file" accept="audio/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
                </label>
              </div>
            ) : (
              <label style={{ border: '1.5px dashed var(--hf-border-strong)', background: 'var(--hf-surface-1)', borderRadius: 14, aspectRatio: '16/6.5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 6, cursor: 'pointer', color: 'var(--hf-text-tertiary)' }}>
                <Icon name="mic" size={22} sw={1.7} />
                <span style={{ fontSize: 13, fontWeight: 500 }}>Drop a voice sample or click to upload</span>
                <span style={{ fontSize: 11 }}>WAV · MP3 · ~10s of one speaker</span>
                <input type="file" accept="audio/*" style={{ display: 'none' }} onChange={(e) => e.target.files?.[0] && s.onUpload(e.target.files[0])} />
              </label>
            )}
          </div>
        )}

        {/* how it works & tuning tips (feature-provided guide) */}
        {f.guide && f.guide.length > 0 && (
          <div style={{ border: '1px solid var(--hf-border)', borderRadius: 12, background: 'var(--hf-surface-1)', overflow: 'hidden' }}>
            <button onClick={() => setGuideOpen(!guideOpen)}
              style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 9, padding: '11px 14px', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--hf-text-secondary)' }}>
              <Icon name="sparkle" size={15} sw={1.8} />
              <span style={{ flex: 1, textAlign: 'left', font: '600 12.5px var(--hf-font-sans)' }}>How it works &amp; tuning tips</span>
              <span style={{ transform: guideOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .18s', display: 'flex' }}><Icon name="chevronDown" size={14} sw={1.6} /></span>
            </button>
            {guideOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, padding: '2px 14px 14px' }}>
                {f.guide.map((g, i) => (
                  <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span style={{ font: '600 11px var(--hf-font-sans)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }}>{g.h}</span>
                    <span style={{ font: '400 12.5px var(--hf-font-sans)', lineHeight: 1.5, color: 'var(--hf-text-secondary)' }}>{g.b}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* basic params */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {basic.map((p) => p.control === 'lora'
            ? <LoraField key={p.name} s={s} />
            : <ParamField key={p.name} p={p} value={s.values[p.name]} onChange={(v) => onParam(p, v)} />)}
        </div>

        {/* final STL size (relief) */}
        {f.id === 'relief' && (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '10px 14px', border: '1px solid var(--hf-border)', borderRadius: 12, background: 'var(--hf-surface-1)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 7, font: '600 12px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>Final STL size</span>
              <span style={{ font: '400 11px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>pixel size × input resolution</span>
            </div>
            <span style={{ font: '500 14px var(--hf-font-mono)', color: 'var(--hf-text-primary)' }}>{finalSize}</span>
          </div>
        )}

        {/* advanced */}
        {advanced.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
            <button onClick={() => s.setAdvancedOpen(!s.advancedOpen)}
              style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'none', border: 'none', padding: '6px 0', cursor: 'pointer', color: 'var(--hf-text-secondary)', font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase' }}>
              <span style={{ flex: 1, textAlign: 'left' }}>Advanced</span>
              <span style={{ font: '400 11px var(--hf-font-mono)', letterSpacing: 0, textTransform: 'none', color: 'var(--hf-text-tertiary)' }}>{advanced.length} settings</span>
              <span style={{ transform: s.advancedOpen ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform .18s', display: 'flex' }}><Icon name="chevronDown" size={14} sw={1.6} /></span>
            </button>
            {s.advancedOpen && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {advanced.map((p) => p.control === 'lora'
                  ? <LoraField key={p.name} s={s} />
                  : <ParamField key={p.name} p={p} value={s.values[p.name]} onChange={(v) => onParam(p, v)} />)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* generate footer */}
      <div style={{ flexShrink: 0, borderTop: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)', padding: '11px 22px 13px', display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--hf-text-tertiary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }} title={clarityEstSec ? 'Estimated from your settings; calibrates to your machine after each run' : ''}><Icon name="clock" size={13} sw={2} />{estLabel}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="system" size={13} sw={2} />{f.vram}</span>
        </div>
        {s.running ? (
          <Button variant="secondary" size="lg" block onClick={s.cancel}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Icon name="x" size={15} sw={2.4} />Cancel{s.runState === 'submitting' ? ' (submitting…)' : ''}
            </span>
          </Button>
        ) : (
          <Button variant="primary" size="lg" block
            disabled={((f.needs_image || f.needs_mesh) && !s.file) || (f.needs_image2 && !s.file2)} onClick={s.generate}>Generate</Button>
        )}
        {!s.running && (((f.needs_image || f.needs_mesh) && !s.file) || (f.needs_image2 && !s.file2)) && <span style={{ fontSize: 11, color: 'var(--hf-text-tertiary)', textAlign: 'center' }}>Upload {f.needs_image2 ? 'both images' : `a ${f.needs_mesh ? '3D model' : 'image'}`} first.</span>}
      </div>
    </section>
  )
}
