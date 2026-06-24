import type { Studio } from './studio'
import { Button } from './ds'
import { Icon } from './icons'

const eyebrow: React.CSSProperties = { font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }

function kindOf(url: string): 'glb' | 'image' | 'mesh' {
  const u = url.toLowerCase()
  if (u.endsWith('.glb') || u.endsWith('.gltf')) return 'glb'
  if (/\.(png|jpg|jpeg|webp)$/.test(u)) return 'image'
  return 'mesh'
}
const ARTLABEL: Record<string, string> = { heightmap: 'Heightmap', preview3d: '3D preview', stl: 'STL mesh', image: 'Image' }

function ArtifactCard({ name, url }: { name: string; url: string }) {
  const kind = kindOf(url)
  return (
    <div style={{ border: '1px solid var(--hf-border)', borderRadius: 16, overflow: 'hidden', background: 'var(--hf-surface-1)', boxShadow: 'var(--hf-sheen-top)' }}>
      {kind === 'image' && (
        <div style={{ aspectRatio: '4/5', background: 'var(--hf-surface-inset)' }}>
          <img src={url} style={{ width: '100%', height: '100%', objectFit: 'contain', display: 'block' }} />
        </div>
      )}
      {kind === 'glb' && (
        <div style={{ aspectRatio: '4/5', background: 'radial-gradient(120% 90% at 50% 18%, #EDEFF3 0%, #D9DDE4 75%)' }}>
          {/* @ts-ignore — model-viewer web component */}
          <model-viewer src={url} camera-controls auto-rotate camera-orbit="-20deg 72deg 100%"
            exposure="1.15" shadow-intensity="1" tone-mapping="neutral" interaction-prompt="none"
            style={{ width: '100%', height: '100%' }} />
        </div>
      )}
      {kind === 'mesh' && (
        <div style={{ aspectRatio: '4/5', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 12, background: 'repeating-linear-gradient(135deg, var(--hf-surface-inset) 0 10px, var(--hf-surface-3) 10px 20px)' }}>
          <span style={{ width: 48, height: 48, borderRadius: 13, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--hf-text-secondary)' }}><Icon name="mesh" size={24} sw={1.7} /></span>
          <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>download to open</span>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '12px 14px', borderTop: '1px solid var(--hf-border-subtle)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <strong style={{ fontSize: 13 }}>{ARTLABEL[name] || name}</strong>
          <span style={{ font: '400 11px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{url.split('/').pop()}</span>
        </div>
        <a href={url} download title="Download" style={{ width: 34, height: 34, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', color: 'var(--hf-text-secondary)' }}>
          <Icon name="download" size={16} />
        </a>
      </div>
    </div>
  )
}

export default function Results({ s }: { s: Studio }) {
  const f = s.active
  const p = s.progress
  if (!f) return null

  // ---- idle ----
  if (s.runState === 'idle') {
    return (
      <div style={{ height: '100%', minHeight: 420, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 18, textAlign: 'center' }}>
        <span style={{ width: 60, height: 60, borderRadius: 18, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--hf-text-tertiary)' }}><Icon name="image" size={26} sw={1.6} /></span>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          <strong style={{ fontSize: 15, color: 'var(--hf-text-secondary)' }}>Results appear here</strong>
          <span style={{ fontSize: 13, color: 'var(--hf-text-tertiary)' }}>Adjust parameters, then generate.</span>
        </div>
        <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', justifyContent: 'center' }}>
          {f.output_kinds.map((o) => <span key={o} style={{ display: 'inline-flex', alignItems: 'center', height: 26, padding: '0 11px', borderRadius: 99, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', font: '500 11.5px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>{o}</span>)}
        </div>
      </div>
    )
  }

  // ---- running ----
  if (s.running) {
    const phases = p?.phases || []
    const idx = p?.phase_idx ?? 0
    const isComfy = p?.engine === 'comfy'
    const percent = isComfy ? Math.round((((p?.value || 0) / (p?.max || 8)) * 100)) : (p?.percent ?? 0)
    const phaseLabel = phases[idx] || p?.node || (s.runState === 'submitting' ? 'Submitting' : 'Preparing…')
    const stats = isComfy
      ? [{ k: 'Steps', v: `${p?.value || 0} / ${p?.max || 8}` }, { k: 'Node', v: p?.node || '—' }, { k: 'Elapsed', v: `${s.elapsed.toFixed(1)}s` }]
      : [{ k: 'Phase', v: phaseLabel }, { k: 'Tiles', v: String(p?.tiles_total ?? '—') }, { k: 'Elapsed', v: `${s.elapsed.toFixed(1)}s` }]
    return (
      <div style={{ maxWidth: 540, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24, paddingTop: 14, animation: 'rs-rise .3s var(--hf-ease-out)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: 'var(--hf-live)', animation: 'rs-pulse 1.6s var(--hf-ease-out) infinite' }} />
          <strong style={{ fontSize: 15 }}>{phaseLabel}</strong>
          <span style={{ marginLeft: 'auto', font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-secondary)' }}>{s.elapsed.toFixed(1)}s</span>
        </div>

        {phases.length > 0 && (
          <>
            <div style={{ display: 'flex', alignItems: 'center' }}>
              {phases.map((_, i) => {
                const done = i < idx, active = i === idx, last = i === phases.length - 1
                return (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', flex: last ? '0 0 auto' : '1 1 auto' }}>
                    <span style={{ width: 22, height: 22, flexShrink: 0, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', background: done ? 'var(--hf-accent)' : active ? 'var(--hf-white)' : 'var(--hf-surface-2)', color: done ? 'var(--hf-accent-fg)' : active ? 'var(--hf-text-inverse)' : 'var(--hf-text-tertiary)', border: `1px solid ${done || active ? 'transparent' : 'var(--hf-border)'}` }}>
                      {done ? <Icon name="check" size={11} sw={3} /> : <span style={{ width: 6, height: 6, borderRadius: 99, background: 'currentColor' }} />}
                    </span>
                    {!last && <span style={{ flex: 1, height: 2, margin: '0 4px', borderRadius: 2, background: done ? 'var(--hf-accent)' : 'var(--hf-fill-strong)' }} />}
                  </div>
                )
              })}
            </div>
            <div style={{ font: '600 13px var(--hf-font-sans)', color: 'var(--hf-text-primary)', marginTop: -12 }}>{phaseLabel}</div>
          </>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
            <span style={{ font: '700 30px var(--hf-font-sans)', letterSpacing: '-.02em' }}>{percent}%</span>
            <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{isComfy ? `${p?.value || 0}/${p?.max || 8} steps` : phaseLabel}</span>
          </div>
          <div style={{ position: 'relative', height: 8, borderRadius: 99, background: 'var(--hf-fill-strong)', overflow: 'hidden' }}>
            <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 99, width: `${percent}%`, background: 'var(--hf-white)', transition: 'width .2s linear' }} />
            <div style={{ position: 'absolute', top: 0, bottom: 0, left: 0, width: '40%', background: 'linear-gradient(90deg,transparent,rgba(255,255,255,.35),transparent)', animation: 'rs-shimmer 1.3s linear infinite' }} />
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10 }}>
          {stats.map((st) => (
            <div key={st.k} style={{ border: '1px solid var(--hf-border)', borderRadius: 12, background: 'var(--hf-surface-1)', padding: '12px 13px', display: 'flex', flexDirection: 'column', gap: 5 }}>
              <span style={{ font: '500 11px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>{st.k}</span>
              <span style={{ font: '600 16px var(--hf-font-mono)', color: 'var(--hf-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{st.v}</span>
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <span style={{ font: '400 11.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{f.id} · {p?.engine || f.engine}</span>
          <button onClick={s.cancel} style={{ height: 34, padding: '0 16px', borderRadius: 10, border: '1px solid var(--hf-border-strong)', background: 'transparent', color: 'var(--hf-text-primary)', font: '600 13px var(--hf-font-sans)', cursor: 'pointer' }}>Cancel</button>
        </div>
      </div>
    )
  }

  // ---- error ----
  if (s.runState === 'error') {
    return (
      <div style={{ maxWidth: 480, margin: '40px auto 0', border: '1px solid var(--hf-danger)', borderRadius: 16, background: 'var(--hf-danger-dim)', padding: 22, display: 'flex', flexDirection: 'column', gap: 14, textAlign: 'center', alignItems: 'center' }}>
        <span style={{ width: 46, height: 46, borderRadius: 13, background: 'rgba(214,69,63,.14)', color: 'var(--hf-danger)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Icon name="xCircle" size={24} sw={2} /></span>
        <div><strong style={{ fontSize: 15 }}>Run failed</strong><p style={{ margin: '5px 0 0', font: '400 13px var(--hf-font-mono)', color: 'var(--hf-text-secondary)', wordBreak: 'break-word' }}>{s.error}</p></div>
        <Button variant="secondary" size="md" onClick={s.generate}>Retry</Button>
      </div>
    )
  }

  // ---- result ----
  const rec = s.record
  if (!rec) return null
  const arts = Object.entries(rec.artifacts)
  const meta = rec.meta
  const metaRows = [
    { k: 'Duration', v: `${meta.duration_s.toFixed(1)} s` },
    { k: 'Dimensions', v: meta.dimensions || '—' },
    { k: 'File size', v: meta.file_size || '—' },
    { k: 'Seed', v: meta.seed != null ? String(meta.seed) : '—' },
    { k: 'Model', v: meta.model || '—' },
  ]
  const grid = f.id === 'relief' ? 'repeat(2, minmax(0,1fr))' : 'minmax(0, 520px)'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, animation: 'rs-rise .3s var(--hf-ease-out)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 24, padding: '0 10px', borderRadius: 99, background: 'var(--hf-success-dim)', color: 'var(--hf-success)', font: '600 11px var(--hf-font-sans)' }}><Icon name="check" size={12} sw={3} />Complete</span>
        <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>took {meta.duration_s.toFixed(1)} s</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={s.generate} style={{ height: 34, padding: '0 14px', borderRadius: 10, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', color: 'var(--hf-text-primary)', font: '600 13px var(--hf-font-sans)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 }}><Icon name="rerun" size={15} />Re-run</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: grid, gap: 14, alignItems: 'start' }}>
        {arts.map(([name, url]) => <ArtifactCard key={name} name={name} url={url} />)}
      </div>

      <div style={{ border: '1px solid var(--hf-border)', borderRadius: 14, background: 'var(--hf-surface-1)', padding: '15px 17px' }}>
        <div style={{ marginBottom: 13 }}><span style={eyebrow}>Run metadata</span></div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: '13px 24px' }}>
          {metaRows.map((r) => (
            <div key={r.k} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, borderBottom: '1px solid var(--hf-border-subtle)', paddingBottom: 9 }}>
              <span style={{ font: '400 12px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>{r.k}</span>
              <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-secondary)', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '60%' }}>{r.v}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
