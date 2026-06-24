import { useEffect, useState } from 'react'
import { FeatureSchema, getFeatures, getModelsStatus } from './api'
import FeaturePanel from './FeaturePanel'
import ComfyGate from './ComfyGate'
import ModelsBanner from './ModelsBanner'

export default function App() {
  const [features, setFeatures] = useState<FeatureSchema[]>([])
  const [active, setActive] = useState<string>('')
  const [err, setErr] = useState('')
  const [installed, setInstalled] = useState<boolean | null>(null)

  useEffect(() => {
    getFeatures()
      .then((fs) => { setFeatures(fs); setActive(fs[0]?.id || '') })
      .catch((e) => setErr(e.message))
    getModelsStatus().then((s) => setInstalled(s.installed))
  }, [])

  const current = features.find((f) => f.id === active)

  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col px-5 py-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Relief Studio</h1>
          <p className="text-xs text-gray-500">Local GPU AI · modular features</p>
        </div>
        {installed !== null && (
          <span className={`rounded-full px-3 py-1 text-xs ${installed ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'}`}>
            {installed ? 'full mode (models installed)' : 'lite / models not installed'}
          </span>
        )}
      </header>

      {err && (
        <div className="mb-4 rounded-md bg-red-500/15 p-3 text-sm text-red-300">
          Can’t reach the API ({err}). Is <code>server.py</code> running on :8000?
        </div>
      )}

      {features.length > 1 && (
        <nav className="mb-5 flex gap-2">
          {features.map((f) => (
            <button key={f.id} onClick={() => setActive(f.id)}
              className={`rounded-md px-3 py-1.5 text-sm ${active === f.id ? 'bg-indigo-500 text-white' : 'bg-white/5 text-gray-300 hover:bg-white/10'}`}>
              {f.name}
            </button>
          ))}
        </nav>
      )}

      {current ? (
        current.needs_comfy
          ? <ComfyGate><FeaturePanel feature={current} /></ComfyGate>
          : <><ModelsBanner /><FeaturePanel feature={current} /></>
      ) : !err && (
        <div className="text-sm text-gray-500">Loading features…</div>
      )}
    </div>
  )
}
