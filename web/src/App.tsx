import { useStudio } from './studio'
import { Icon, featureIcon } from './icons'
import Controls from './Controls'
import Results from './Results'
import { LiteBanner, ComfyWizard, HistoryPanel, SystemPanel, Toasts } from './panels'

export default function App() {
  const s = useStudio()
  const { active, comfy, models, system } = s

  // Feature-aware engine readiness: relight needs the IC-Light node + relight models; image3d
  // needs the Hunyuan3D wrapper node + its shape checkpoint; clarity needs the Ultimate SD
  // Upscale node + the clarity models (Tile ControlNet + checkpoint + LoRA); the rest need Krea.
  const comfyReady = (() => {
    if (!comfy || !comfy.installed || !comfy.running) return false
    if (active?.id === 'relight' || active?.id === 'portrait') {
      const m = Object.values(comfy.relight_models || {})
      return !!comfy.nodes?.iclight && m.length > 0 && m.every(Boolean)
    }
    if (active?.id === 'image3d') {
      const m = Object.values(comfy.hunyuan3d_models || {})
      return !!comfy.nodes?.hy3dwrap && m.length > 0 && m.every(Boolean)
    }
    if (active?.id === 'clarity') {
      const m = Object.values(comfy.clarity_models || {})
      return !!comfy.nodes?.usdu && m.length > 0 && m.every(Boolean)
    }
    if (active?.id === 'image_edit' || active?.id === 'room_mockup' || active?.id === 'apply_texture') {
      const m = Object.values(comfy.qwen_edit_models || {})
      return !!comfy.nodes?.gguf && m.length > 0 && m.every(Boolean)
    }
    return Object.values(comfy.models).every(Boolean)
  })()
  const showComfyGate = !!active && active.engine === 'comfy' && !comfyReady
  const reliefDot = models?.installed ? 'var(--hf-accent)' : 'var(--hf-warning)'
  const comfyDot = comfyReady ? 'var(--hf-accent)' : comfy?.installed ? 'var(--hf-warning)' : 'var(--hf-text-tertiary)'
  const vramPct = system?.vram_percent || 0
  const vramColor = vramPct >= 90 ? 'var(--hf-danger)' : vramPct >= 75 ? 'var(--hf-warning)' : 'var(--hf-accent)'

  const railBtn = (id: string, icon: string, title: string, dot?: boolean) => {
    const on = s.activeId === id
    return (
      <button key={id} onClick={() => s.selectFeature(id)} title={title} className="rs-hover"
        style={{ position: 'relative', width: 46, height: 46, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 13, border: 'none', cursor: 'pointer',
          background: on ? 'var(--hf-fill-medium)' : 'transparent', color: on ? 'var(--hf-text-primary)' : 'var(--hf-text-secondary)' }}>
        <Icon name={icon} size={20} />
        {dot && <span style={{ position: 'absolute', top: 7, right: 7, width: 7, height: 7, borderRadius: 99, background: 'var(--hf-warning)', border: '1.5px solid var(--hf-bg-base)' }} />}
      </button>
    )
  }

  const pill = (dot: string, label: string) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, height: 32, padding: '0 11px', borderRadius: 99, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', fontSize: 12, color: 'var(--hf-text-secondary)' }}>
      <span style={{ width: 7, height: 7, borderRadius: 99, background: dot }} />{label}
    </div>
  )

  return (
    <div style={{ display: 'flex', height: '100vh', width: '100%', overflow: 'hidden', background: 'var(--hf-bg)' }}>
      {/* ICON RAIL */}
      <aside style={{ width: 72, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, padding: '16px 0 14px', borderRight: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)' }}>
        <span title="Relief Studio · local" style={{ width: 38, height: 38, borderRadius: 11, background: 'var(--hf-white)', color: 'var(--hf-text-inverse)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}><Icon name="logo" size={20} /></span>
        <div style={{ width: 26, height: 1, background: 'var(--hf-border)', margin: '9px 0 7px' }} />
        {s.features.map((f) => railBtn(f.id, featureIcon(f.icon), f.name, f.id === 'relief' && !!models && !models.installed))}
        <div style={{ flex: 1 }} />
        <button onClick={() => s.setSysOpen(true)} title={system ? `VRAM ${system.vram_used} / ${system.vram_total} GB` : 'System'} className="rs-hover"
          style={{ width: 46, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 5, padding: '8px 0', borderRadius: 13, border: 'none', background: 'transparent', cursor: 'pointer' }}>
          <div style={{ width: 7, height: 30, borderRadius: 99, background: 'var(--hf-fill-strong)', overflow: 'hidden', display: 'flex', flexDirection: 'column', justifyContent: 'flex-end' }}>
            <div style={{ width: '100%', height: `${vramPct}%`, background: vramColor, transition: 'height .25s var(--hf-ease-out)' }} />
          </div>
          <span style={{ font: '600 9px var(--hf-font-sans)', letterSpacing: '.04em', color: 'var(--hf-text-tertiary)' }}>VRAM</span>
        </button>
        <button onClick={() => s.setSysOpen(true)} title="System & health" className="rs-hover"
          style={{ width: 46, height: 46, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 13, border: 'none', background: 'transparent', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}><Icon name="system" size={20} /></button>
      </aside>

      {/* MAIN */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <header style={{ height: 62, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, padding: '0 26px', borderBottom: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9, minWidth: 0 }}>
            <span style={{ font: '700 14.5px var(--hf-font-sans)', letterSpacing: '-.01em' }}>Relief Studio</span>
            <span style={{ color: 'var(--hf-text-tertiary)', flexShrink: 0, display: 'flex' }}><Icon name="chevronRight" size={14} sw={2} /></span>
            <span style={{ font: '600 14px var(--hf-font-sans)', color: 'var(--hf-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{active?.name || '…'}</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            {pill(reliefDot, 'Depth weights')}
            {pill(comfyDot, 'Image engine')}
            <button onClick={() => s.setHistoryOpen(!s.historyOpen)} title="Recent generations" className="rs-hover-border"
              style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, cursor: 'pointer', transition: 'background .14s,border-color .14s,color .14s', border: `1px solid ${s.historyOpen ? 'var(--hf-border-strong)' : 'var(--hf-border)'}`, background: s.historyOpen ? 'var(--hf-fill-medium)' : 'var(--hf-surface-1)', color: s.historyOpen ? 'var(--hf-text-primary)' : 'var(--hf-text-secondary)' }}><Icon name="history" size={18} /></button>
            <button onClick={() => s.setSysOpen(true)} title="System & health" className="rs-hover-border"
              style={{ width: 34, height: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 10, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', color: 'var(--hf-text-secondary)', cursor: 'pointer' }}><Icon name="system" size={18} /></button>
          </div>
        </header>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'auto' }}>
          {s.bootErr && (
            <div style={{ margin: '16px 26px', borderRadius: 12, border: '1px solid var(--hf-danger)', background: 'var(--hf-danger-dim)', padding: '14px 16px', font: '500 13px var(--hf-font-sans)', color: 'var(--hf-danger)' }}>
              Can’t reach the API ({s.bootErr}). Is the server running on :8000?
            </div>
          )}
          {active && (showComfyGate ? (
            <ComfyWizard s={s} />
          ) : (
            <div style={{ flex: 1, minHeight: 0, display: 'grid', gridTemplateColumns: '420px 1fr' }}>
              <Controls s={s} />
              <section style={{ minWidth: 0, minHeight: 0, overflow: 'auto', padding: '20px 24px', background: 'var(--hf-bg)' }}>
                <LiteBanner s={s} />
                <Results s={s} />
              </section>
            </div>
          ))}
          {!active && !s.bootErr && <div style={{ padding: 26, fontSize: 13, color: 'var(--hf-text-tertiary)' }}>Loading features…</div>}
        </div>
      </div>

      <HistoryPanel s={s} />
      <SystemPanel s={s} />
      <Toasts s={s} />
    </div>
  )
}
