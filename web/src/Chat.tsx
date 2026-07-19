// The Chat section — a full-height conversational UI over the local Bonsai model.
//
// Layout: thread sidebar · message thread (centred, max 780px) · sticky composer.
// Before a model can answer there are three setup stages (build the engine, download
// weights, load them into VRAM); ChatSetup below renders whichever one is outstanding,
// mirroring how ComfyWizard gates the ComfyUI-backed features.
import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useChat, splitThinking, type Chat as ChatState, type Msg } from './useChat'
import { Markdown } from './markdown'
import { Icon } from './icons'
import { Button, Slider } from './ds'
import type { LlmModel, LlmProgress } from './api'

const CARD = { borderRadius: 14, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)' } as const
const LABEL = { font: '600 12px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' } as const

const SUGGESTIONS = [
  'Explain what a ternary quantized model is, simply.',
  'Write a Python function that reads an STL and reports its bounding box.',
  'Draft a short product description for a CNC-carved wooden relief panel.',
  'What G-code command sets a feed rate, and what units does it use?',
]

// ---------------------------------------------------------------- setup gate
function LogPanel({ lines }: { lines: string[] }) {
  const ref = useRef<HTMLPreElement>(null)
  useLayoutEffect(() => { if (ref.current) ref.current.scrollTop = ref.current.scrollHeight }, [lines])
  if (!lines.length) return null
  return (
    <pre ref={ref} style={{ margin: '12px 0 0', maxHeight: 210, overflow: 'auto', padding: '11px 13px', borderRadius: 10, background: 'var(--hf-surface-2)', border: '1px solid var(--hf-border)', font: '400 11.5px/1.6 var(--hf-font-mono)', color: 'var(--hf-text-secondary)', whiteSpace: 'pre-wrap' }}>
      {lines.join('\n')}
    </pre>
  )
}

