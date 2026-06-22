# Dev Workflow & Handover — MacBook (build/test) → Windows RTX 3060 (real run)

Companion to `cnc-bas-relief-build-plan.md`. This covers the part you asked about: develop and test **all the logic + UI** on your MacBook with **no heavy models**, then hand the code to the Windows machine (RTX 3060 **12 GB**) where the real models actually run.

The trick is a **backend switch**:

| Backend | Where | Models? | torch/CUDA? | Quality | Purpose |
|---------|-------|---------|-------------|---------|---------|
| **`lite`** | MacBook (or anything) | **none** | **not installed** | crude | test pipeline + UI + STL with zero downloads |
| **`full`** | Windows RTX 3060 | downloaded on demand | installed | production | the real relief |

The `lite` path was **verified end-to-end on CPU**: image → normals (from luminance, no model) → integrate → bas-relief compress → 16-bit heightmap → STL. So on your Mac you can exercise the *entire* program — upload, the whole geometry pipeline, file output, the API — and only the neural quality is stubbed. Everything else is the real code.

> Your RTX 3060 is the 192-bit / **12 GB** model. That's comfortable: StableNormal + depth fusion fit; only unload between stages on tight runs.

---

## 1. The backend switch — `backends.py`

The key design point: **`FullBackend` imports `models` lazily**, so importing `backends.py` on the Mac never pulls in torch. The Mac only ever touches `LiteBackend`.

```python
"""
backends.py — pluggable inference backend.
  lite : pure CPU, NO models. Normals derived from image luminance.
         Runs on the MacBook. Crude quality — for testing the full
         pipeline + UI without downloading anything.
  full : real models (BiRefNet + StableNormal/Marigold + Depth Anything).
         Needs an NVIDIA GPU, requirements-gpu.txt, and downloaded weights.
Select with env var RELIEF_BACKEND=lite|full, or pass backend= explicitly.
"""
import os
import numpy as np
import cv2
from PIL import Image


def get_backend(name=None):
    name = name or os.environ.get("RELIEF_BACKEND", "lite")
    return FullBackend() if name == "full" else LiteBackend()


# ---------------- LITE (CPU, no models, Mac-friendly) ----------------
class LiteBackend:
    name = "lite"

    def remove_background(self, image: Image.Image) -> np.ndarray:
        # no real segmentation in lite mode: whole image is foreground
        return np.ones((image.height, image.width), np.float32)

    def estimate_normals(self, image: Image.Image, strength=2.5, **_) -> np.ndarray:
        rgb = np.asarray(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        gray = cv2.bilateralFilter(gray, d=-1, sigmaColor=0.1, sigmaSpace=5)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=5)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
        nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(gray)
        n = np.stack([nx, ny, nz], -1)
        n /= (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8)
        return (n + 1.0) / 2.0                      # HxWx3 in [0,1]

    def estimate_depth(self, image: Image.Image):
        return None                                 # no depth fusion in lite mode


# ---------------- FULL (GPU, real models) ----------------
class FullBackend:
    name = "full"

    def __init__(self):
        import models                               # <-- lazy: only imported here
        self._m = models

    def remove_background(self, image):
        return self._m.remove_background(image)

    def estimate_normals(self, image, which="stable", **_):
        if which == "marigold":
            return self._m.estimate_normals_marigold(image)
        return self._m.estimate_normals_stable(image)

    def estimate_depth(self, image):
        return self._m.estimate_depth(image)
```

**`pipeline.py` becomes backend-aware** (one new argument; the rest is unchanged from the main plan):

```python
def generate_relief(image_path, out_dir, params, backend=None):
    from backends import get_backend
    be = get_backend(backend or getattr(params, "backend", None))

    image = Image.open(image_path).convert("RGB")
    mask = be.remove_background(image)
    normal_map = be.estimate_normals(image, which=params.normals)

    height = rc.integrate_normals(normal_map, flip_y=params.flip_y)

    depth = be.estimate_depth(image)                # None in lite mode
    if params.use_depth_fusion and depth is not None:
        height = _fuse_depth(height, depth, mask)

    height = rc.bas_relief_compress(height, beta=params.compress_beta)
    height = rc.enhance_detail(height, detail_gain=params.detail_gain)
    height = rc.flatten_background(height, mask)
    height16 = rc.to_heightmap_16bit(height, invert=params.invert)
    # ... save PNG + STL exactly as before ...
```

