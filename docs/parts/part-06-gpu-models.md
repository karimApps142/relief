# Part 06 — GPU model wrappers (`models.py`)

**Goal:** create `models.py`, the real GPU inference wrappers that `FullBackend` calls:
background removal (BiRefNet), surface normals (StableNormal or Marigold-v1-1), and depth
(Depth-Anything-V2-Large). Each loader is lazy + cached, with `unload_all()` to free VRAM
between stages on tight runs. **This is the first part that needs the GPU box.**

**Runs on:** 🪟 Windows 11 (RTX 3060, 12 GB) — needs `requirements-gpu.txt` installed

**Prerequisites:** Parts 00–05 on the repo (pulled to Windows), and torch/CUDA installed
(`requirements-gpu.txt`). Part 02 `FullBackend` expects exactly the function names defined here.

**Files:** `models.py` (new). `requirements-gpu.txt` already created in Part 00 — confirm it's
present.

---

## The big idea

This is the only torch-dependent module. `FullBackend.__init__` (Part 02) does `import models`
lazily, so this file is never touched on the Mac. Each model loader is wrapped in
`functools.lru_cache(maxsize=1)` (load once, reuse). On a 12 GB card you can keep all models
resident; `unload_all()` exists for tight runs — it frees the caches so peak VRAM ≈ the single
heaviest model (~8–10 GB) instead of the sum.

**Pipeline stage → model → VRAM (plan §3):**

| Stage | Model (local) | Source | ~VRAM |
|-------|---------------|--------|-------|
| Background removal | BiRefNet | `ZhengPeng7/BiRefNet` | ~3–4 GB |
| Normals (primary) | StableNormal | `Stable-X/StableNormal` (torch.hub) | ~7–9 GB |
| Normals (alt, diffusion) | Marigold-Normals v1-1 | `prs-eth/marigold-normals-v1-1` | ~8–10 GB |
| Depth (global form) | Depth Anything V2-Large | `depth-anything/Depth-Anything-V2-Large-hf` | ~4–6 GB |

> Your 3060 is the **12 GB** model — StableNormal + depth fusion fit; only unload between stages
> on tight runs.

---

## The code

### `models.py`

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

> These wrappers use standard `diffusers` / `transformers` / `torch.hub` APIs. **Check the
> library version pins before running** (plan note) — `diffusers>=0.30`, `transformers>=4.44`.
> `MarigoldNormalsPipeline` requires a recent `diffusers`; if import fails, bump it.

### `requirements-gpu.txt` (from Part 00 — confirm present)

```txt
--extra-index-url https://download.pytorch.org/whl/cu121
torch
torchvision
diffusers>=0.30
transformers>=4.44
accelerate
einops
```

---

## Steps (on the Windows box)

```powershell
# in the cloned repo, venv already created (see Part 07)
pip install -r requirements.txt
pip install -r requirements-gpu.txt          # cu121 torch wheel + diffusers/transformers
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# expect: a version + True
```

Then create `models.py` and confirm it imports:

```powershell
python -c "import models; print('DEVICE =', models.DEVICE)"
# expect: DEVICE = cuda
```

> Importing `models` does **not** download weights — the lazy `lru_cache` loaders only fire on
> first inference. Weight download is the **Download Models** step in Part 07.

---

## Verify

- `torch.cuda.is_available()` is `True` on the 3060.
- `import models` succeeds and `models.DEVICE == "cuda"`.
- The four function names match exactly what `FullBackend` calls (Part 02): `remove_background`,
  `estimate_normals_stable`, `estimate_normals_marigold`, `estimate_depth`, plus `unload_all`.

## Done when

- [ ] `requirements-gpu.txt` installed; `torch.cuda.is_available()` is `True`.
- [ ] `models.py` exists with all loaders + `unload_all`.
- [ ] `import models` works and reports `DEVICE = cuda`.
- [ ] Function names line up with `FullBackend` (no rename drift).

## Source

Plan §5.2 (`models.py`), §3 (stage→model→VRAM table), and §4 / handover §3 (`requirements-gpu.txt`).
Full end-to-end real run is Part 07.
