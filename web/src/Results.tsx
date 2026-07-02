import { useEffect, useRef, useState } from 'react'
import type { Studio } from './studio'
import { Button } from './ds'
import { Icon } from './icons'
import { fmtDur } from './api'

const eyebrow: React.CSSProperties = { font: '600 11px var(--hf-font-sans)', letterSpacing: '.12em', textTransform: 'uppercase', color: 'var(--hf-text-tertiary)' }

function kindOf(url: string): 'glb' | 'image' | 'audio' | 'mesh' {
  const u = url.toLowerCase()
  if (u.endsWith('.glb') || u.endsWith('.gltf')) return 'glb'
  if (/\.(png|jpg|jpeg|webp)$/.test(u)) return 'image'
  if (/\.(wav|mp3|flac|ogg|m4a)$/.test(u)) return 'audio'
  return 'mesh'
}
const ARTLABEL: Record<string, string> = { heightmap: 'Heightmap', preview3d: '3D preview', stl: 'STL mesh', image: 'Image', depth_16bit: 'Depth (16-bit)', depth_preview: 'Depth preview', normal: 'Normal map', relief_heat: 'Heat map', depth_heat: 'Heat map', heat3d: '3D heat map', audio: 'Speech' }

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
        // Soft studio backdrop + matte plaster lighting, so the relief reads as a lit cast
        // (like a lithophane preview) instead of a flat, blown-out white blob.
        <div style={{ aspectRatio: '4/5', background: 'linear-gradient(165deg, #eef4fb 0%, #c6d6e8 58%, #a9bdd6 100%)' }}>
          {/* @ts-ignore — model-viewer web component */}
          <model-viewer src={url} camera-controls auto-rotate auto-rotate-delay="0"
            rotation-per-second="16deg" camera-orbit="-16deg 78deg 108%" field-of-view="27deg"
            exposure="0.95" shadow-intensity="1.0" shadow-softness="0.85"
            tone-mapping="neutral" interaction-prompt="none"
            style={{ width: '100%', height: '100%', backgroundColor: 'transparent' }} />
        </div>
      )}
      {kind === 'audio' && (
        <div style={{ padding: '26px 18px 22px', background: 'var(--hf-surface-inset)', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16 }}>
          <span style={{ width: 52, height: 52, borderRadius: 14, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--hf-text-secondary)' }}><Icon name="waveform" size={26} sw={1.7} /></span>
          <audio src={url} controls style={{ width: '100%' }} />
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

// shared drag-to-wipe state: the divider position + pointer handlers, reused by the inline
// card and the full-screen overlay so they behave identically at any size.
function useWipe() {
  const [pos, setPos] = useState(50)
  const ref = useRef<HTMLDivElement>(null)
  const dragging = useRef(false)
  const moveTo = (clientX: number) => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    setPos(Math.max(0, Math.min(100, ((clientX - r.left) / r.width) * 100)))
  }
  const handlers = {
    onPointerDown: (e: React.PointerEvent) => { dragging.current = true; e.currentTarget.setPointerCapture(e.pointerId); moveTo(e.clientX) },
    onPointerMove: (e: React.PointerEvent) => { if (dragging.current) moveTo(e.clientX) },
    onPointerUp: (e: React.PointerEvent) => { dragging.current = false; e.currentTarget.releasePointerCapture?.(e.pointerId) },
    onPointerCancel: () => { dragging.current = false },
  }
  return { pos, ref, handlers }
}

const wipeBadge: React.CSSProperties = { position: 'absolute', top: 10, padding: '3px 9px', borderRadius: 99, font: '600 10.5px var(--hf-font-sans)', letterSpacing: '.06em', textTransform: 'uppercase', background: 'rgba(0,0,0,.55)', color: '#fff', backdropFilter: 'blur(4px)', pointerEvents: 'none' }

// Before/After labels + the divider line and round drag handle, positioned at `pos` percent.
function WipeChrome({ pos }: { pos: number }) {
  return (
    <>
      <span style={{ ...wipeBadge, left: 10 }}>Before</span>
      <span style={{ ...wipeBadge, right: 10 }}>After</span>
      <div style={{ position: 'absolute', top: 0, bottom: 0, left: `${pos}%`, width: 2, marginLeft: -1, background: '#fff', boxShadow: '0 0 6px rgba(0,0,0,.45)', pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', top: '50%', left: '50%', transform: 'translate(-50%,-50%)', width: 34, height: 34, borderRadius: 99, background: '#fff', boxShadow: '0 1px 6px rgba(0,0,0,.4)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#333' }}>
          <Icon name="chevronLeft" size={12} sw={2.6} /><Icon name="chevronRight" size={12} sw={2.6} />
        </div>
      </div>
    </>
  )
}

const imgFill: React.CSSProperties = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'contain', display: 'block' }

// Inline before/after card: the uploaded input (before) under the generated image (after),
// revealed left→right by a draggable divider. A Full-screen button opens the large overlay.
function BeforeAfter({ before, after, onExpand }: { before: string; after: string; onExpand: () => void }) {
  const { pos, ref, handlers } = useWipe()
  return (
    <div style={{ border: '1px solid var(--hf-border)', borderRadius: 16, overflow: 'hidden', background: 'var(--hf-surface-1)', boxShadow: 'var(--hf-sheen-top)' }}>
      <div ref={ref} {...handlers}
        style={{ position: 'relative', aspectRatio: '4/5', background: 'var(--hf-surface-inset)', cursor: 'ew-resize', touchAction: 'none', userSelect: 'none' }}>
        <img src={after} draggable={false} style={imgFill} />
        <img src={before} draggable={false} style={{ ...imgFill, clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
        <WipeChrome pos={pos} />
        <button onClick={onExpand} title="Compare full screen"
          style={{ position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)', height: 28, padding: '0 11px', display: 'flex', alignItems: 'center', gap: 6, borderRadius: 99, background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', border: '1px solid var(--hf-glass-border)', color: '#fff', font: '600 11px var(--hf-font-sans)', cursor: 'pointer' }}>
          <Icon name="expand" size={13} sw={2} />Full screen
        </button>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '12px 14px', borderTop: '1px solid var(--hf-border-subtle)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <strong style={{ fontSize: 13 }}>Before / After</strong>
          <span style={{ font: '400 11px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>drag to compare · {after.split('/').pop()}</span>
        </div>
        <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <button onClick={onExpand} title="Compare full screen"
            style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}>
            <Icon name="expand" size={15} />
          </button>
          <a href={after} download title="Download" style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', color: 'var(--hf-text-secondary)' }}>
            <Icon name="download" size={16} />
          </a>
        </div>
      </div>
    </div>
  )
}

// Full-screen overlay: the same wipe at the image's natural size. Esc or the Close button exits.
function FullscreenCompare({ before, after, onClose }: { before: string; after: string; onClose: () => void }) {
  const { pos, ref, handlers } = useWipe()
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])
  const btn: React.CSSProperties = { height: 34, padding: '0 13px', display: 'flex', alignItems: 'center', gap: 7, borderRadius: 10, border: '1px solid var(--hf-glass-border)', background: 'var(--hf-glass-bg)', backdropFilter: 'blur(18px)', color: '#fff', font: '600 13px var(--hf-font-sans)', cursor: 'pointer', textDecoration: 'none' }
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 400, background: 'rgba(8,10,14,.94)', backdropFilter: 'blur(8px)', display: 'flex', flexDirection: 'column', animation: 'rs-rise .2s var(--hf-ease-out)' }}>
      <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '14px 18px' }}>
        <span style={{ color: '#fff', font: '700 14px var(--hf-font-sans)', letterSpacing: '-.01em' }}>Before / After — drag to compare</span>
        <div style={{ display: 'flex', gap: 9 }}>
          <a href={after} download style={btn}><Icon name="download" size={15} />Download</a>
          <button onClick={onClose} style={btn}><Icon name="x" size={15} sw={2.4} />Close <span style={{ opacity: .6, fontSize: 11, marginLeft: 1 }}>Esc</span></button>
        </div>
      </div>
      <div style={{ flex: 1, minHeight: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '0 18px 18px' }}>
        <div ref={ref} {...handlers}
          style={{ position: 'relative', display: 'inline-block', lineHeight: 0, cursor: 'ew-resize', touchAction: 'none', userSelect: 'none' }}>
          <img src={after} draggable={false} style={{ display: 'block', maxWidth: '92vw', maxHeight: 'calc(100vh - 120px)', objectFit: 'contain' }} />
          <img src={before} draggable={false} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', clipPath: `inset(0 ${100 - pos}% 0 0)` }} />
          <WipeChrome pos={pos} />
        </div>
      </div>
    </div>
  )
}

