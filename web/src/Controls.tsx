import { useEffect, useState } from 'react'
import type { Studio } from './studio'
import type { ParamSpec } from './api'
import { choiceList, choiceLabel } from './api'
import { Button, Switch, Slider, Segmented, Select } from './ds'
import { Icon, featureIcon } from './icons'

const eyebrow: React.CSSProperties = { font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }

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

export default function Controls({ s }: { s: Studio }) {
  const f = s.active
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null)

  useEffect(() => {
    setDims(null)
    if (!s.file) return
    const url = URL.createObjectURL(s.file)
    const img = new Image()
    img.onload = () => setDims({ w: img.naturalWidth, h: img.naturalHeight })
    img.src = url
    return () => URL.revokeObjectURL(url)
  }, [s.file])

  if (!f) return null
  const visible = (p: ParamSpec) => !p.depends_on || s.values[p.depends_on.param] === p.depends_on.value
  const basic = f.params.filter((p) => p.group === 'basic' && visible(p))
  const advanced = f.params.filter((p) => p.group === 'advanced' && visible(p))
  const liteRelief = f.id === 'relief' && s.models && !s.models.installed
  const px = Number(s.values.pixel_mm ?? 0.1) || 0.1
  const finalSize = dims ? `${Math.round(dims.w * px)} × ${Math.round(dims.h * px)} mm` : '—'

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
            <span style={eyebrow}>Input image</span>
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

        {/* basic params */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {basic.map((p) => <ParamField key={p.name} p={p} value={s.values[p.name]} onChange={(v) => s.setVal(p.name, v)} />)}
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
                {advanced.map((p) => <ParamField key={p.name} p={p} value={s.values[p.name]} onChange={(v) => s.setVal(p.name, v)} />)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* generate footer */}
      <div style={{ flexShrink: 0, borderTop: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)', padding: '11px 22px 13px', display: 'flex', flexDirection: 'column', gap: 9 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11.5, color: 'var(--hf-text-tertiary)' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="clock" size={13} sw={2} />{f.est_runtime}</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}><Icon name="system" size={13} sw={2} />{f.vram}</span>
        </div>
        <Button variant="primary" size="lg" block loading={s.running}
          disabled={s.running || (f.needs_image && !s.file)} onClick={s.generate}>
          {s.runState === 'submitting' ? 'Submitting…' : s.runState === 'running' ? 'Generating…' : 'Generate'}
        </Button>
        {f.needs_image && !s.file && <span style={{ fontSize: 11, color: 'var(--hf-text-tertiary)', textAlign: 'center' }}>Upload an image first.</span>}
      </div>
    </section>
  )
}
