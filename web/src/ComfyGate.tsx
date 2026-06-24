// Gates a ComfyUI-backed feature behind a one-time, in-app setup wizard:
// Install ComfyUI -> Download models -> Start. Polls /api/comfy/status and, once
// the engine is installed + running with all models present, renders the feature.
import { useEffect, useState, type ReactNode } from 'react'
import {
  ComfyStatus, getComfyStatus, comfyInstall, comfyDownload, comfyStart,
} from './api'
import { Button, Card } from './ui'

function Mark({ ok }: { ok: boolean }) {
  return <span className={ok ? 'text-emerald-400' : 'text-gray-600'}>{ok ? '✓' : '○'}</span>
}

export default function ComfyGate({ children }: { children: ReactNode }) {
  const [s, setS] = useState<ComfyStatus | null>(null)
  const [busyBtn, setBusyBtn] = useState('')

  async function refresh() {
    try { setS(await getComfyStatus()) } catch { /* server may be down */ }
  }
  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 2500)         // live progress while installing/downloading
    return () => clearInterval(t)
  }, [])

  if (!s) {
    return <Card><div className="text-sm text-gray-500">Checking ComfyUI…</div></Card>
  }

  const models = Object.entries(s.models)
  const modelsReady = models.length > 0 && models.every(([, ok]) => ok)
  const ready = s.installed && s.running && modelsReady
  if (ready) return <>{children}</>

  async function act(fn: () => Promise<any>, name: string) {
    setBusyBtn(name)
    try { await fn() } finally { setBusyBtn(''); refresh() }
  }
  const disabled = s.busy || !!busyBtn

  return (
    <Card>
      <h2 className="mb-1 text-lg font-semibold">Set up the image engine</h2>
      <p className="mb-5 text-xs text-gray-400">
        This feature runs on a local ComfyUI engine. One-time setup — handled right here,
        you never leave this app.
      </p>

      <ol className="space-y-5 text-sm">
        <li className="flex items-start gap-3">
          <Mark ok={s.installed} />
          <div className="flex-1">
            <div className="font-medium">Install ComfyUI</div>
            <div className="break-all text-xs text-gray-500">{s.dir}</div>
            {!s.installed && (
              <div className="mt-2">
                <Button disabled={disabled} onClick={() => act(comfyInstall, 'install')}>
                  {s.busy && s.action === 'install' ? 'Installing…' : 'Install'}
                </Button>
              </div>
            )}
          </div>
        </li>

        <li className="flex items-start gap-3">
          <Mark ok={modelsReady} />
          <div className="flex-1">
            <div className="font-medium">Download models</div>
            <ul className="mt-1 space-y-0.5 text-xs text-gray-500">
              {models.map(([label, ok]) => (
                <li key={label} className="flex items-center gap-2"><Mark ok={ok} /> {label}</li>
              ))}
            </ul>
            {s.installed && !modelsReady && (
              <div className="mt-2">
                <Button disabled={disabled} onClick={() => act(comfyDownload, 'download')}>
                  {s.busy && s.action === 'download' ? 'Downloading…' : 'Download models'}
                </Button>
              </div>
            )}
          </div>
        </li>

        <li className="flex items-start gap-3">
          <Mark ok={s.running} />
          <div className="flex-1">
            <div className="font-medium">Start the engine</div>
            <div className="text-xs text-gray-500">{s.url}</div>
            {s.installed && !s.running && (
              <div className="mt-2">
                <Button disabled={disabled} onClick={() => act(comfyStart, 'start')}>
                  {busyBtn === 'start' ? 'Starting…' : 'Start'}
                </Button>
              </div>
            )}
          </div>
        </li>
      </ol>

      {s.error && (
        <div className="mt-4 rounded-md bg-red-500/15 p-3 text-xs text-red-300">{s.error}</div>
      )}
      {(s.busy || s.log.length > 0) && (
        <pre className="mt-4 max-h-56 overflow-auto whitespace-pre-wrap rounded-md bg-black/40 p-3 text-[11px] leading-relaxed text-gray-400">
          {s.log.join('\n')}
        </pre>
      )}
    </Card>
  )
}