/** Determinate bar for the in-flight weight download — a 7 GB fetch needs real feedback. */
function DownloadBar({ p }: { p: LlmProgress }) {
  const gb = (n: number) => (n / 1e9).toFixed(2)
  return (
    <div style={{ marginTop: 11 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 6 }}>
        <span style={{ font: '600 12px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>Downloading…</span>
        <span style={{ font: '500 11.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>
          {gb(p.done)} / {gb(p.total)} GB · {p.percent}%
        </span>
      </div>
      <div style={{ height: 6, borderRadius: 99, background: 'var(--hf-fill-strong)', overflow: 'hidden' }}>
        <div style={{ height: '100%', borderRadius: 99, width: `${p.percent}%`, background: 'var(--hf-action)', transition: 'width .3s var(--hf-ease-out)' }} />
      </div>
    </div>
  )
}

function ModelCard({ m, present, loaded, busy, canLoad, progress, onDownload, onLoad }: {
  m: LlmModel; present: boolean; loaded: boolean; busy: boolean; canLoad: boolean
  progress?: LlmProgress; onDownload: () => void; onLoad: () => void
}) {
  const downloading = progress?.key === m.key
  return (
    <div style={{ ...CARD, padding: 16, display: 'flex', flexDirection: 'column', gap: 10, borderColor: loaded ? 'var(--hf-accent)' : 'var(--hf-border)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ font: '650 14px var(--hf-font-sans)' }}>{m.label}</span>
            <span style={{ font: '600 10.5px var(--hf-font-sans)', letterSpacing: '.03em', textTransform: 'uppercase', padding: '3px 7px', borderRadius: 6, background: 'var(--hf-fill-medium)', color: 'var(--hf-text-secondary)' }}>{m.tag}</span>
            {loaded && <span style={{ font: '600 10.5px var(--hf-font-sans)', letterSpacing: '.03em', textTransform: 'uppercase', padding: '3px 7px', borderRadius: 6, background: 'var(--hf-accent-dim)', color: 'var(--hf-accent)' }}>Loaded</span>}
          </div>
          <p style={{ margin: '7px 0 0', font: '400 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>{m.blurb}</p>
        </div>
        <span style={{ flexShrink: 0, font: '600 12px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{m.size_gb.toFixed(2)} GB</span>
      </div>
      {downloading ? <DownloadBar p={progress!} /> : (
        <div style={{ display: 'flex', gap: 8 }}>
          {/* Downloading only needs the network — deliberately NOT gated on the build, so a
              7 GB fetch can run while the user is still installing a compiler. */}
          {!present
            ? <Button size="sm" variant="secondary" onClick={onDownload} disabled={busy}>Download {m.size_gb.toFixed(1)} GB</Button>
            : loaded
              ? <span style={{ display: 'flex', alignItems: 'center', gap: 6, font: '600 12.5px var(--hf-font-sans)', color: 'var(--hf-accent)' }}><Icon name="check" size={14} sw={2.2} />Ready</span>
              : <Button size="sm" onClick={onLoad} disabled={busy || !canLoad}>Load into VRAM</Button>}
          {present && !loaded && !canLoad && (
            <span style={{ alignSelf: 'center', font: '500 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
              Downloaded — build the engine to load it
            </span>
          )}
        </div>
      )}
    </div>
  )
}

function ChatSetup({ c }: { c: ChatState }) {
  const llm = c.llm
  if (!llm) return <div style={{ padding: 30, fontSize: 13, color: 'var(--hf-text-tertiary)' }}>Checking the chat engine…</div>
  const tc = llm.toolchain
  const anyModel = Object.values(llm.models).some(Boolean)
  const missing = (['git', 'cmake'] as const).filter((k) => !tc[k])

  return (
    <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '28px 26px' }}>
      <div style={{ maxWidth: 720, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div>
          <h2 style={{ margin: 0, font: '700 21px var(--hf-font-sans)', letterSpacing: '-.015em' }}>Set up the chat engine</h2>
          <p style={{ margin: '8px 0 0', font: '400 13.5px/1.7 var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>
            Bonsai runs fully offline on this machine. Its weights use a custom <code style={{ font: '500 12.5px var(--hf-font-mono)', background: 'var(--hf-fill-medium)', padding: '.12em .38em', borderRadius: 5 }}>dspark</code> architecture,
            so it needs Prism ML's llama.cpp fork — stock llama.cpp cannot load these files. This is a one-time build.
          </p>
        </div>

        {/* stage 1 — build */}
        <div style={{ ...CARD, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 22, height: 22, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', background: llm.built ? 'var(--hf-accent)' : 'var(--hf-fill-strong)', color: llm.built ? '#fff' : 'var(--hf-text-secondary)', font: '700 11px var(--hf-font-sans)' }}>
                {llm.built ? <Icon name="check" size={13} sw={2.6} /> : '1'}
              </span>
              <span style={{ font: '650 14px var(--hf-font-sans)' }}>Build llama.cpp (PrismML fork)</span>
            </div>
            {llm.built
              ? <span style={{ font: '600 12.5px var(--hf-font-sans)', color: 'var(--hf-accent)' }}>Built</span>
              : <Button size="sm" onClick={c.install} loading={llm.busy && llm.action === 'install'} disabled={llm.busy || missing.length > 0}>
                  {llm.busy && llm.action === 'install' ? 'Building…' : 'Build'}
                </Button>}
          </div>
          {!llm.built && (
            <div style={{ marginTop: 12, display: 'flex', flexWrap: 'wrap', gap: 7 }}>
              {/* required tools only — GPU support is reported separately, since its absence
                  makes the build slower rather than impossible. */}
              {(['git', 'cmake', 'compiler'] as const).map((k) => (
                <span key={k} style={{ display: 'flex', alignItems: 'center', gap: 5, height: 26, padding: '0 9px', borderRadius: 99, border: '1px solid var(--hf-border)', font: '500 11.5px var(--hf-font-mono)', color: tc[k] ? 'var(--hf-accent)' : 'var(--hf-text-tertiary)' }}>
                  <Icon name={tc[k] ? 'check' : 'x'} size={11} sw={2.4} />{k}
                </span>
              ))}
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, height: 26, padding: '0 9px', borderRadius: 99, border: '1px solid var(--hf-border)', font: '500 11.5px var(--hf-font-mono)', color: tc.gpu === 'cpu' ? 'var(--hf-text-tertiary)' : 'var(--hf-accent)' }}>
                <Icon name={tc.gpu === 'cpu' ? 'x' : 'check'} size={11} sw={2.4} />
                {tc.gpu === 'cuda' ? 'cuda gpu' : tc.gpu === 'metal' ? 'metal gpu' : 'cpu only'}
              </span>
            </div>
          )}
          {/* only while it still matters — a finished build makes the toolchain moot */}
          {!llm.built && missing.length > 0 && (
            <p style={{ margin: '11px 0 0', font: '500 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-warning)' }}>
              {missing.join(' and ')} {missing.length > 1 ? 'are' : 'is'} not on PATH — install {missing.length > 1 ? 'them' : 'it'} first, then reopen the terminal.
            </p>
          )}
          {!llm.built && tc.gpu === 'cpu' && (
            <p style={{ margin: '9px 0 0', font: '400 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
              No CUDA toolkit found, so the build would be <strong>CPU-only</strong> — it works, but a 27B
              model will answer slowly. For full GPU speed install the{' '}
              <a href="https://developer.nvidia.com/cuda-downloads" target="_blank" rel="noreferrer noopener"
                style={{ color: 'var(--hf-info)' }}>CUDA Toolkit</a>, then restart the server so it is picked up.
            </p>
          )}
          {!llm.built && tc.gpu === 'metal' && (
            <p style={{ margin: '9px 0 0', font: '400 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
              Will build with <strong>Metal</strong> GPU acceleration — no CUDA toolkit needed on macOS.
            </p>
          )}
          {llm.action === 'install' && <LogPanel lines={llm.log} />}
        </div>

        {/* stage 2/3 — weights + load */}
        <div style={{ ...CARD, padding: 16 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 13 }}>
            <span style={{ width: 22, height: 22, borderRadius: 99, display: 'flex', alignItems: 'center', justifyContent: 'center', background: anyModel ? 'var(--hf-accent)' : 'var(--hf-fill-strong)', color: anyModel ? '#fff' : 'var(--hf-text-secondary)', font: '700 11px var(--hf-font-sans)' }}>
              {anyModel ? <Icon name="check" size={13} sw={2.6} /> : '2'}
            </span>
            <span style={{ font: '650 14px var(--hf-font-sans)' }}>Choose a model</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {llm.catalog.map((m) => (
              <ModelCard key={m.key} m={m} present={!!llm.models[m.key]} loaded={llm.loaded === m.key}
                busy={llm.busy} canLoad={llm.built} progress={llm.progress}
                onDownload={() => c.download([m.key])} onLoad={() => c.loadModel(m.key)} />
            ))}
          </div>
          {(llm.action === 'download' || llm.action === 'start') && <LogPanel lines={llm.log} />}
          {anyModel && (
            <p style={{ margin: '13px 0 0', font: '400 11.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)', wordBreak: 'break-all' }}>
              Weights are stored in <code style={{ font: '500 11px var(--hf-font-mono)' }}>{llm.models_dir}</code> — kept
              outside the llama.cpp folder, so rebuilding or updating the engine never touches them.
            </p>
          )}
        </div>

        {llm.error && (
          <div style={{ borderRadius: 12, border: '1px solid var(--hf-danger)', background: 'var(--hf-danger-dim)', padding: '13px 15px', font: '500 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-danger)' }}>
            {llm.error}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- thinking panel
function Thinking({ text, live }: { text: string; live: boolean }) {
  const [open, setOpen] = useState(false)
  if (!text) return null
  return (
    <div style={{ margin: '0 0 10px', borderRadius: 11, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', overflow: 'hidden' }}>
      <button onClick={() => setOpen(!open)} className="rs-hover"
        style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, height: 34, padding: '0 12px', border: 'none', background: 'transparent', cursor: 'pointer', font: '600 12px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>
        <Icon name="brain" size={14} />
        <span>{live ? 'Thinking…' : 'Thought process'}</span>
        <span style={{ flex: 1 }} />
        <span style={{ display: 'flex', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform .18s var(--hf-ease-out)' }}><Icon name="chevronDown" size={14} /></span>
      </button>
      {open && (
        <div style={{ padding: '2px 13px 12px', borderTop: '1px solid var(--hf-border)', font: '400 13px/1.7 var(--hf-font-sans)', color: 'var(--hf-text-secondary)', whiteSpace: 'pre-wrap' }}>
          {text}
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------- messages
function IconBtn({ icon, label, onClick, tone }: { icon: string; label: string; onClick: () => void; tone?: string }) {
  return (
    <button onClick={onClick} title={label} aria-label={label} className="rs-hover"
      style={{ display: 'flex', alignItems: 'center', gap: 5, height: 26, padding: '0 8px', borderRadius: 7, border: 'none', background: 'transparent', cursor: 'pointer', font: '600 11.5px var(--hf-font-sans)', color: tone || 'var(--hf-text-tertiary)' }}>
      <Icon name={icon} size={13} sw={2} />{label}
    </button>
  )
}

function Bubble({ m, streaming, isLast, onRegenerate }: {
  m: Msg; streaming: boolean; isLast: boolean; onRegenerate: () => void
}) {
  const [copied, setCopied] = useState(false)
  // Reasoning arrives either out-of-band (reasoning_content) or inline as <think> tags;
  // splitThinking is a no-op on the former, so `answer` is correct in both cases.
  const { thinking, answer } = splitThinking(m.content)
  const reasoning = m.reasoning || thinking
  const body = answer
  const live = streaming && isLast

  if (m.role === 'user') {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '0 0 22px' }}>
        <div style={{ maxWidth: '82%', padding: '11px 15px', borderRadius: '16px 16px 4px 16px', background: 'var(--hf-surface-3)', font: '400 14.5px/1.65 var(--hf-font-sans)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
          {m.content}
        </div>
      </div>
    )
  }

  const copy = () => {
    navigator.clipboard?.writeText(body).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1600)
    }).catch(() => {})
  }

  return (
    <div style={{ display: 'flex', gap: 13, margin: '0 0 26px' }}>
      <span style={{ flexShrink: 0, width: 28, height: 28, borderRadius: 9, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--hf-white)', color: 'var(--hf-text-inverse)', marginTop: 1 }}>
        <Icon name="sparkle" size={15} />
      </span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <Thinking text={reasoning} live={live && !body} />
        {body
          ? <Markdown text={body} />
          : live && !reasoning
            ? <span style={{ display: 'inline-block', width: 8, height: 16, borderRadius: 2, background: 'var(--hf-text-tertiary)', animation: 'rs-blink 1s steps(2) infinite', verticalAlign: 'middle' }} />
            : null}
        {live && body && <span style={{ display: 'inline-block', width: 7, height: 14, marginLeft: 3, borderRadius: 2, background: 'var(--hf-text-tertiary)', animation: 'rs-blink 1s steps(2) infinite', verticalAlign: 'text-bottom' }} />}

        {m.error && (
          <div style={{ marginTop: 10, borderRadius: 10, border: '1px solid var(--hf-danger)', background: 'var(--hf-danger-dim)', padding: '10px 12px', font: '500 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-danger)' }}>
            {m.error}
          </div>
        )}

        {!live && (body || m.error) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 2, marginTop: 8, marginLeft: -8 }}>
            <IconBtn icon={copied ? 'check' : 'copy'} label={copied ? 'Copied' : 'Copy'} onClick={copy}
              tone={copied ? 'var(--hf-accent)' : undefined} />
            {isLast && <IconBtn icon="rerun" label="Regenerate" onClick={onRegenerate} />}
            {m.timings && (
              <span style={{ marginLeft: 6, font: '500 11.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>
                {m.timings.predicted_n} tok · {m.timings.predicted_per_second.toFixed(1)} tok/s
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- composer
function Composer({ c }: { c: ChatState }) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  // auto-grow to fit the draft, capped so the thread never disappears behind it
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 220) + 'px'
  }, [text])

  const submit = () => {
    const body = text.trim()
    if (!body || c.streaming) return
    setText('')
    c.send(body)
  }

  return (
    <div style={{ flexShrink: 0, padding: '10px 24px 18px', background: 'linear-gradient(to top, var(--hf-bg) 62%, transparent)' }}>
      <div style={{ maxWidth: 780, margin: '0 auto' }}>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 9, padding: 9, borderRadius: 18, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', boxShadow: 'var(--hf-shadow-sm)' }}>
          <textarea
            ref={ref} value={text} rows={1}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              // Enter sends, Shift+Enter inserts a newline — the convention every chat UI uses.
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); submit() }
            }}
            placeholder={c.streaming ? 'Generating…' : 'Message Bonsai…'}
            style={{ flex: 1, minWidth: 0, resize: 'none', border: 'none', outline: 'none', background: 'transparent', padding: '8px 6px 8px 8px', font: '400 14.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-primary)', maxHeight: 220 }}
          />
          {c.streaming ? (
            <button onClick={c.stop} title="Stop generating" aria-label="Stop generating"
              style={{ flexShrink: 0, width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 12, border: 'none', cursor: 'pointer', background: 'var(--hf-surface-3)', color: 'var(--hf-text-primary)' }}>
              <Icon name="stop" size={15} sw={2} />
            </button>
          ) : (
            <button onClick={submit} disabled={!text.trim()} title="Send" aria-label="Send message"
              style={{ flexShrink: 0, width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 12, border: 'none', cursor: text.trim() ? 'pointer' : 'not-allowed', background: text.trim() ? 'var(--hf-action)' : 'var(--hf-fill-strong)', color: text.trim() ? '#fff' : 'var(--hf-text-disabled)', transition: 'background .14s' }}>
              <Icon name="send" size={16} sw={2.2} />
            </button>
          )}
        </div>
        <p style={{ margin: '9px 0 0', textAlign: 'center', font: '400 11.5px var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
          Runs entirely on this machine. Bonsai is a compressed model — check anything important.
        </p>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------- settings drawer
function NumRow({ label, value, min, max, step, suffix, onChange, help }: {
  label: string; value: number; min: number; max: number; step: number
  suffix?: string; onChange: (v: number) => void; help?: string
}) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 7 }}>
        <span style={LABEL}>{label}</span>
        <span style={{ font: '600 12px var(--hf-font-mono)', color: 'var(--hf-text-primary)' }}>{value}{suffix || ''}</span>
      </div>
      <Slider value={value} min={min} max={max} step={step} onChange={onChange} />
      {help && <p style={{ margin: '7px 0 0', font: '400 11.5px/1.55 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>{help}</p>}
    </div>
  )
}

function Settings({ c }: { c: ChatState }) {
  if (!c.settingsOpen) return null
  const s = c.sampling
  const set = (k: keyof typeof s) => (v: number) => c.setSampling({ ...s, [k]: v })
  return (
    <aside style={{ width: 320, flexShrink: 0, borderLeft: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)', overflow: 'auto', padding: '18px 18px 26px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <span style={{ font: '650 14px var(--hf-font-sans)' }}>Settings</span>
        <button onClick={() => c.setSettingsOpen(false)} className="rs-hover" aria-label="Close settings"
          style={{ width: 28, height: 28, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--hf-text-secondary)' }}>
          <Icon name="x" size={15} />
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
        <div>
          <span style={LABEL}>System prompt</span>
          <textarea value={c.systemPrompt} onChange={(e) => c.setSystemPrompt(e.target.value)} rows={3}
            placeholder="You are a helpful assistant"
            style={{ marginTop: 7, width: '100%', resize: 'vertical', borderRadius: 11, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', padding: '10px 12px', font: '400 13px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-primary)', outline: 'none' }} />
          <p style={{ margin: '7px 0 0', font: '400 11.5px/1.55 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
            Applies to new turns in every thread.
          </p>
        </div>
        <NumRow label="Temperature" value={s.temperature} min={0} max={2} step={0.05} onChange={set('temperature')}
          help="Higher is more varied. Prism benchmarks the model at 0.7." />
        <NumRow label="Top-p" value={s.top_p} min={0.05} max={1} step={0.05} onChange={set('top_p')}
          help="Nucleus sampling cutoff. Recommended 0.95." />
        <NumRow label="Top-k" value={s.top_k} min={1} max={100} step={1} onChange={set('top_k')}
          help="Candidate pool per token. Recommended 20." />
        <NumRow label="Max tokens" value={s.max_tokens} min={256} max={8192} step={256} onChange={set('max_tokens')}
          help="Upper bound on a single reply." />
        <Button variant="secondary" size="sm" block onClick={c.resetSampling}>Reset to recommended</Button>

        <div style={{ borderTop: '1px solid var(--hf-border)', paddingTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={LABEL}>Model</span>
          {/* Both actions live here, because once a model is loaded the setup gate no longer
              renders — without a download button the second model would be unreachable. */}
          {c.llm?.catalog.map((m) => {
            const present = !!c.llm?.models[m.key]
            const loaded = c.llm?.loaded === m.key
            const downloading = c.llm?.progress?.key === m.key
            const blocked = !!c.llm?.busy || c.streaming
            const act = () => (present ? c.loadModel(m.key) : c.download([m.key]))
            return (
              <div key={m.key}
                style={{ padding: '10px 12px', borderRadius: 11, border: `1px solid ${loaded ? 'var(--hf-accent)' : 'var(--hf-border)'}`, background: 'var(--hf-surface-1)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <span style={{ font: '600 12.5px var(--hf-font-sans)' }}>{m.label}</span>
                  <span style={{ font: '500 11px var(--hf-font-mono)', color: loaded ? 'var(--hf-accent)' : 'var(--hf-text-tertiary)' }}>
                    {loaded ? 'loaded' : `${m.size_gb.toFixed(1)} GB`}
                  </span>
                </div>
                {downloading ? <DownloadBar p={c.llm!.progress} /> : !loaded && (
                  <button onClick={act} disabled={blocked || (present && !c.llm?.built)} className="rs-hover"
                    style={{ marginTop: 8, width: '100%', height: 28, borderRadius: 8, cursor: blocked ? 'default' : 'pointer', border: '1px solid var(--hf-border)', background: 'var(--hf-surface-2)', font: '600 11.5px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>
                    {present ? 'Load into VRAM' : `Download ${m.size_gb.toFixed(1)} GB`}
                  </button>
                )}
              </div>
            )
          })}
          {c.llm?.running && (
            <Button variant="secondary" size="sm" block onClick={c.unload} disabled={c.streaming}>
              Unload · free VRAM
            </Button>
          )}
          <p style={{ margin: 0, font: '400 11.5px/1.55 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
            Only one model fits in VRAM at a time — loading one unloads the image and depth engines.
          </p>
        </div>
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- sidebar
function Threads({ c }: { c: ChatState }) {
  if (!c.sidebarOpen) return null
  return (
    <aside style={{ width: 244, flexShrink: 0, display: 'flex', flexDirection: 'column', borderRight: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)' }}>
      <div style={{ padding: '14px 12px 10px' }}>
        <Button size="sm" block variant="secondary" onClick={c.newThread}>
          <Icon name="plus" size={15} sw={2.2} />New chat
        </Button>
      </div>
      <div style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '2px 8px 14px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {!c.threads.length && (
          <p style={{ margin: '10px 6px', font: '400 12px/1.6 var(--hf-font-sans)', color: 'var(--hf-text-tertiary)' }}>
            No conversations yet.
          </p>
        )}
        {c.threads.map((t) => {
          const on = t.id === c.threadId
          return (
            <div key={t.id} className="rs-hover"
              style={{ display: 'flex', alignItems: 'center', gap: 4, borderRadius: 10, background: on ? 'var(--hf-fill-medium)' : 'transparent' }}>
              <button onClick={() => c.setThreadId(t.id)} title={t.title}
                style={{ flex: 1, minWidth: 0, textAlign: 'left', height: 34, padding: '0 4px 0 10px', border: 'none', background: 'transparent', cursor: 'pointer', font: `${on ? 600 : 500} 12.5px var(--hf-font-sans)`, color: on ? 'var(--hf-text-primary)' : 'var(--hf-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {t.title}
              </button>
              <button onClick={() => c.deleteThread(t.id)} title="Delete chat" aria-label={`Delete ${t.title}`}
                style={{ flexShrink: 0, width: 28, height: 28, marginRight: 3, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 8, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--hf-text-tertiary)' }}>
                <Icon name="trash" size={13} sw={2} />
              </button>
            </div>
          )
        })}
      </div>
    </aside>
  )
}

// ---------------------------------------------------------------- section
export default function Chat() {
  const c = useChat()
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)          // stay glued to the bottom unless the user scrolls up

  const { messages, streaming } = c
  const last = messages[messages.length - 1]

  useEffect(() => {
    const el = scroller.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [messages, last?.content, last?.reasoning])

  const onScroll = () => {
    const el = scroller.current
    if (!el) return
    pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 90
  }

  const ready = !!c.llm?.built && !!c.llm?.running
  const activeModel = c.llm?.catalog.find((m) => m.key === c.llm?.loaded)

  return (
    <div style={{ flex: 1, minHeight: 0, display: 'flex' }}>
      <Threads c={c} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {/* chat toolbar */}
        <div style={{ flexShrink: 0, height: 48, display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px 0 10px', borderBottom: '1px solid var(--hf-border)', background: 'var(--hf-bg-base)' }}>
          <button onClick={() => c.setSidebarOpen(!c.sidebarOpen)} className="rs-hover" title="Toggle conversations"
            style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, border: 'none', background: 'transparent', cursor: 'pointer', color: 'var(--hf-text-secondary)' }}>
            <Icon name="panel" size={17} />
          </button>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, font: '600 13px var(--hf-font-sans)' }}>
            <span style={{ width: 7, height: 7, borderRadius: 99, background: ready ? 'var(--hf-accent)' : 'var(--hf-text-tertiary)' }} />
            {activeModel?.label || 'No model loaded'}
          </span>
          {ready && <span style={{ font: '500 11.5px var(--hf-font-mono)', color: 'var(--hf-text-tertiary)' }}>{(c.llm?.ctx || 0).toLocaleString()} ctx</span>}
          <span style={{ flex: 1 }} />
          <button onClick={() => c.setSettingsOpen(!c.settingsOpen)} className="rs-hover-border" title="Chat settings"
            style={{ width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: 9, cursor: 'pointer', border: `1px solid ${c.settingsOpen ? 'var(--hf-border-strong)' : 'var(--hf-border)'}`, background: c.settingsOpen ? 'var(--hf-fill-medium)' : 'var(--hf-surface-1)', color: 'var(--hf-text-secondary)' }}>
            <Icon name="sliders" size={16} />
          </button>
        </div>

        {!ready ? (
          <ChatSetup c={c} />
        ) : (
          <>
            <div ref={scroller} onScroll={onScroll} style={{ flex: 1, minHeight: 0, overflow: 'auto', padding: '26px 24px 4px' }}>
              <div style={{ maxWidth: 780, margin: '0 auto' }}>
                {!messages.length ? (
                  <div style={{ paddingTop: '8vh', textAlign: 'center' }}>
                    <span style={{ display: 'inline-flex', width: 46, height: 46, borderRadius: 14, alignItems: 'center', justifyContent: 'center', background: 'var(--hf-white)', color: 'var(--hf-text-inverse)' }}>
                      <Icon name="sparkle" size={23} />
                    </span>
                    <h2 style={{ margin: '16px 0 6px', font: '700 21px var(--hf-font-sans)', letterSpacing: '-.015em' }}>
                      How can I help?
                    </h2>
                    <p style={{ margin: '0 0 26px', font: '400 13.5px var(--hf-font-sans)', color: 'var(--hf-text-secondary)' }}>
                      {activeModel?.label} · running locally on this machine
                    </p>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 9, textAlign: 'left' }}>
                      {SUGGESTIONS.map((q) => (
                        <button key={q} onClick={() => c.send(q)} className="rs-hover-border"
                          style={{ padding: '13px 15px', borderRadius: 13, border: '1px solid var(--hf-border)', background: 'var(--hf-surface-1)', cursor: 'pointer', font: '400 13px/1.55 var(--hf-font-sans)', color: 'var(--hf-text-secondary)', textAlign: 'left', transition: 'border-color .14s, color .14s' }}>
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((m, i) => (
                    <Bubble key={m.id} m={m} streaming={streaming} isLast={i === messages.length - 1}
                      onRegenerate={c.regenerate} />
                  ))
                )}
                {c.err && !last?.error && (
                  <div style={{ borderRadius: 12, border: '1px solid var(--hf-danger)', background: 'var(--hf-danger-dim)', padding: '12px 14px', font: '500 12.5px/1.6 var(--hf-font-sans)', color: 'var(--hf-danger)' }}>
                    {c.err}
                  </div>
                )}
              </div>
            </div>
            <Composer c={c} />
          </>
        )}
      </div>

      <Settings c={c} />
    </div>
  )
}
