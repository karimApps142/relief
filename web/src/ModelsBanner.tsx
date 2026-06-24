// Non-blocking banner on the Relief tab: relief still works in "lite" mode (crude CPU
// depth), but this offers a one-click download of the CORE GPU weights (BiRefNet +
// Depth-Anything-V2) that flip it to full quality. Self-hides once installed; the next
// relief run then uses the full backend automatically (no restart). Polls only until
// installed (or while a download is in flight).
import { useEffect, useState } from 'react'
import { ModelsStatus, getModelsStatus, modelsDownload } from './api'
import { Button } from './ui'

export default function ModelsBanner() {
  const [s, setS] = useState<ModelsStatus | null>(null)
  const [busyBtn, setBusyBtn] = useState(false)

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined
    let alive = true
    const loop = async () => {
      const st = await getModelsStatus().catch(() => null)
      if (!alive) return
      if (st) setS(st)
      if (!st || !st.installed) timer = setTimeout(loop, 2500)   // stop once installed
    }
    loop()
    return () => { alive = false; if (timer) clearTimeout(timer) }
  }, [])

  if (!s || s.installed) return null   // installed → full mode, nothing to show

  const download = async () => {
    setBusyBtn(true)
    try { await modelsDownload() } finally { setBusyBtn(false) }
  }
  const models = s.models ? Object.entries(s.models) : []

  return (
    <div className="mb-5 rounded-lg border border-amber-500/20 bg-amber-500/10 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm font-medium text-amber-200">Relief is in lite mode (crude CPU depth)</div>
          <div className="mt-0.5 text-xs text-amber-200/70">
            Download the GPU depth models (~2.3 GB: BiRefNet + Depth-Anything-V2) for full quality.
            The next relief run uses them automatically — no restart.
          </div>
          {models.length > 0 && (
            <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-amber-200/70">
              {models.map(([k, ok]) => (
                <li key={k}>{ok ? '✓' : '○'} {k}</li>
              ))}
            </ul>
          )}
        </div>
        {!s.busy && (
          <Button disabled={busyBtn} onClick={download}>
            {busyBtn ? 'Starting…' : 'Download models'}
          </Button>
        )}
      </div>

      {s.error && <div className="mt-3 text-xs text-red-300">{s.error}</div>}
      {(s.busy || (s.log && s.log.length > 0)) && (
        <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded bg-black/30 p-2 text-[11px] leading-relaxed text-amber-100/70">
          {s.log?.join('\n')}
        </pre>
      )}
    </div>
  )
}
