# Relief Studio — UI/UX Data Specification

Pure data for a design system. No theme, no colors, no layout opinions — just the
entities, parameters, states, flows, and data contracts the UI is built from, plus a
set of proposed data fields that would make the experience richer (each marked
**EXISTS** / **AVAILABLE** / **NEEDS-BACKEND**).

---

## 0. What the product is

A local, single-user, GPU-backed AI studio. One web app (served at `:8000`) exposing
several **features**. Each feature takes inputs + parameters, runs on the local GPU,
and returns artifacts. New features are schema-driven (the UI renders entirely from a
feature's declared schema), so the design must be **generic over an arbitrary feature**,
not hand-built per feature.

- Audience: 1 operator (the owner), internal/research use, not public.
- Surfaces: one screen, tab navigation across features, plus setup/onboarding states.
- Hardware context: 1× NVIDIA RTX 3060, 12 GB VRAM. One workflow runs at a time.

---

## 1. Information architecture

```
App
├─ Header
│   ├─ Product name + subtitle
│   └─ Global status indicators (engine + models health)   ← data in §6/§7
├─ Tab navigation  (one tab per feature; 4 today)
└─ Feature workspace  (two regions)
    ├─ Controls region   (inputs + parameters + primary action)
    └─ Results region    (idle / loading / artifacts / error)   ← states in §5
```

The workspace is **the same component for every feature** — it reads the feature's
schema and renders controls + results generically.

---

## 2. Entities — the 4 features

Common fields per feature: `id`, `name`, `description`, `inputs` (what to collect),
`engine` (`local` or `comfy`), `params`, `outputs`. `est_runtime` / `vram` are
approximate (3060) and **proposed metadata** (not in the schema yet).

### 2.1 Image → Relief  `id: relief`
- **Description:** High-resolution TILED monocular-depth heightmap (16-bit PNG) + STL. Tiling recovers facial detail a single depth pass smooths away.
- **Input:** one image (upload)
- **Engine:** local (no ComfyUI)
- **Outputs:** `heightmap` (16-bit grayscale PNG), `stl` (3D mesh, download), `preview` (GLB, interactive 3D)
- **est_runtime:** ~5 s (tiling off) → ~1–4 min (tiling max); scales with tile detail
- **vram:** ~2–4 GB (Depth-Anything-V2) / ~4 GB (Sapiens)
- **Gate:** shows a "lite mode" banner until depth weights are downloaded (§5.3)

| param | type | default | range / choices | step | meaning |
|---|---|---|---|---|---|
| `depth_model` | select | `depth-anything` | `depth-anything`, `depth-anything-3`, `sapiens` | — | Which monocular-depth model estimates shape. sapiens = human-specialized. |
| `tile_detail` | select | `medium` | `off`, `low`, `medium`, `high`, `ultra`, `max` | — | How finely the image is tiled for detail. Higher = sharper faces, slower (off=1 pass → max=144 tiles). |
| `face_crop` | bool | `true` | — | — | Auto-detect the face and concentrate tiling detail there. |
| `da3_variant` | select | `DA3MONO-LARGE` | `DA3MONO-LARGE`, `DA3-LARGE`, `DA3-GIANT`, `DA3-BASE`, `DA3-SMALL` | — | Model size — only relevant when `depth_model = depth-anything-3`. (Conditional/dependent field.) |
| `relief_depth_mm` | number | `8.0` | 2 – 20 | 0.5 | Physical carve depth of the relief, in millimeters. |
| `pixel_mm` | number | `0.1` | 0.02 – 0.5 | 0.01 | Real-world size of one pixel, in mm → sets the physical width/height of the STL. |
| `black_bg` | bool | `true` | — | — | Background sits at zero height (black) vs a mid-gray plate. |
| `invert` | bool | `false` | — | — | Flip near/far (raised ↔ recessed). |
| `flatten_bg` | bool | `true` | — | — | Push the background to a flat plane so only the subject is in relief. |
| `make_solid` | bool | `false` | — | — | Produce a watertight solid (for 3D printing) vs a surface (for CNC). |

Notes for design: `da3_variant` is **conditional** (only meaningful when `depth_model =
depth-anything-3`). `relief_depth_mm` + `pixel_mm` are **physical/engineering** units
and benefit from unit suffixes and a derived "final size" readout (proposed, §7).

### 2.2 Text → Image  `id: text2img`
- **Description:** Generate an image from a prompt with Krea-2-Turbo (GGUF, via ComfyUI).
- **Input:** none (prompt is a parameter)
- **Engine:** comfy (needs the ComfyUI image engine; §5.4 gate)
- **Outputs:** `image` (PNG)
- **est_runtime:** ~5–20 s (8-step turbo, Q4)
- **vram:** ~9–10 GB peak (Q4_K_M)

| param | type | default | range / choices | step | meaning |
|---|---|---|---|---|---|
| `prompt` | text | `""` | free text (multiline) | — | What to generate. |
| `quant` | select | `Q4_K_M` | `Q3_K_M`, `Q4_K_M`, `Q5_K_M`, `Q6_K` | — | Model quantization → quality vs VRAM (higher = better/heavier). |
| `width` | number | `1024` | 512 – 2048 | 64 | Output width (px). |
| `height` | number | `1024` | 512 – 2048 | 64 | Output height (px). |
| `steps` | number | `8` | 4 – 20 | 1 | Sampler steps (turbo is tuned for 8). |
| `seed` | number | `0` | 0 – 2147483647 | 1 | Randomness seed; 0 = random each run. |

### 2.3 Image → Image  `id: img2img`
- **Description:** Transform an image with a prompt (Krea-2-Turbo img2img, via ComfyUI).
- **Input:** one image (upload)
- **Engine:** comfy
- **Outputs:** `image` (PNG)
- **est_runtime / vram:** as text2img

| param | type | default | range / choices | step | meaning |
|---|---|---|---|---|---|
| `prompt` | text | `""` | free text | — | How to transform it. |
| `denoise` | number | `0.6` | 0.1 – 1.0 | 0.05 | Strength — lower stays closer to the original, higher reinvents it. |
| `quant` | select | `Q4_K_M` | `Q3_K_M`, `Q4_K_M`, `Q5_K_M`, `Q6_K` | — | Quality vs VRAM. |
| `steps` | number | `8` | 4 – 20 | 1 | Sampler steps. |
| `seed` | number | `0` | 0 – 2147483647 | 1 | Seed; 0 = random. |

### 2.4 Upscale  `id: upscale`
- **Description:** Upscale an image with an ESRGAN model (ComfyUI; no diffusion model).
- **Input:** one image (upload)
- **Engine:** comfy
- **Outputs:** `image` (PNG, ~4× larger)
- **est_runtime:** ~2–8 s
- **vram:** ~1–2 GB

| param | type | default | range / choices | step | meaning |
|---|---|---|---|---|---|
| `model_name` | select | `4x-UltraSharp.pth` | `4x-UltraSharp.pth`, `RealESRGAN_x4plus.pth`, `4x_foolhardy_Remacri.pth` | — | Which ESRGAN upscaler to use (all ~4×). |

---

## 3. Parameter control vocabulary

There are exactly **5 control types**. A generic form must render each from data:

| type | data fields | renders as | validation |
|---|---|---|---|
| `number` | `default, min, max, step` | slider + numeric readout (or stepper) | clamp to [min,max]; snap to step |
| `select` | `default, choices[]` | single-choice dropdown / segmented | value ∈ choices |
| `bool` | `default` | toggle / checkbox | — |
| `text` | `default` | multiline textarea | free |
| (input) `image` | feature.inputs contains `"image"` | file picker + thumbnail preview | image/* only |

Each param also carries a human `label`. **Proposed additions** to the schema (§7):
`help` (one-line description from the table above), `unit` (`mm`, `px`), `group`
(section grouping), `advanced` (bool, collapse by default), `depends_on`
(e.g. `da3_variant` depends on `depth_model = depth-anything-3`).

---

## 4. Output artifact types

A run returns `artifacts: { name → url }`. The UI renders by file type:

| artifact kind | example name | mime / ext | render as | actions |
|---|---|---|---|---|
| raster image | `heightmap`, `image` | PNG | inline `<img>` | view full, download, (proposed: zoom, compare-to-input) |
| 3D model | `preview` | GLB | interactive 3D viewer (orbit/rotate) | rotate, (proposed: wireframe, measure) |
| mesh download | `stl` | STL | download chip (not previewable inline) | download |

Image features return a single `image`. Relief returns `heightmap` + `stl` + `preview`
together. Design must handle **1..N artifacts of mixed kinds** in the results region.

---

## 5. States & flows

### 5.1 Feature run lifecycle (every feature)
```
idle ──submit──▶ submitting ──▶ running ──success──▶ result
  ▲                                  │
  └──────────────── error ◀──────────┘   (run can also fail)
```
| state | trigger | data shown | controls |
|---|---|---|---|
| idle | initial / after reset | "results appear here" placeholder; current params | editable; primary action enabled if inputs satisfied |
| submitting | user clicks Generate | spinner | action shows busy |
| running | server accepted | **progress** (see §5.2); elapsed (proposed) | action disabled / cancel (proposed) |
| result | run returned artifacts | artifacts (§4) | re-run, tweak params, download |
| error | run failed | error message string | action re-enabled to retry |

`canRun` rule: disabled while running, and (if the feature lists `image` input) until an
image is uploaded.

### 5.2 Progress signals during `running`
- **Local (relief):** no step signal → **indeterminate** progress + a "this can take a
  while at higher tile detail" hint. (Proposed: phase + % — §7.)
- **Comfy (image features):** **determinate** — live `value/max` sampler steps (e.g.
  `6/8`) polled every 400 ms. Renders as a percentage bar. Also `node` (which graph node)
  and `label` (feature). Phases before sampling (model load) currently read as 0/0
  → show "preparing…". (Proposed: explicit phases — §7.)

### 5.3 Relief "lite mode" gate (non-blocking banner)
Relief works without weights but at crude quality. Banner appears until the core depth
weights are present.
```
models.installed == false  ──▶  show banner { message, per-model checklist, Download button, log }
   └─ user clicks Download ──▶ background download (live log) ──▶ installed == true ──▶ banner self-hides
```
Data: `GET /api/models/status` → `{ installed, models{label→bool}, busy, log[], error }`.

### 5.4 ComfyUI engine setup gate (blocking wizard, image features only)
Image features can't run until the engine is installed + models present + running. A
3-step wizard gates the feature:
```
Step 1 Install  (installed?)        → button → background git+pip (live log)
Step 2 Download (all models?)       → button → background downloads (live % log)
Step 3 Start    (running?)          → button → launch; streams boot log; may error w/ exit code
   when installed && all-models && running  ──▶ gate opens, feature workspace renders
```
Each step has tri-state: `done (✓)` / `available (actionable)` / `pending (waiting on prior)`.
Data: `GET /api/comfy/status` (polled 2.5 s) → see §6.

### 5.5 Reset rules
Switching tabs resets params to defaults and clears result/error/progress for that
feature. One feature runs at a time (single GPU).

---

## 6. Backend data contracts (EXISTS today)

### Endpoints
| method | path | purpose |
|---|---|---|
| GET | `/api/health` | liveness `{ ok, features[] }` |
| GET | `/api/features` | array of feature schemas (§2) |
| POST | `/api/features/{id}/run` | run a feature (multipart: optional `file`, `params` JSON) |
| GET | `/api/jobs/{job}/{name}` | fetch an artifact file |
| GET | `/api/models/status` | relief depth-weights status |
| POST | `/api/models/download` | start background download of relief weights |
| GET | `/api/comfy/status` | image-engine status |
| POST | `/api/comfy/install` | start background ComfyUI install |
| POST | `/api/comfy/download` | start background model downloads |
| POST | `/api/comfy/start` | launch the engine |
| GET | `/api/comfy/progress` | live generation progress |

### Response shapes (JSON)
```jsonc
// GET /api/features  → [ FeatureSchema ]
{ "id":"relief", "name":"Image → Relief", "description":"…",
  "inputs":["image"], "needs_comfy":false,
  "params":[ { "name","type","default","label","min","max","step","choices" } ] }

// POST /api/features/{id}/run  → success
{ "job":"a1b2c3", "feature":"relief", "artifacts": { "heightmap":"/api/jobs/…", "stl":"…", "preview":"…" } }
// …or failure
{ "job":"a1b2c3", "error":"human-readable message" }

// GET /api/models/status
{ "installed": false,
  "models": { "birefnet": true, "depth_anything": false },
  "busy": false, "log": ["downloading …"], "error": null, "done": false }

// GET /api/comfy/status
{ "installed": true, "running": false,
  "dir": "F:\\ComfyUI", "url": "127.0.0.1:8188",
  "models": { "transformer · Krea-2-Turbo Q4_K_M (~7.5 GB)": true, "VAE · qwen_image (~0.25 GB)": false, … },
  "busy": false, "action": "download"|"install"|null,
  "log": ["[comfy] …", "✓ …"], "error": null, "done": true }

// GET /api/comfy/progress
{ "active": true, "value": 6, "max": 8, "node": "2", "label": "text2img" }
```

---

## 7. Proposed additional data (richer UX)

Marked **EXISTS** (already returned) · **AVAILABLE** (data exists at the source, just
needs an endpoint) · **NEEDS-BACKEND** (small new work). All are data, not theme.

### 7.1 Loading / progress detail
| field | status | notes |
|---|---|---|
| `phase` enum: `queued → loading_model → sampling → decoding → saving` | NEEDS-BACKEND | ComfyUI ws emits node-level events we can map to phases; turns the bar into a labeled stepper |
| `value` / `max` sampler steps | EXISTS | already drives the bar |
| `percent` (0–100) | EXISTS (derived) | `value/max` |
| `eta_seconds` | NEEDS-BACKEND | derive from step rate (steps/sec × remaining) |
| `iterations_per_second` (it/s) | NEEDS-BACKEND | classic diffusion stat |
| relief tiling progress `tiles_done / tiles_total` | NEEDS-BACKEND | gives relief a determinate bar instead of a spinner |

### 7.2 Download progress (model fetches)
| field | status | notes |
|---|---|---|
| per-file `percent` | EXISTS (in log text) | currently logged as `x.xx/ y.yy GB (NN%)` |
| structured `{ file, bytes_done, bytes_total, percent, speed_bps, eta_s }` | NEEDS-BACKEND | turns the text log into real per-file progress bars |
| overall download `{ files_done, files_total, bytes_total }` | NEEDS-BACKEND | aggregate bar for the 4-file set |

### 7.3 GPU / system stats  (great for a status panel)
| field | status | source |
|---|---|---|
| `device_name` (e.g. "RTX 3060") | AVAILABLE | ComfyUI `/system_stats` (when engine up); `torch.cuda.get_device_name` otherwise |
| `vram_total`, `vram_free`, `vram_used` | AVAILABLE | ComfyUI `/system_stats` `devices[].vram_total/vram_free`; relief side via `torch.cuda.mem_get_info()` |
| `vram_used_percent` | AVAILABLE (derived) | for a gauge |
| `gpu_utilization_percent`, `gpu_temp_c`, `power_w` | NEEDS-BACKEND | `nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw` |
| `which_model_loaded` (relief depth model / comfy quant) | NEEDS-BACKEND | so the UI shows what's resident |
| `disk_free_gb` on the model drive | NEEDS-BACKEND | warn before a multi-GB download |

> Note: image features peak ~9–10 GB on a 12 GB card, and relief + image engine **cannot
> be resident at once** — the server unloads relief models before an image run. A VRAM
> gauge + "engine: relief | image" indicator communicates this constraint well.

### 7.4 Run metadata / metrics (per job)
| field | status | notes |
|---|---|---|
| `created_at`, `started_at`, `finished_at`, `duration_s` | NEEDS-BACKEND | for history + "took 12.4 s" |
| `params_used` (echo of inputs) | NEEDS-BACKEND | reproduce/compare |
| `seed_used` (resolved when seed=0/random) | NEEDS-BACKEND | so a good random result is reproducible |
| `output_dimensions`, `file_size` | NEEDS-BACKEND | shown under each artifact |

### 7.5 Job history / gallery
| field | status | notes |
|---|---|---|
| list of past jobs `{ id, feature, thumbnail, params, created_at, duration }` | NEEDS-BACKEND | jobs already persist under `data/jobs/<id>/`; expose a `GET /api/jobs` to list them |
| per-job actions: open, re-run with same params, delete, download | NEEDS-BACKEND | a "recent generations" strip is high-value UX |

### 7.6 Feature metadata (static, add to schema)
| field | status | notes |
|---|---|---|
| `category` (`fabrication` for relief; `image` for the rest) | NEEDS-BACKEND | group tabs |
| `est_runtime`, `vram_cost`, `output_kinds` | NEEDS-BACKEND | set expectations before running |
| `icon_hint` (semantic, e.g. `cube`, `text`, `image`, `arrows-out`) | NEEDS-BACKEND | tab/affordance icons without a theme |
| param `help`, `unit`, `group`, `advanced`, `depends_on` | NEEDS-BACKEND | better forms (helper text, sections, conditional fields) |

### 7.7 Engine / health summary (for a global status area)
| field | status | notes |
|---|---|---|
| relief models: `installed` + per-model checklist | EXISTS | `/api/models/status` |
| image engine: `installed / running / models-ready` | EXISTS | `/api/comfy/status` |
| a single derived `system_ready` per feature | NEEDS-BACKEND (derived) | "this feature is ready / needs setup" |

### 7.8 Notifications (frontend-only)
Toasts/inline banners for: run complete, run failed (with message), download complete,
engine started, engine crashed (with exit code). Data already present in the status/run
responses; this is presentation only.

---

## 8. Glossary (label the domain correctly)

- **Heightmap** — grayscale image where brightness = height; the relief surface.
- **STL** — 3D mesh file for CNC/printing. **GLB** — 3D model for the in-app preview.
- **Bas-relief** — shallow 3D carving raised from a flat background.
- **Depth model / monocular depth** — AI that estimates 3D shape from one 2D photo.
- **Tiling** — splitting the image into tiles, estimating depth per tile, recombining; recovers fine facial detail.
- **Sapiens / Depth-Anything / DA3** — specific depth models (human-specialized vs general).
- **Quant (Q3/Q4/Q5/Q6)** — model compression level; higher = better quality, more VRAM.
- **Seed** — number that makes a random generation reproducible.
- **Denoise / strength** — in img2img, how far from the original the result may drift.
- **Steps** — diffusion sampler iterations.
- **ESRGAN** — image super-resolution (upscaling) model.
- **ComfyUI** — the local engine that hosts the image models (managed invisibly by this app).
- **VRAM** — GPU memory (12 GB here); the budget that limits resolution/model size.

---

## 9. Surfaces the data implies (data-driven, no theme)

1. **Feature workspace** — generic controls + results; the core screen (§1, §5.1).
2. **Setup wizard** — ComfyUI 3-step gate for image features (§5.4).
3. **Models banner** — relief lite→full download (§5.3).
4. **System/health panel** — engine + models + GPU/VRAM stats (§6, §7.3, §7.7).
5. **History / gallery** — past jobs with re-run (§7.5).
6. **Progress surface** — phase + %/ETA + it/s, per run (§7.1).

Items 4–6 are the biggest UX upgrades and are mostly **data we can expose**, not theme.
