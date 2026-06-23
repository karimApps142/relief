// Minimal Tailwind UI primitives (shadcn-ish), no external UI dep.
import React from 'react'

export function Button(
  { children, variant = 'primary', ...props }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'ghost' },
) {
  const base = 'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed'
  const styles = variant === 'primary'
    ? 'bg-indigo-500 hover:bg-indigo-400 text-white'
    : 'bg-transparent hover:bg-white/10 text-gray-200'
  return <button className={`${base} ${styles}`} {...props}>{children}</button>
}

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-xl border border-white/10 bg-white/[0.03] p-4 ${className}`}>{children}</div>
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div className="mb-1 text-xs font-medium text-gray-400">{label}</div>
      {children}
    </label>
  )
}

export function NumberSlider(
  { value, min, max, step, onChange }:
  { value: number; min: number; max: number; step: number; onChange: (v: number) => void },
) {
  return (
    <div className="flex items-center gap-3">
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded bg-white/15 accent-indigo-500" />
      <span className="w-12 shrink-0 text-right text-xs tabular-nums text-gray-300">{value}</span>
    </div>
  )
}

export function Toggle(
  { checked, onChange, label }:
  { checked: boolean; onChange: (v: boolean) => void; label: string },
) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-gray-300">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4 accent-indigo-500" />
      {label}
    </label>
  )
}

export function Select(
  { value, choices, onChange }:
  { value: string; choices: string[]; onChange: (v: string) => void },
) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100">
      {choices.map((c) => <option key={c} value={c}>{c}</option>)}
    </select>
  )
}
