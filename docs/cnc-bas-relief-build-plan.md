# CNC Bas-Relief Generator — Full Build Plan

**What it is:** a **local tool** that takes an ordinary image and produces a clean, high-detail **bas-relief heightmap** (16-bit) plus an **STL**, ready for CNC carving or 3D printing — the same kind of output as Sculptok and 翰林AI (idiaoke).

**Stack:** a Python pipeline (AI + geometry) that runs entirely on your own GPU. Use it as a CLI or behind a small local FastAPI; the Laravel + web frontend in §6 is optional, only if you later want a browser UI.

**Local use → license is a non-issue.** Everything below picks the **best-quality** model for each stage regardless of license, since you're running it privately on your own machine. (If you ever distribute it commercially, revisit §10.)

**Status of the code in this doc:** the geometry stages (§5.1) have been run end-to-end and verified (valid 16-bit output, watertight STL). The GPU model calls (§5.2) use standard `diffusers` / `transformers` / `torch.hub` APIs — check the library version pins before running.

---

## 1. Goal & Scope

**In scope (MVP):**
- Upload one image → return one relief heightmap (16-bit PNG/TIFF) + one STL.
- Background auto-removed so the subject sits on a flat base plane.
- A few tuning knobs (relief depth, detail strength) with sane defaults.
- Runs in roughly 10–60s per image on a consumer GPU.

