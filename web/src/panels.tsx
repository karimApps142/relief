import type { Studio } from './studio'
import { Button } from './ds'
import { Icon } from './icons'
import { relativeTime } from './api'

const eyebrow: React.CSSProperties = { font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }
const card: React.CSSProperties = { border: '1px solid var(--hf-border)', borderRadius: 14, background: 'var(--hf-surface-1)', padding: '15px 16px' }
const mark = (b: boolean) => ({ mk: b ? '✓' : '○', color: b ? 'var(--hf-success)' : 'var(--hf-text-tertiary)' })
const TONE: Record<string, string> = { success: 'var(--hf-success)', info: 'var(--hf-info)', warning: 'var(--hf-warning)', danger: 'var(--hf-danger)' }

// ---------------------------------------------------------------- LITE BANNER
export function LiteBanner({ s }: { s: Studio }) {
  if (s.activeId !== 'relief' || !s.models || s.models.installed) return null
  const m = s.models
  return (
    <div style={{ margin: '0 0 16px', border: '1px solid var(--hf-border)', borderLeft: '3px solid var(--hf-warning)', borderRadius: 12, background: 'var(--hf-surface-1)', boxShadow: 'var(--hf-sheen-top)', overflow: 'hidden' }}>
      {m.busy ? (
        <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ width: 17, height: 17, flexShrink: 0, borderRadius: 99, border: '2px solid var(--hf-fill-strong)', borderTopColor: 'var(--hf-warning)', animation: 'rs-spin .8s linear infinite' }} />
            <strong style={{ fontSize: 13 }}>Downloading depth weights</strong>
          </div>
          <div style={{ font: '500 11px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{m.log?.[m.log.length - 1] || 'starting…'}</div>
        </div>
      ) : (
        <div style={{ padding: '11px 13px 11px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ width: 30, height: 30, flexShrink: 0, borderRadius: 9, background: 'var(--hf-warning-dim)', color: 'var(--hf-warning)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="warning" size={16} sw={2} /></span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <strong style={{ fontSize: 13 }}>Running in lite mode</strong>
              <span style={{ font: '700 8.5px var(--hf-font-sans)', letterSpacing: '.08em', textTransform: 'uppercase', color: 'var(--hf-warning)', background: 'var(--hf-warning-dim)', padding: '2px 6px', borderRadius: 99 }}>Crude</span>
            </div>
            <span style={{ display: 'block', fontSize: 11.5, color: 'var(--hf-text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 1 }}>Facial detail is smoothed — install depth weights for full resolution.</span>
          </div>
          <Button variant="primary" size="sm" onClick={s.downloadWeights}>Download · 2.3 GB</Button>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- COMFY WIZARD
export function ComfyWizard({ s }: { s: Studio }) {
  const c = s.comfy
  const f = s.active
  if (!c || !f) return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--hf-text-tertiary)', fontSize: 13 }}>Checking the image engine…</div>
  )
  // feature-aware requirements: relight needs the IC-Light node + its own models
  const isRelight = f.id === 'relight'
  const models = isRelight ? Object.entries(c.relight_models || {}) : Object.entries(c.models)
  const allM = models.length > 0 && models.every(([, b]) => b)
  const nodeOk = !!(c.nodes || {})[isRelight ? 'iclight' : 'gguf']
  const installedOk = c.installed && nodeOk
  const addNode = c.installed && !nodeOk         // engine there, just missing this tool's node
  const steps = [
    { key: 'install', label: isRelight ? 'Install ComfyUI + IC-Light' : 'Install ComfyUI',
      desc: addNode ? 'Add the IC-Light node and reload the engine.' : 'Clone the engine and Python dependencies.',
      done: installedOk, available: !installedOk, btn: addNode ? 'Add node' : 'Install', showModels: false },
    { key: 'download', label: 'Download models',
      desc: isRelight ? 'Fetch the relight models (~3.7 GB).' : 'Fetch the 4 model files (~11.7 GB total).',
      done: allM, available: c.installed && !allM, btn: 'Download', showModels: true },
    c.running
      ? { key: 'restart', label: 'Reload engine', desc: 'Restart ComfyUI to load newly-added tools.',
          done: installedOk && allM, available: true, btn: 'Reload', showModels: false }
      : { key: 'start', label: 'Start engine', desc: 'Launch ComfyUI on 127.0.0.1:8188.',
          done: false, available: installedOk && allM, btn: 'Start', showModels: false },
  ]
  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '34px 26px' }}>
      <div style={{ width: '100%', maxWidth: 620, border: '1px solid var(--hf-border)', borderRadius: 20, background: 'var(--hf-surface-1)', padding: 28, boxShadow: 'var(--hf-shadow-md), var(--hf-sheen-top)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 6 }}>
          <span style={{ width: 40, height: 40, borderRadius: 12, background: 'var(--hf-fill-medium)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="sparkle" size={20} /></span>
          <div>
            <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, letterSpacing: '-.01em' }}>Set up the image engine</h2>
            <p style={{ margin: '2px 0 0', fontSize: 13, color: 'var(--hf-text-secondary)' }}>{f.name} runs on ComfyUI. Complete the steps to unlock it.</p>
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 20 }}>
          {steps.map((st, i) => {
            const status = st.done ? 'done' : st.available ? 'available' : 'pending'
            const busy = !!c?.busy && c.action === st.key
            return (
              <div key={st.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '14px 15px', border: `1px solid ${st.available ? 'var(--hf-border-strong)' : 'var(--hf-border)'}`, borderRadius: 14, background: st.available ? 'var(--hf-surface-2)' : 'var(--hf-surface-1)' }}>
                <span style={{ width: 28, height: 28, flexShrink: 0, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', font: '700 13px var(--hf-font-sans)', background: st.done ? 'var(--hf-success-dim)' : st.available ? 'var(--hf-white)' : 'var(--hf-fill-medium)', color: st.done ? 'var(--hf-success)' : st.available ? 'var(--hf-text-inverse)' : 'var(--hf-text-tertiary)' }}>{st.done ? '✓' : String(i + 1)}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <strong style={{ fontSize: 14, color: status === 'pending' ? 'var(--hf-text-tertiary)' : 'var(--hf-text-primary)' }}>{st.label}</strong>
                    <span style={{ fontSize: 11, fontWeight: 600, color: st.done ? 'var(--hf-success)' : st.available ? 'var(--hf-text-secondary)' : 'var(--hf-text-tertiary)' }}>{st.done ? 'Done' : st.available ? 'Ready' : 'Waiting'}</span>
                  </div>
                  <p style={{ margin: '3px 0 0', fontSize: 12, color: 'var(--hf-text-tertiary)', lineHeight: 1.45 }}>{st.desc}</p>
                  {st.showModels && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 10 }}>
                      {models.map(([label, b]) => { const mk = mark(b); return (
                        <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 8, font: '400 11.5px var(--hf-font-mono)', color: 'var(--hf-text-secondary)' }}><span style={{ color: mk.color }}>{mk.mk}</span><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span></div>
                      ) })}
                    </div>
                  )}
                </div>
                {(st.available || busy) && (
                  <div style={{ flexShrink: 0 }}>
                    <Button variant="primary" size="sm" loading={busy} disabled={!!c?.busy} onClick={() => s.doComfy(st.key as any)}>{st.btn}</Button>
                  </div>
                )}
              </div>
            )
          })}
        </div>
        {!!c?.log.length && (
          <pre style={{ marginTop: 16, background: 'var(--hf-surface-inset)', border: '1px solid var(--hf-border-subtle)', borderRadius: 12, padding: '12px 14px', maxHeight: 160, overflow: 'auto', font: '400 11.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)', lineHeight: 1.75, whiteSpace: 'pre-wrap' }}>{c.log.slice(-60).join('\n')}</pre>
        )}
        {c?.error && <div style={{ marginTop: 12, font: '400 12px var(--hf-font-mono)', color: 'var(--hf-danger)' }}>{c.error}</div>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- HISTORY
export function HistoryPanel({ s }: { s: Studio }) {
  if (!s.historyOpen) return null
  return (
    <aside style={{ width: 256, flexShrink: 0, display: 'flex', flexDirection: 'column', minHeight: 0, borderLeft: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)', animation: 'rs-rise .22s var(--hf-ease-out)' }}>
      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', gap: 8, padding: '0 14px 0 18px', height: 62, borderBottom: '1px solid var(--hf-border)' }}>
        <span style={eyebrow}>Recent</span>
        <span style={{ font: '400 11px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{s.jobs.length}</span>
        <button onClick={() => s.setHistoryOpen(false)} title="Hide" style={{ marginLeft: 'auto', width: 30, height: 30, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: 'none', background: 'var(--hf-fill-soft)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}><Icon name="chevronRight" size={16} sw={2} /></button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {s.jobs.length === 0 && <div style={{ padding: '20px 6px', fontSize: 12, color: 'var(--hf-text-tertiary)', textAlign: 'center' }}>No generations yet.</div>}
        {s.jobs.map((h) => (
          <button key={h.job} onClick={() => s.rerun(h)} title="Re-run with these settings"
            style={{ display: 'flex', alignItems: 'center', gap: 11, width: '100%', textAlign: 'left', padding: 8, borderRadius: 12, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', cursor: 'pointer' }}>
            <div style={{ position: 'relative', width: 60, height: 48, flexShrink: 0, borderRadius: 9, overflow: 'hidden', border: '1px solid var(--hf-border)', background: 'var(--hf-surface-inset)' }}>
              {h.thumb && <img src={h.thumb} style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />}
              <span style={{ position: 'absolute', left: 5, bottom: 4, font: '600 9px var(--hf-font-mono)', color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,.6)' }}>{h.duration_s.toFixed(1)}s</span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ font: '600 12.5px var(--hf-font-sans)', color: 'var(--hf-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{h.name}</div>
              <div style={{ font: '400 11px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', marginTop: 1 }}>{relativeTime(h.created_at)}</div>
            </div>
            <span style={{ flexShrink: 0, color: 'var(--hf-text-tertiary)' }}><Icon name="rerun" size={15} /></span>
          </button>
        ))}
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- SYSTEM PANEL
export function SystemPanel({ s }: { s: Studio }) {
  if (!s.sysOpen) return null
  const sys = s.system
  const vramColor = !sys ? 'var(--hf-text-tertiary)' : sys.vram_percent >= 90 ? 'var(--hf-danger)' : sys.vram_percent >= 75 ? 'var(--hf-warning)' : 'var(--hf-accent)'
  const resident = sys?.resident || 'idle'
  const gpu = sys ? [
    { k: 'Utilization', v: `${sys.util}%` }, { k: 'Temp', v: `${sys.temp}°C` }, { k: 'Power', v: `${sys.power} W` },
    { k: 'Loaded', v: sys.model_loaded }, { k: 'Disk free', v: sys.disk_free != null ? `${sys.disk_free} GB` : '—' },
    { k: 'Resident', v: ({ relief: 'Relief', image: 'Image', idle: 'Idle' } as any)[resident] },
  ] : []
  const weights = s.models?.models ? Object.entries(s.models.models) : []
  const cmodels = s.comfy ? Object.entries(s.comfy.models) : []
  return (
    <>
      <div onClick={() => s.setSysOpen(false)} style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'var(--hf-scrim)', backdropFilter: 'blur(2px)', animation: 'rs-rise .2s var(--hf-ease-out)' }} />
      <div style={{ position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 310, width: 420, maxWidth: '92vw', background: 'var(--hf-bg-base)', borderLeft: '1px solid var(--hf-border)', boxShadow: 'var(--hf-shadow-xl)', display: 'flex', flexDirection: 'column', animation: 'rs-rise .24s var(--hf-ease-out)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 22px', borderBottom: '1px solid var(--hf-border)' }}>
          <div><h2 style={{ margin: 0, fontSize: 16, fontWeight: 700 }}>System &amp; health</h2><span style={{ fontSize: 12, color: 'var(--hf-text-tertiary)' }}>{sys?.device || '—'}</span></div>
          <button onClick={() => s.setSysOpen(false)} style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, border: 'none', background: 'var(--hf-fill-soft)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}><Icon name="x" size={18} sw={2} /></button>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div style={{ ...card, padding: 17, boxShadow: 'var(--hf-sheen-top)' }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ font: '600 13px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>VRAM</span>
              <span style={{ font: '700 18px var(--hf-font-mono)', color: vramColor }}>{sys ? `${sys.vram_used} / ${sys.vram_total} GB` : '—'}</span>
            </div>
            <div style={{ height: 10, borderRadius: 99, background: 'var(--hf-fill-strong)', overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRadius: 99, width: `${sys?.vram_percent || 0}%`, background: vramColor, transition: 'width .25s var(--hf-ease-out)' }} />
            </div>
            <p style={{ margin: '11px 0 0', font: '400 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', lineHeight: 1.5 }}>Relief and the image engine can't be resident at once — relief models unload before an image run.</p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            <span style={eyebrow}>Resident engine</span>
            <div style={{ display: 'flex', gap: 7 }}>
              {[{ id: 'relief', label: 'Relief' }, { id: 'image', label: 'Image' }, { id: 'idle', label: 'Idle' }].map((e) => { const on = resident === e.id; return (
                <div key={e.id} style={{ flex: 1, textAlign: 'center', padding: '11px 6px', borderRadius: 11, border: `1px solid ${on ? 'var(--hf-border-strong)' : 'var(--hf-border)'}`, background: on ? 'var(--hf-fill-medium)' : 'transparent', color: on ? 'var(--hf-text-primary)' : 'var(--hf-text-tertiary)', font: '600 12.5px var(--hf-font-sans)' }}>{e.label}</div>
              ) })}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
            <span style={eyebrow}>GPU telemetry {sys && !sys.available && <span style={{ textTransform: 'none', letterSpacing: 0, fontSize: 10, color: 'var(--hf-text-tertiary)' }}>· unavailable off-box</span>}</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 9 }}>
              {gpu.map((g) => (
                <div key={g.k} style={{ border: '1px solid var(--hf-border)', borderRadius: 12, background: 'var(--hf-surface-1)', padding: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <span style={{ font: '500 10.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>{g.k}</span>
                  <span style={{ font: '700 16px var(--hf-font-mono)', color: 'var(--hf-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{g.v}</span>
                </div>
              ))}
            </div>
          </div>

          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 11 }}>
              <span style={{ font: '600 13px var(--hf-font-sans)' }}>Relief depth weights</span>
              <span style={{ font: '600 11px var(--hf-font-sans)', color: s.models?.installed ? 'var(--hf-success)' : 'var(--hf-warning)' }}>{s.models?.installed ? 'Installed' : 'Lite mode'}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {weights.map(([label, b]) => { const mk = mark(b); return <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 9, font: '400 12.5px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}><span style={{ color: mk.color }}>{mk.mk}</span>{label}</div> })}
            </div>
          </div>

          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 11 }}>
              <span style={{ font: '600 13px var(--hf-font-sans)' }}>Image engine</span>
              <span style={{ font: '600 11px var(--hf-font-sans)', color: s.comfy?.running ? 'var(--hf-success)' : 'var(--hf-warning)' }}>{s.comfy?.running ? 'Running' : s.comfy?.installed ? 'Stopped' : 'Not installed'}</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {cmodels.map(([label, b]) => { const mk = mark(b); return <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 9, font: '400 12px var(--hf-font-mono)', color: 'var(--hf-text-secondary)' }}><span style={{ color: mk.color }}>{mk.mk}</span><span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span></div> })}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

// ---------------------------------------------------------------- TOASTS
export function Toasts({ s }: { s: Studio }) {
  return (
    <div style={{ position: 'fixed', right: 22, bottom: 22, zIndex: 400, display: 'flex', flexDirection: 'column', gap: 10, alignItems: 'flex-end' }}>
      {s.toasts.map((t) => (
        <div key={t.id} style={{ minWidth: 240, maxWidth: 340, display: 'flex', alignItems: 'center', gap: 11, padding: '13px 15px', borderRadius: 13, border: '1px solid var(--hf-border-strong)', borderLeft: `3px solid ${TONE[t.tone] || 'var(--hf-white)'}`, background: 'var(--hf-surface-2)', boxShadow: 'var(--hf-shadow-lg)', animation: 'rs-rise .26s var(--hf-ease-out)' }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: TONE[t.tone] || 'var(--hf-white)', flexShrink: 0 }} />
          <span style={{ font: '500 13px var(--hf-font-sans)', color: 'var(--hf-text-primary)', lineHeight: 1.4 }}>{t.msg}</span>
        </div>
      ))}
    </div>
  )
}