Mac: `RELIEF_BACKEND=lite` → lite normals, `depth=None`, fusion skipped → you get a (crude) relief and a valid STL.
Windows: `RELIEF_BACKEND=full` → real models.

---

## 2. The "download models later" option — `model_manager.py`

Weights are **never** in the repo. The app ships able to run in `lite` mode immediately; a **Download Models** button pulls the weights on the Windows box, after which it switches to `full`.

```python
"""
model_manager.py — check whether heavy weights are present, and download
them on demand (the "Download Models" button). Only meaningful on the GPU box.
"""
from huggingface_hub import snapshot_download

HF_REPOS = {
    "birefnet":         "ZhengPeng7/BiRefNet",
    "marigold_normals": "prs-eth/marigold-normals-v1-1",
    "depth_anything":   "depth-anything/Depth-Anything-V2-Large-hf",
}
# StableNormal loads via torch.hub and downloads on first inference call.


def models_present() -> bool:
    """True only if every repo is fully in the local HF cache."""
    for repo in HF_REPOS.values():
        try:
            snapshot_download(repo, local_files_only=True)
        except Exception:
            return False
    return True


def download_models(progress=print):
    for name, repo in HF_REPOS.items():
        progress(f"downloading {name} ({repo}) ...")
        snapshot_download(repo)
    try:                                            # warm StableNormal weights
        import torch
        torch.hub.load("Stable-X/StableNormal", "StableNormal", trust_repo=True)
    except Exception as e:
        progress(f"stablenormal warm skipped ({e}) — fine if using marigold")
    progress("done")
```

**Wire it into `service.py`** so the UI can trigger + poll it, and `/relief` auto-picks the backend:

```python
from fastapi import BackgroundTasks, Form
import model_manager

_dl = {"running": False, "log": []}

@app.get("/models/status")
def models_status():
    return {"installed": model_manager.models_present(),
            "downloading": _dl["running"], "log": _dl["log"][-20:]}

def _run_download():
    _dl.update(running=True, log=[])
    try:
        model_manager.download_models(lambda m: _dl["log"].append(m))
    finally:
        _dl["running"] = False

@app.post("/models/download")
def models_download(bg: BackgroundTasks):
    if not _dl["running"]:
        bg.add_task(_run_download)
    return {"started": True}

# in the /relief handler, resolve "auto" -> full if installed, else lite:
#   if backend == "auto":
#       backend = "full" if model_manager.models_present() else "lite"
```

**UI behavior (any frontend — local web page, Laravel, RN):**
1. On load, call `GET /models/status`.
2. If `installed=false`, show a **Download Models** button + a "running in preview/lite mode" badge.
3. Button → `POST /models/download`, then poll `GET /models/status` for the log/progress until `installed=true`.
4. Once installed, relief requests use the `full` backend automatically.

On the Mac you simply never press the button → it stays in `lite` → everything is testable.

---

## 3. Repo structure (what you push to GitHub)

```
relief/
├── relief_core.py         # CPU geometry — runs everywhere (verified)
├── backends.py            # lite (Mac) + full (GPU); full imports models lazily
├── models.py              # real model wrappers — only used by FullBackend
├── model_manager.py       # check + download weights (the UI button)
├── pipeline.py            # backend-aware orchestration
├── service.py             # FastAPI: /relief + /models/status + /models/download
├── requirements.txt       # LIGHT deps — installs on Mac, NO torch
├── requirements-gpu.txt   # torch / diffusers / transformers — GPU box only
├── Dockerfile             # GPU image for Windows / other machines
├── .dockerignore
├── .gitignore
└── README.md
```

**`requirements.txt`** (light — this is all the Mac installs):
```txt
numpy
scipy
opencv-python-headless
Pillow
scikit-image
trimesh
fastapi
uvicorn[standard]
python-multipart
pydantic
huggingface_hub          # for the download manager; pulls no torch by itself
```

**`requirements-gpu.txt`** (Windows / NVIDIA box only, installed *after* the light file):
```txt
--extra-index-url https://download.pytorch.org/whl/cu121
torch
torchvision
diffusers>=0.30
transformers>=4.44
accelerate
einops
```

**`.gitignore`** (weights live in the HF cache, never in git):
```gitignore
.venv/
venv/
__pycache__/
*.pyc
.DS_Store
/data/
/outputs/
# HF model cache lives in ~/.cache/huggingface — outside the repo by design
```