export default function Results({ s }: { s: Studio }) {
  const f = s.active
  const p = s.progress
  const [zoom, setZoom] = useState(false)
  useEffect(() => { setZoom(false) }, [s.record])   // a new result closes any open full-screen compare
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
    // Prefer the backend's cumulative percent (smooth single fill across all tiles/passes);
    // fall back to the current run's value/max only if an older backend omits it.
    const percent = p?.percent ?? (isComfy ? Math.round((((p?.value || 0) / (p?.max || 8)) * 100)) : 0)
    // ETA from real progress: time_left ≈ elapsed × (100−pct)/pct. Hold off until there's a
    // little signal (pct>3, >4 s) so the first estimate isn't wild.
    const eta = percent > 3 && percent < 100 && s.elapsed > 4
      ? Math.round((s.elapsed * (100 - percent)) / percent) : 0
    const phaseLabel = phases[idx] || p?.node || (s.runState === 'submitting' ? 'Submitting' : 'Preparing…')
    const tilesStat = (p?.tiles_total ?? 0) > 0 ? `${p?.tiles_done ?? 0} / ${p?.tiles_total}` : '—'
    const stats = isComfy
      ? [{ k: 'Time left', v: eta ? `~${fmtDur(eta)}` : 'estimating…' }, { k: 'Node', v: p?.node || '—' }, { k: 'Elapsed', v: fmtDur(s.elapsed) }]
      : [{ k: 'Phase', v: phaseLabel }, { k: 'Tiles', v: tilesStat }, { k: 'Elapsed', v: fmtDur(s.elapsed) }]
    return (
      <div style={{ maxWidth: 540, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24, paddingTop: 14, animation: 'rs-rise .3s var(--hf-ease-out)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: 99, background: 'var(--hf-live)', animation: 'rs-pulse 1.6s var(--hf-ease-out) infinite' }} />
          <strong style={{ fontSize: 15 }}>{phaseLabel}</strong>
          <span style={{ marginLeft: 'auto', font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-secondary)' }}>{fmtDur(s.elapsed)}{eta ? <span style={{ color: 'var(--hf-text-tertiary)' }}>{`  ·  ~${fmtDur(eta)} left`}</span> : ''}</span>
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
            <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{eta ? `~${fmtDur(eta)} left` : (isComfy ? 'working…' : phaseLabel)}</span>
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
          <button onClick={s.cancel} style={{ height: 34, padding: '0 14px', borderRadius: 10, border: '1px solid var(--hf-danger)', background: 'var(--hf-danger-dim)', color: 'var(--hf-danger)', font: '600 13px var(--hf-font-sans)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 }}><Icon name="x" size={14} sw={2.4} />Cancel</button>
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
    { k: 'Duration', v: fmtDur(meta.duration_s) },
    { k: 'Dimensions', v: meta.dimensions || '—' },
    { k: 'File size', v: meta.file_size || '—' },
    { k: 'Seed', v: meta.seed != null ? String(meta.seed) : '—' },
    { k: 'Model', v: meta.model || '—' },
  ]
  const grid = (f.id === 'relief' || f.id === 'depthmap') ? 'repeat(2, minmax(0,1fr))' : 'minmax(0, 520px)'
  // Upscalers compare against the source: swap the plain image card for a before/after wipe
  // when we still hold the uploaded input (a fresh run; not a re-opened history item).
  const compareArt = (f.id === 'upscale' || f.id === 'clarity') && s.preview
    ? arts.find(([, url]) => kindOf(url) === 'image') : null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18, animation: 'rs-rise .3s var(--hf-ease-out)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 24, padding: '0 10px', borderRadius: 99, background: 'var(--hf-success-dim)', color: 'var(--hf-success)', font: '600 11px var(--hf-font-sans)' }}><Icon name="check" size={12} sw={3} />Complete</span>
        <span style={{ font: '500 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>took {fmtDur(meta.duration_s)}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button onClick={s.generate} style={{ height: 34, padding: '0 14px', borderRadius: 10, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', color: 'var(--hf-text-primary)', font: '600 13px var(--hf-font-sans)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 7 }}><Icon name="rerun" size={15} />Re-run</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: grid, gap: 14, alignItems: 'start' }}>
        {compareArt
          ? <BeforeAfter before={s.preview} after={compareArt[1]} onExpand={() => setZoom(true)} />
          : arts.map(([name, url]) => <ArtifactCard key={name} name={name} url={url} />)}
      </div>

      {zoom && compareArt && s.preview && (
        <FullscreenCompare before={s.preview} after={compareArt[1]} onClose={() => setZoom(false)} />
      )}

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
