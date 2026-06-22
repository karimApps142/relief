# Part 02 — Backend switch (`backends.py`): lite + full

**Goal:** create `backends.py`, the pluggable inference layer that makes Mac development
possible. `LiteBackend` derives crude normals from image luminance with **zero models** (pure
CPU/OpenCV); `FullBackend` wraps the real GPU models but **imports them lazily** so merely
importing `backends.py` on the Mac never pulls in torch.

**Runs on:** 🍎 Mac (you build + test `LiteBackend` here; `FullBackend` is just wired, exercised
later on Windows)

**Prerequisites:** Part 00 (scaffold), Part 01 (`relief_core.py`).

**Files created:** `backends.py`

---

## The big idea (the single most important design point)

`FullBackend.__init__` does `import models` **inside the method**, not at module top. That means:

- On the Mac, `get_backend("lite")` → `LiteBackend()` → `models` is never imported → torch is
  never touched. You can `import backends` with only the light `requirements.txt` installed.
- On Windows, `get_backend("full")` → `FullBackend()` → `import models` runs → torch + real
  models load.

Select via env var `RELIEF_BACKEND=lite|full` (default `lite`), or pass `backend=` explicitly.
`get_backend` also resolves **`auto`** centrally (→ `full` if `model_manager.models_present()`
else `lite`), so every direct caller — the Gradio app (Part 09), scripts — gets the right backend,
not just the `/relief` HTTP handler. (Part 05's handler still resolves `auto` itself so its JSON
response can echo the concrete backend that ran.)

> Note: the original plan only resolved `auto` in the API handler; centralizing it here fixes a
> gap where `generate_relief(..., backend="auto")` called directly would always fall through to
> lite. The `import model_manager` stays inside the `auto` branch so the lite path pulls nothing
> extra.

---

## The code

### `backends.py`

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
    if name == "auto":                          # full if weights present, else lite
        import model_manager                    # light dep (huggingface_hub), no torch
        name = "full" if model_manager.models_present() else "lite"
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

> `FullBackend` references `models.py`, which you don't create until **Part 06**. That's fine —
> as long as you never instantiate `FullBackend()` on the Mac, the missing `models` import is
> never triggered. `LiteBackend` has no such dependency.

---

## Steps

1. Create `backends.py` with the code above.
2. Confirm the lite path imports clean and produces a normal map, with no torch installed:

```python
from PIL import Image
import numpy as np
from backends import get_backend

be = get_backend("lite")
print(be.name)                                   # "lite"
img = Image.new("RGB", (128, 96), (120, 120, 120))
nm = be.estimate_normals(img)
print(nm.shape, nm.dtype, nm.min(), nm.max())    # (96,128,3) float ~[0,1]
print(be.remove_background(img).shape)           # (96,128)
print(be.estimate_depth(img))                    # None
```

---

## Verify

```bash
RELIEF_BACKEND=lite python -c "import backends; print('ok, no torch needed')"
python -c "import sys; import backends; print('torch' in sys.modules)"   # expect: False
```
- Importing `backends` succeeds with only the light requirements installed.
- `torch` is **not** in `sys.modules` after `import backends` (lazy import confirmed).
- `LiteBackend.estimate_normals` returns an `HxWx3` array in `[0,1]`.

## Done when

- [ ] `backends.py` exists with `get_backend`, `LiteBackend`, `FullBackend`.
- [ ] `import backends` works on the Mac with no torch.
- [ ] `torch` does not appear in `sys.modules` after import (lazy `import models` confirmed).
- [ ] `LiteBackend` returns normals (`[0,1]`), a full-foreground mask, and `None` depth.

## Source

Handover §1 (the backend switch, lazy import design).