---

## 4. GitHub workflow

```bash
# ===== MacBook (build + test logic/UI, lite mode) =====
git init
git add .
git commit -m "relief pipeline + lite/full backends"
git branch -M main
git remote add origin git@github.com:karimapps142/relief.git
git push -u origin main

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt           # light only, no torch
RELIEF_BACKEND=lite uvicorn service:app --reload
# upload an image -> get a crude relief + STL. Proves the whole flow.
```

```powershell
# ===== Windows RTX 3060 (real run) =====
git clone git@github.com:karimapps142/relief.git
cd relief
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-gpu.txt       # torch+cuda, diffusers, transformers
uvicorn service:app --host 0.0.0.0 --port 8000
# then hit the "Download Models" button (POST /models/download) once.
# RELIEF_BACKEND=auto -> switches to full once weights are present.
```

Day-to-day: edit on Mac → `git push` → on Windows `git pull` → restart the service. Code only; the multi-GB weights stay in each machine's HF cache and are downloaded once.

---

## 5. Docker — should you use it?

You're distributing to **several Windows 10 machines**, so the honest answer is **yes, eventually** — Docker is the right tool for reproducing the messy `torch`/`diffusers`/CUDA stack across machines. But two caveats:

- **Mac: don't bother.** Docker on Apple Silicon can't reach an NVIDIA GPU, and you don't need a container for CPU/lite testing. Just the venv above.
- **First Windows box: go native first.** Get it working with the plain venv + the `cu121` torch wheel before containerizing — it's far easier to debug. You do **not** need conda; the PyTorch wheels bundle their own CUDA runtime, so `pip` in a venv is enough on Windows. Containerize *after* it works, for portability to the other machines.

**Important:** Docker removes the *Python-dependency* pain, not the *GPU-driver* setup. Each Windows machine still needs the driver + WSL2 plumbing below.

### Windows 10 + Docker + GPU prerequisites
1. Latest NVIDIA driver (Game Ready or Studio — WSL2 CUDA support is built in).
2. **WSL2** enabled, with a Linux distro installed.
3. **Docker Desktop** using the **WSL2 backend**.
4. NVIDIA GPU support (recent Docker Desktop wires this through WSL2 automatically).

Verify the GPU is visible to Docker:
```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
# should list your RTX 3060
```

### `Dockerfile` (GPU image)
```dockerfile
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
        python3 python3-pip git libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-gpu.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt -r requirements-gpu.txt
COPY . .
ENV RELIEF_BACKEND=auto
EXPOSE 8000
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
```
> `libgl1` + `libglib2.0-0` are required by OpenCV in a slim image.

### `.dockerignore`
```gitignore
.venv/
venv/
__pycache__/
.git/
data/
outputs/
```

### Build & run (on the Windows box, inside WSL2/Docker)
```bash
docker build -t relief-gpu .
docker run --gpus all -p 8000:8000 \
  -v hf_cache:/root/.cache/huggingface \
  relief-gpu
```
The `-v hf_cache:...` volume **persists the downloaded weights** across container restarts — without it, every `docker run` re-downloads several GB. Press **Download Models** once; the volume keeps them.

---

## 6. "What runs where" cheat-sheet

| | MacBook (dev) | Windows RTX 3060 (real) |
|---|---|---|
| Install | `requirements.txt` | `requirements.txt` + `requirements-gpu.txt` |
| torch / CUDA | not installed | installed (cu121 wheel) |
| Model weights | none | downloaded on demand (HF cache) |
| Backend | `lite` (CPU) | `full` (GPU), `auto` resolves to it |
| Docker | no | optional now, recommended for multi-machine |
| You're testing | UI, pipeline, geometry, STL, the API | real relief quality |
| Verified | ✅ full pipeline runs, 0 models | run the real models here |

---

## 7. Suggested order

1. **Mac**: build `backends.py` + `model_manager.py`, wire the `/models/*` endpoints + the Download button into your UI. Run everything in `lite` mode — confirm upload → relief → STL → download all work and the UI behaves.
2. **Push to GitHub.**
3. **Windows (native)**: clone, install both requirements, run, press Download Models, confirm real output on the 3060. Tune the §9 knobs from the main plan for your subjects.
4. **Dockerize** once native works, then deploy the image to the other Windows machines (each needs the driver + WSL2 once).
