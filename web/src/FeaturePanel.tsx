// Generic, schema-driven feature runner. Renders inputs + params from the
// feature's schema and shows whatever artifacts come back — so relief works now
// and future features (upscale/text2img) appear with no changes here.
import React, { useEffect, useMemo, useState } from 'react'
import { FeatureSchema, RunResult, runFeature } from './api'
import { Button, Card, Field, NumberSlider, Toggle, Select } from './ui'

function defaults(f: FeatureSchema): Record<string, any> {
  const p: Record<string, any> = {}
  for (const s of f.params) p[s.name] = s.default
  return p
}

function Artifact({ name, url }: { name: string; url: string }) {
  const lower = url.toLowerCase()
  if (lower.endsWith('.glb') || lower.endsWith('.gltf')) {
    // @ts-ignore — model-viewer is a web component (loaded in index.html)
    return <model-viewer src={url} camera-controls auto-rotate
      camera-orbit="-20deg 72deg 100%" min-field-of-view="25deg" exposure="1.15"
      shadow-intensity="1" tone-mapping="neutral" interaction-prompt="none" />
  }
  if (/\.(png|jpg|jpeg|webp)$/.test(lower)) {
    return <img src={url} alt={name} className="w-full rounded-lg border border-white/10" />
  }
  return (
    <a href={url} download className="inline-block rounded-md bg-white/10 px-3 py-2 text-sm hover:bg-white/20">
      ⬇ Download {name}
    </a>
  )
}

export default function FeaturePanel({ feature }: { feature: FeatureSchema }) {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string>('')
  const [params, setParams] = useState<Record<string, any>>(defaults(feature))
  const [running, setRunning] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<RunResult | null>(null)

  useEffect(() => { setParams(defaults(feature)); setResult(null); setError('') }, [feature.id])

  const needsImage = feature.inputs.includes('image')
  const canRun = !running && (!needsImage || !!file)

  function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0] || null
    setFile(f)
    setPreview(f ? URL.createObjectURL(f) : '')
  }

  async function generate() {
    setRunning(true); setError(''); setResult(null)
    try {
      setResult(await runFeature(feature.id, file, params))
    } catch (e: any) {
      setError(e.message || String(e))
    } finally {
      setRunning(false)
    }
  }

  const artifacts = useMemo(
    () => (result ? Object.entries(result.artifacts) : []),
    [result],
  )

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[360px_1fr]">
      {/* controls */}
      <Card>
        <h2 className="mb-1 text-lg font-semibold">{feature.name}</h2>
        <p className="mb-4 text-xs text-gray-400">{feature.description}</p>

        {needsImage && (
          <div className="mb-4">
            <Field label="Input image">
              <input type="file" accept="image/*" onChange={onFile}
                className="block w-full text-xs text-gray-400 file:mr-3 file:rounded-md file:border-0 file:bg-white/10 file:px-3 file:py-2 file:text-gray-200 hover:file:bg-white/20" />
            </Field>
            {preview && <img src={preview} className="mt-3 max-h-48 rounded-lg border border-white/10" />}
          </div>
        )}

        <div className="space-y-3">
          {feature.params.map((p) => (
            <Field key={p.name} label={p.label || p.name}>
              {p.type === 'number' && (
                <NumberSlider value={params[p.name]} min={p.min ?? 0} max={p.max ?? 1}
                  step={p.step ?? 0.01} onChange={(v) => setParams((s) => ({ ...s, [p.name]: v }))} />
              )}
              {p.type === 'select' && (
                <Select value={params[p.name]} choices={p.choices || []}
                  onChange={(v) => setParams((s) => ({ ...s, [p.name]: v }))} />
              )}
              {p.type === 'bool' && (
                <Toggle checked={!!params[p.name]} label={p.label || p.name}
                  onChange={(v) => setParams((s) => ({ ...s, [p.name]: v }))} />
              )}
              {p.type === 'text' && (
                <textarea value={params[p.name] || ''} rows={3}
                  placeholder="Describe the image…"
                  onChange={(e) => setParams((s) => ({ ...s, [p.name]: e.target.value }))}
                  className="w-full rounded-md border border-white/10 bg-white/5 px-3 py-2 text-sm text-gray-100" />
              )}
            </Field>
          ))}
        </div>

        <div className="mt-5">
          <Button onClick={generate} disabled={!canRun}>
            {running ? 'Generating…' : 'Generate'}
          </Button>
          {needsImage && !file && <p className="mt-2 text-xs text-gray-500">Upload an image first.</p>}
        </div>
      </Card>

      {/* results */}
      <Card>
        {error && <div className="mb-4 rounded-md bg-red-500/15 p-3 text-sm text-red-300">{error}</div>}
        {!result && !error && (
          <div className="flex h-full min-h-[300px] items-center justify-center text-sm text-gray-500">
            {running ? 'Running on the GPU…' : 'Results appear here.'}
          </div>
        )}
        {artifacts.length > 0 && (
          <div className="space-y-4">
            {artifacts.map(([name, url]) => (
              <div key={name}>
                <div className="mb-1 text-xs uppercase tracking-wide text-gray-500">{name}</div>
                <Artifact name={name} url={url} />
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
