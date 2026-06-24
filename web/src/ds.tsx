// Light-theme reimplementation of the Higgsfield DS controls used by the design.
import { useRef, useState, type CSSProperties } from 'react'
import type { Choice } from './api'

const SIZES = { sm: { h: 32, px: 14, fs: 13 }, md: { h: 40, px: 16, fs: 13.5 }, lg: { h: 48, px: 20, fs: 14.5 } }

export function Button({
  children, onClick, variant = 'primary', size = 'md', block = false, loading = false, disabled = false,
}: {
  children: React.ReactNode; onClick?: () => void
  variant?: 'primary' | 'secondary' | 'ghost'; size?: 'sm' | 'md' | 'lg'
  block?: boolean; loading?: boolean; disabled?: boolean
}) {
  const [hover, setHover] = useState(false)
  const s = SIZES[size]
  const off = disabled || loading
  const base: CSSProperties = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
    height: s.h, padding: `0 ${s.px}px`, width: block ? '100%' : undefined,
    borderRadius: 12, font: `600 ${s.fs}px var(--hf-font-sans)`, cursor: off ? 'not-allowed' : 'pointer',
    opacity: off ? 0.55 : 1, transition: 'background .14s, border-color .14s, transform .08s', border: '1px solid transparent',
  }
  const variants: Record<string, CSSProperties> = {
    primary: { background: hover && !off ? 'var(--hf-action-hover)' : 'var(--hf-action)', color: '#fff' },
    secondary: { background: 'var(--hf-surface-2)', color: 'var(--hf-text-primary)', borderColor: hover && !off ? 'var(--hf-border-strong)' : 'var(--hf-border)' },
    ghost: { background: hover && !off ? 'var(--hf-fill-soft)' : 'transparent', color: 'var(--hf-text-secondary)' },
  }
  return (
    <button onClick={off ? undefined : onClick} disabled={off}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{ ...base, ...variants[variant] }}>
      {loading && <span style={{ width: 14, height: 14, borderRadius: 99, border: '2px solid rgba(255,255,255,.4)', borderTopColor: '#fff', animation: 'rs-spin .8s linear infinite' }} />}
      {children}
    </button>
  )
}

export function Switch({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!checked)} aria-pressed={checked}
      style={{ width: 40, height: 24, flexShrink: 0, borderRadius: 99, border: 'none', cursor: 'pointer', padding: 2,
        background: checked ? 'var(--hf-action)' : 'var(--hf-fill-strong)', transition: 'background .18s var(--hf-ease-out)', display: 'flex' }}>
      <span style={{ width: 20, height: 20, borderRadius: 99, background: '#fff', boxShadow: '0 1px 2px rgba(15,20,28,.3)',
        transform: checked ? 'translateX(16px)' : 'translateX(0)', transition: 'transform .18s var(--hf-ease-out)' }} />
    </button>
  )
}

export function Slider({ value, min, max, step, onChange }: {
  value: number; min: number; max: number; step: number; onChange: (v: number) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const pct = Math.max(0, Math.min(100, ((value - min) / (max - min || 1)) * 100))
  const setFromX = (clientX: number) => {
    const el = ref.current; if (!el) return
    const r = el.getBoundingClientRect()
    const t = Math.max(0, Math.min(1, (clientX - r.left) / r.width))
    const raw = min + t * (max - min)
    const snapped = Math.round(raw / step) * step
    const fixed = Number(snapped.toFixed(6))
    onChange(Math.max(min, Math.min(max, fixed)))
  }
  const onDown = (e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture?.(e.pointerId); setFromX(e.clientX)
    const move = (ev: PointerEvent) => setFromX(ev.clientX)
    const up = () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', up) }
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', up)
  }
  return (
    <div ref={ref} onPointerDown={onDown}
      style={{ position: 'relative', height: 18, display: 'flex', alignItems: 'center', cursor: 'pointer', touchAction: 'none' }}>
      <div style={{ position: 'absolute', left: 0, right: 0, height: 5, borderRadius: 99, background: 'var(--hf-fill-strong)' }} />
      <div style={{ position: 'absolute', left: 0, width: `${pct}%`, height: 5, borderRadius: 99, background: 'var(--hf-action)' }} />
      <div style={{ position: 'absolute', left: `${pct}%`, transform: 'translateX(-50%)', width: 16, height: 16, borderRadius: 99, background: '#fff', border: '1px solid var(--hf-border-strong)', boxShadow: 'var(--hf-shadow-xs)' }} />
    </div>
  )
}

export function Segmented({ options, value, onChange }: { options: Choice[]; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ display: 'flex', gap: 3, padding: 3, borderRadius: 11, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)' }}>
      {options.map((o) => {
        const on = o.value === value
        return (
          <button key={o.value} onClick={() => onChange(o.value)}
            style={{ flex: 1, height: 30, borderRadius: 8, border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', padding: '0 8px',
              font: `600 12px var(--hf-font-sans)`, transition: 'background .14s, color .14s',
              background: on ? 'var(--hf-white)' : 'transparent', color: on ? 'var(--hf-text-inverse)' : 'var(--hf-text-secondary)' }}>
            {o.label}
          </button>
        )
      })}
    </div>
  )
}

export function Select({ options, value, onChange }: { options: Choice[]; value: string; onChange: (v: string) => void }) {
  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        style={{ width: '100%', height: 40, appearance: 'none', WebkitAppearance: 'none', borderRadius: 12,
          border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', color: 'var(--hf-text-primary)',
          font: '500 13.5px var(--hf-font-sans)', padding: '0 36px 0 13px', cursor: 'pointer', outline: 'none' }}>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <span style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--hf-text-tertiary)', display: 'flex' }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="m6 9 6 6 6-6" /></svg>
      </span>
    </div>
  )
}