**Out of scope (later phases):**
- Toolpath / G-code generation (that's CAM — see §8 Phase 4).
- Fine-tuned, material-specific models (jade vs wood vs jewelry).
- Accounts, credits, payments (bolt on after the pipeline works).

---

## 2. How It Works (the core idea)

The mistake everyone makes first: running a depth-estimation model (Depth Anything) and calling the depth map a heightmap. **Depth ≠ relief.** A depth map encodes camera distance — it captures the silhouette but throws away surface detail, so feathers/folds/hair melt into blobs.

The detail that reads as *carved* lives in the **surface normals**, not in coarse depth. So the pipeline is **normal-driven**:

```
image
  └─> remove background ........... (subject mask + clean plane)
  └─> estimate surface normals .... (fine detail: feathers, folds)
  └─> [optional] estimate depth ... (global proportion)
  └─> integrate normals -> height . (surface-from-gradient)
  └─> bas-relief compression ...... (squash global depth, keep detail)  ← the secret sauce
  └─> enhance + flatten + 16-bit .. (CNC-ready heightmap)
  └─> heightmap -> STL ............ (CNC / 3D print)
```

Only **one** stage is real algorithm code you write (bas-relief compression). Everything else is a model you call or a repo you clone.

---

## 3. The Pipeline — stage → best model → VRAM

Best-quality pick per stage (license ignored — local use). Approx VRAM is at fp16, ~1–2 MP input.

| # | Stage | Best model (local) | Source | ~VRAM |
|---|-------|----------------------|--------|-------|
| 0 | Background removal | **BiRefNet** (or BiRefNet-HR for max res) | `ZhengPeng7/BiRefNet` (HF) | ~3–4 GB |
| 1 | Surface normals **(primary — best detail)** | **StableNormal** | `Stable-X/StableNormal` (torch.hub) | ~7–9 GB |
| 1 | Surface normals *(alt, diffusion)* | **Marigold-Normals v1-1** (full, ~10 steps) | `prs-eth/marigold-normals-v1-1` (HF) | ~8–10 GB |
| 1 | Surface normals *(clean-subject objects)* | **GeoWizard** object model | `lemonaddie/geowizard` (HF) | ~8–10 GB |
| 2 | Depth *(for global-form fusion)* | **Depth Anything V2-Large** | `depth-anything/Depth-Anything-V2-Large-hf` (HF) | ~4–6 GB |
| 3 | Normals → height | Poisson / Frankot-Chellappa | own code (§5.1) | CPU |
| 4 | Bas-relief compression | gradient attenuation + Poisson | own code (§5.1) | CPU |
| 5 | Enhance + 16-bit | numpy / OpenCV | own code (§5.1) | CPU |
| 6 | Heightmap → STL | **trimesh** | own code (§5.1) | CPU |

**Stack changes vs a commercial build:** only two. Marigold's full **v1-1** replaces the distilled LCM (sharper), and **Depth Anything V2-Large** is now fair game. StableNormal + BiRefNet were already the best picks.

**VRAM strategy:** run stages **sequentially and unload between them** (see §5.2 `unload_all`) so peak VRAM ≈ the single heaviest model (~8–10 GB), not the sum. On a ≥12 GB card you can keep them all resident; on 8 GB, unload between stages.

**Commercial-safe default set:** BiRefNet (MIT) + Marigold-Normals-LCM (Apache) + trimesh (MIT) → zero licensing ambiguity. Use StableNormal for best quality once you've confirmed its license terms for your use.

---

## 4. Python Stack — `requirements.txt`

```txt
# --- core geometry (CPU, always needed) ---
numpy
scipy
opencv-python-headless
Pillow
scikit-image
trimesh

# --- GPU inference ---
torch
torchvision
diffusers>=0.30
transformers>=4.44
huggingface_hub
accelerate
einops
# xformers        # optional: speeds up diffusion models on CUDA

# --- service layer ---
fastapi
uvicorn[standard]
python-multipart   # file uploads
pydantic
```

> GPU note: the normal/depth diffusion models want an NVIDIA GPU with ~8–12 GB VRAM. The geometry stages are CPU-only and fast.

---

## 5. Reference Implementation

Four files: `relief_core.py` (geometry), `models.py` (GPU inference), `pipeline.py` (orchestration), `service.py` (FastAPI).

### 5.1 `relief_core.py` — geometry (verified, runs as-is)

```python
"""
relief_core.py — CPU geometry stages of the bas-relief pipeline.
Normal integration, bas-relief compression, detail enhancement,
16-bit export, and STL export. No GPU / no models needed here.
"""
import numpy as np
import cv2
from scipy.fft import dctn, idctn
import trimesh


# ----- Poisson solver (Neumann/free BC via DCT) — reused twice -----
def solve_poisson_neumann(f):
    """Solve laplacian(u) = f with Neumann boundary conditions (DCT)."""
    M, N = f.shape
    i = np.arange(M).reshape(-1, 1)
    j = np.arange(N).reshape(1, -1)
    denom = (2 * np.cos(np.pi * i / M) - 2) + (2 * np.cos(np.pi * j / N) - 2)
    denom[0, 0] = 1.0                       # fix null-space (DC) term
    F = dctn(f, type=2, norm="ortho")
    U = F / denom
    U[0, 0] = 0.0
    return idctn(U, type=2, norm="ortho")


# ----- Stage 3: surface normals -> height field -----
def normal_to_gradients(normal_map, flip_y=False):
    """normal_map: HxWx3 float in [0,1]. Returns p=dz/dx, q=dz/dy."""
    n = normal_map.astype(np.float64) * 2.0 - 1.0
    nx, ny, nz = n[..., 0], n[..., 1], n[..., 2]
    if flip_y:                              # OpenGL vs DirectX green channel
        ny = -ny
    nz = np.clip(nz, 1e-6, None)
    return -nx / nz, -ny / nz


def integrate_normals(normal_map, flip_y=False):
    p, q = normal_to_gradients(normal_map, flip_y)
    div = np.gradient(p, axis=1) + np.gradient(q, axis=0)
    return solve_poisson_neumann(div)


# ----- Stage 4: bas-relief compression (THE secret sauce) -----
# Fattal-2002 / Weyrich-2007 style: attenuate large gradients (big depth
# jumps) while preserving/boosting small ones (fine detail), then re-integrate.
def bas_relief_compress(height, alpha=None, beta=0.55, detail_boost=1.0):
    gx = np.gradient(height, axis=1)
    gy = np.gradient(height, axis=0)
    mag = np.sqrt(gx ** 2 + gy ** 2) + 1e-8
    if alpha is None:                       # auto: fraction of mean gradient
        alpha = 0.6 * np.mean(mag)
    phi = (alpha / mag) * np.power(mag / alpha, beta) * detail_boost
    div = np.gradient(gx * phi, axis=1) + np.gradient(gy * phi, axis=0)
    return solve_poisson_neumann(div)


# ----- Stage 5: detail enhance + background flatten + 16-bit -----
def enhance_detail(height, sigma_space=12, detail_gain=1.4):
    h = height.astype(np.float32)
    h = (h - h.min()) / (h.max() - h.min() + 1e-8)
    base = cv2.bilateralFilter(h, d=-1, sigmaColor=0.08, sigmaSpace=sigma_space)
    return base + (h - base) * detail_gain  # boost the high-frequency layer


def flatten_background(height, mask, threshold=0.5):
    m = mask > threshold
    bg = np.percentile(height[~m], 50) if (~m).any() else height.min()
    height = height - bg
    height[~m] = 0.0
    return np.clip(height, 0, None)


def to_heightmap_16bit(height, invert=False):
    h = height.astype(np.float64)
    h = (h - h.min()) / (h.max() - h.min() + 1e-8)
    if invert:
        h = 1.0 - h
    return (h * 65535.0).astype(np.uint16)


# ----- Stage 6: heightmap -> STL -----
def heightmap_to_surface(height16, z_scale_mm=8.0, pixel_mm=0.1):
    """Open top-surface mesh — fine for CNC (CAM closes the model)."""
    h = height16.astype(np.float64) / 65535.0
    rows, cols = h.shape
    xv, yv = np.meshgrid(np.arange(cols) * pixel_mm, np.arange(rows) * pixel_mm)
    V = np.stack([xv.ravel(), yv.ravel(), (h * z_scale_mm).ravel()], 1)
    idx = np.arange(rows * cols).reshape(rows, cols)
    v00, v10 = idx[:-1, :-1].ravel(), idx[1:, :-1].ravel()
    v01, v11 = idx[:-1, 1:].ravel(), idx[1:, 1:].ravel()
    F = np.concatenate([np.stack([v00, v10, v11], 1),
                        np.stack([v00, v11, v01], 1)], 0)
    return trimesh.Trimesh(vertices=V, faces=F, process=False)


def heightmap_to_solid(height16, z_scale_mm=8.0, pixel_mm=0.1, base_mm=2.0):
    """Watertight solid (top + base + walls) — needed for 3D printing."""
    h = height16.astype(np.float64) / 65535.0
    rows, cols = h.shape
    xv, yv = np.meshgrid(np.arange(cols) * pixel_mm, np.arange(rows) * pixel_mm)
    N = rows * cols
    top = np.stack([xv.ravel(), yv.ravel(),
                    (h * z_scale_mm + base_mm).ravel()], 1)
    bot = np.stack([xv.ravel(), yv.ravel(), np.zeros(N)], 1)
    V = np.vstack([top, bot])
    idx, b = np.arange(N).reshape(rows, cols), np.arange(N).reshape(rows, cols) + N

    def grid(a, up=True):
        v00, v10 = a[:-1, :-1].ravel(), a[1:, :-1].ravel()
        v01, v11 = a[:-1, 1:].ravel(), a[1:, 1:].ravel()
        if up:
            return np.concatenate([np.stack([v00, v10, v11], 1),
                                   np.stack([v00, v11, v01], 1)], 0)
        return np.concatenate([np.stack([v00, v11, v10], 1),
                               np.stack([v00, v01, v11], 1)], 0)

    def wall(t, bt):
        return np.concatenate([np.stack([t[:-1], t[1:], bt[1:]], 1),
                               np.stack([t[:-1], bt[1:], bt[:-1]], 1)], 0)

    F = np.concatenate([
        grid(idx, True), grid(b, False),
        wall(idx[0, :], b[0, :]), wall(idx[-1, ::-1], b[-1, ::-1]),
        wall(idx[::-1, 0], b[::-1, 0]), wall(idx[:, -1], b[:, -1]),
    ], 0)
    m = trimesh.Trimesh(vertices=V, faces=F, process=True)
    trimesh.repair.fix_normals(m)
    return m
```

### 5.2 `models.py` — GPU inference (background removal, normals, depth)

```python
"""
models.py — model wrappers. Each loader is lazy + cached. For a low-VRAM
local GPU, call unload_all() between stages so peak VRAM ≈ the single
heaviest model instead of the sum.
"""
import functools
import gc
import numpy as np
import cv2
import torch
from PIL import Image

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def unload_all():
    """Free cached models + VRAM. Call between heavy stages on small GPUs."""
    for fn in (_birefnet, _stablenormal, _marigold_normals, _depth_pipe):
        fn.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ---------- Stage 0: background removal (BiRefNet, MIT) ----------
@functools.lru_cache(maxsize=1)
def _birefnet():
    from transformers import AutoModelForImageSegmentation
    m = AutoModelForImageSegmentation.from_pretrained(
        "ZhengPeng7/BiRefNet", trust_remote_code=True
    ).to(DEVICE).eval()
    return m


def remove_background(image: Image.Image) -> np.ndarray:
    """Return a soft foreground mask HxW in [0,1]."""
    from torchvision import transforms
    tf = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = tf(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        pred = _birefnet()(x)[-1].sigmoid().cpu()[0, 0].numpy()
    return cv2.resize(pred, image.size)  # back to (W,H)


# ---------- Stage 1: surface normals ----------
# Option A — StableNormal (best detail). Returns a PIL normal map.
@functools.lru_cache(maxsize=1)
def _stablenormal():
    return torch.hub.load("Stable-X/StableNormal", "StableNormal",
                          trust_repo=True)


def estimate_normals_stable(image: Image.Image) -> np.ndarray:
    normal_pil = _stablenormal()(image)
    return np.asarray(normal_pil).astype(np.float32) / 255.0  # HxWx3 [0,1]


# Option B — Marigold-Normals v1-1 (full quality, more steps = sharper).
@functools.lru_cache(maxsize=1)
def _marigold_normals():
    from diffusers import MarigoldNormalsPipeline
    return MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1",
        torch_dtype=torch.float16,
    ).to(DEVICE)


def estimate_normals_marigold(image: Image.Image) -> np.ndarray:
    out = _marigold_normals()(image, num_inference_steps=10, ensemble_size=5)
    n = np.asarray(out.prediction[0])          # HxWx3 in [-1,1]
    return (n + 1.0) / 2.0                       # -> [0,1]


# ---------- Stage 2 (optional): depth for global form ----------
@functools.lru_cache(maxsize=1)
def _depth_pipe():
    from transformers import pipeline
    return pipeline("depth-estimation",
                    model="depth-anything/Depth-Anything-V2-Large-hf",
                    device=0 if DEVICE == "cuda" else -1)


def estimate_depth(image: Image.Image) -> np.ndarray:
    d = np.asarray(_depth_pipe()(image)["depth"]).astype(np.float32)
    return (d - d.min()) / (d.max() - d.min() + 1e-8)  # HxW [0,1]
```

### 5.3 `pipeline.py` — orchestration

```python
"""
pipeline.py — single image in, relief heightmap + STL out.
"""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

import relief_core as rc
import models as M


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve
    pixel_mm: float = 0.1            # mm per pixel (controls plate size)
    normals: str = "stable"         # "stable" | "marigold"
    use_depth_fusion: bool = True   # blend global depth + normal detail
    compress_beta: float = 0.55     # lower = flatter relief
    detail_gain: float = 1.4        # higher = punchier detail
    flip_y: bool = False            # toggle if relief comes out inverted
    invert: bool = False            # toggle white<->black height convention
    make_solid: bool = False        # True = watertight (3D print), False = CNC


def _fuse_depth(height, depth, mask):
    """Low-frequency from depth, high-frequency from normal integration."""
    h = (height - height.min()) / (height.max() - height.min() + 1e-8)
    base = cv2.GaussianBlur(depth.astype(np.float32), (0, 0), sigmaX=8)
    detail = h - cv2.GaussianBlur(h.astype(np.float32), (0, 0), sigmaX=8)
    return base + detail


def generate_relief(image_path: str, out_dir: str,
                    params: ReliefParams = ReliefParams()):
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")

    # 0. subject mask
    mask = M.remove_background(image)

    # 1. surface normals
    if params.normals == "marigold":
        normal_map = M.estimate_normals_marigold(image)
    else:
        normal_map = M.estimate_normals_stable(image)

    # 3. integrate to a height field
    height = rc.integrate_normals(normal_map, flip_y=params.flip_y)

    # 2+. optional global-form fusion
    if params.use_depth_fusion:
        depth = M.estimate_depth(image)
        height = _fuse_depth(height, depth, mask)

    # 4. bas-relief compression
    height = rc.bas_relief_compress(height, beta=params.compress_beta)

    # 5. enhance + flatten + 16-bit
    height = rc.enhance_detail(height, detail_gain=params.detail_gain)
    height = rc.flatten_background(height, mask)
    height16 = rc.to_heightmap_16bit(height, invert=params.invert)

    png_path = out / "relief_heightmap.png"
    cv2.imwrite(str(png_path), height16)         # 16-bit PNG

    # 6. STL
    if params.make_solid:
        mesh = rc.heightmap_to_solid(height16, params.relief_depth_mm,
                                     params.pixel_mm)
    else:
        mesh = rc.heightmap_to_surface(height16, params.relief_depth_mm,
                                       params.pixel_mm)
    stl_path = out / "relief.stl"
    mesh.export(str(stl_path))

    return {"heightmap": str(png_path), "stl": str(stl_path)}
```

### 5.4 `service.py` — FastAPI endpoint

```python
"""
service.py — minimal inference API. Laravel calls POST /relief.
Run: uvicorn service:app --host 0.0.0.0 --port 8000
"""
import tempfile, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

from pipeline import generate_relief, ReliefParams

app = FastAPI(title="Relief Service")
OUT_ROOT = Path("/data/relief_jobs")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/relief")
async def relief(
    file: UploadFile = File(...),
    relief_depth_mm: float = Form(8.0),
    pixel_mm: float = Form(0.1),
    normals: str = Form("stable"),
    make_solid: bool = Form(False),
):
    job = str(uuid.uuid4())
    out_dir = OUT_ROOT / job
    out_dir.mkdir(parents=True, exist_ok=True)

    src = out_dir / f"src_{file.filename}"
    src.write_bytes(await file.read())

    params = ReliefParams(relief_depth_mm=relief_depth_mm, pixel_mm=pixel_mm,
                          normals=normals, make_solid=make_solid)
    try:
        result = generate_relief(str(src), str(out_dir), params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"job": job, "error": str(e)})

    return {"job": job, **result}
```

---

## 6. System Architecture

```
┌────────────┐   upload    ┌─────────────────┐   enqueue   ┌──────────────────┐
│  Frontend  │ ──────────▶ │   Laravel API   │ ──────────▶ │  Queue (Horizon) │
│ Next.js /  │             │  - store upload │             └────────┬─────────┘
│ React Native│            │  - create job   │                      │ HTTP
└─────▲──────┘             │  - serve result │             ┌────────▼─────────┐
      │  poll / download   └────────▲────────┘             │  Python service  │
      │                             │                      │  (FastAPI + GPU) │
      │                             │  save png+stl        │  models.py       │
      │                             └──────────────────────│  pipeline.py     │
      │                                                     └────────┬─────────┘
      │                  ┌──────────────────────────┐                │
      └──────────────────│  Object storage (S3 /    │◀───────────────┘
                         │  DO Spaces): src+outputs │
                         └──────────────────────────┘
```

**Responsibilities**
- **Frontend** — image upload, job-status polling, preview + download of heightmap/STL.
- **Laravel** — auth, upload storage, `relief_jobs` table, Horizon queue job that POSTs the image to the Python service and saves the returned files. Credits/membership live here later.
- **Python service** — the only non-Laravel piece. Stateless; does the GPU work.
- **Storage** — S3 / DigitalOcean Spaces for source images and outputs.

**Laravel job (sketch):**
```php
// app/Jobs/GenerateRelief.php
public function handle(): void
{
    $resp = Http::timeout(180)
        ->attach('file', Storage::get($this->job->src_path), 'src.png')
        ->post(config('services.relief.url').'/relief', [
            'relief_depth_mm' => $this->job->depth_mm,
            'pixel_mm'        => $this->job->pixel_mm,
            'make_solid'      => $this->job->make_solid,
        ])->throw()->json();

    // download + store outputs, mark job complete
    $this->job->update([
        'status'        => 'done',
        'heightmap_path'=> $this->store($resp['heightmap']),
        'stl_path'      => $this->store($resp['stl']),
    ]);
}
```

---

## 7. Running Locally

Everything runs on your own GPU — no cloud, no per-image cost.

**Setup**
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# PyTorch: install the CUDA build matching your driver from pytorch.org
```

**Two ways to run**
1. **CLI / script** — import `generate_relief` and point it at an image:
   ```python
   from pipeline import generate_relief, ReliefParams
   generate_relief("input.jpg", "out/", ReliefParams(normals="stable"))
   ```
2. **Local FastAPI** — `uvicorn service:app --port 8000`, then POST images from a script, Postman, or a small local web page. (Skip Laravel entirely unless you want the §6 browser UI.)

**First run** downloads model weights from HuggingFace (a few GB total) into your local HF cache; later runs are offline-fast.

**GPU sizing**
| Your VRAM | How to run |
|-----------|-----------|
| ≥ 16 GB | Keep all models resident; `use_depth_fusion=True`; fastest. |
| 10–12 GB | Fine; call `models.unload_all()` between stages on tight runs. |
| 8 GB | Unload between stages; run Marigold at lower res or skip depth fusion. |
| < 8 GB | Use Depth-Anything-V2-**Base** and run normals at reduced resolution, then upscale the heightmap. |

---

## 8. Build Roadmap

**Phase 0 — Prototype the quality (days, no app).**
Wire the pipeline in **ComfyUI** to eyeball output on real images before committing to a service. Useful nodes: `ComfyUI-LBM` (depth+normal), `ComfyUI-Geowizard`, `DepthToNormalMap`, and `ComfyUI-Depth2Mesh` (heightmap→STL). Add one custom Python node for the §5.1 `bas_relief_compress`. Goal: confirm the relief looks carved, find good default knobs.

**Phase 1 — The pipeline running locally (the core).**
Get `relief_core.py` + `models.py` + `pipeline.py` running on your GPU. Test on 20–30 varied images (portraits, animals, ornaments). Lock in good default knobs for your typical subjects.

**Phase 2 — A local UI (optional).**
Either a tiny local web page hitting `service.py`, or the full Laravel + frontend from §6 if you want upload history and a polished interface. Skip if the CLI is enough.

**Phase 3 — Quality & control.**
Depth fusion on by default, per-material presets (jade/wood/jewelry depth + detail settings), an interactive relief-depth slider, optional 4K upscaling of the input (Real-ESRGAN/SUPIR) before processing.

**Phase 4 — The hard moat (ongoing).**
- **Fine-tune the normal model** on a relief/sculpture dataset → biggest single quality jump (this is what the Chinese players actually did).
- **Toolpath / G-code**: integrate CAM (Vectric Aspire relief module, or open-source CAM) so output is machine-ready, not just an STL.

---

## 9. Tuning Guide (the knobs that matter)

| Knob (in `ReliefParams`) | Effect | If output looks wrong |
|------|--------|----------------------|
| `compress_beta` | global depth compression | relief too "tall"/distorted → lower it; too flat → raise it |
| `detail_gain` | high-frequency punch | mushy/soft → raise; noisy/harsh → lower |
| `relief_depth_mm` | physical carve depth | set to your stock/material limit |
| `pixel_mm` | physical plate size & resolution | controls final dimensions |
| `flip_y` | normal green-channel convention | relief inverted/embossed-inward → toggle |
| `invert` | white=high vs black=high | if your CAM expects the opposite, toggle |

Always export **16-bit** — 8-bit causes visible stepping ("terracing") on the carved surface.

---

## 10. Licensing (only if you ever distribute)

For your **local/private use this section doesn't apply** — run whatever's best. It matters only if you later ship this commercially:

- **Safe to ship as-is:** BiRefNet (MIT), Marigold-Normals (the Apache-2.0 `-lcm-v0-1` checkpoint), trimesh (MIT), and all the §5.1 geometry (public-domain math).
- **Would need swapping:** StableNormal, GeoWizard, Depth Anything V2 *Large* — several research checkpoints are **CC-BY-NC**. For a paid product, switch normals to the Apache Marigold-LCM and depth to Depth-Anything **Small/Base**.
- The bas-relief algorithm itself is unencumbered.

---

## 11. Closing the Quality Gap

A naive version of this pipeline produces a recognizable carved relief immediately. The distance to Sculptok/idiaoke's *exact* polish comes from three things, in order of payoff:

1. **Fine-tuned normal estimation on relief data** — generic StableNormal is trained on indoor scenes; tuned on busts/sculptures/ornaments it gets dramatically cleaner on your actual subjects. **This is the real moat.**
2. **Per-material compression presets** — jade, wood, and jewelry have different depth budgets; hand-tuned `beta`/`detail_gain` per material.
3. **Clean input generation** — if you later add AI image generation (FLUX/Qwen-Image), bias it toward high-contrast, single-subject, clutter-free images so the pipeline behaves.

None of these is a missing magic model — they're **data and tuning**. The algorithm is in this document.

---

## 12. Repos & Models — quick reference

**Models (HuggingFace / hub)**
- `ZhengPeng7/BiRefNet` — background removal (MIT)
- `Stable-X/StableNormal` — surface normals, best detail
- `prs-eth/marigold-normals-v1-1` — surface normals (full quality); `-lcm-v0-1` is the fast Apache variant
- `lemonaddie/geowizard` — normals/depth, strong object model
- `depth-anything/Depth-Anything-V2-Large-hf` — depth

**Repos (geometry / glue)**
- `HugoTini/NormalHeight` — Frankot-Chellappa normal→height reference
- `Sajjad-Mahmoudi/Photometric-Stereo` — clean `frankotchellappa()` function
- `timothywong731/ComfyUI-Depth2Mesh` — heightmap→STL for CNC
- `1038lab/ComfyUI-LBM` — depth+normal nodes for the Phase-0 prototype

**Key paper (Stage 4 math)**
- Ji, Sun, Ma — *Normal Image Manipulation for Bas-relief Generation* (arXiv:1804.06092)
- Weyrich et al. 2007 / Fattal et al. 2002 — gradient-domain compression
