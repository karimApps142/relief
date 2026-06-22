# Part 03 — Orchestration (`pipeline.py`), backend-aware

**Goal:** create `pipeline.py` — the single function that takes one image in and writes one
relief heightmap (16-bit PNG) + one STL out. It wires together the geometry from Part 01 and the
backend from Part 02, so the **same code path runs lite on the Mac and full on Windows**. After
this part you can produce a (crude but real) relief end-to-end on the Mac.

**Runs on:** 🍎 Mac (lite end-to-end) — and unchanged on 🪟 Windows (full)

**Prerequisites:** Part 01 (`relief_core.py`), Part 02 (`backends.py`).

**Files created:** `pipeline.py`

---

## The big idea

This is the orchestration from plan §5.3, made backend-aware per handover §1. The one structural
change vs the plan's original: it asks a **backend** for the mask / normals / depth instead of
calling `models` directly. In lite mode `estimate_depth` returns `None`, so depth fusion is
skipped automatically. Everything after the backend hand-off — integrate → compress → enhance →
flatten → 16-bit → STL — is the verified Part 01 geometry, identical in both modes.

---

## The code

### `pipeline.py`

```python
"""
pipeline.py — single image in, relief heightmap + STL out. Backend-aware:
lite (Mac, no models) and full (GPU) run the exact same geometry path.
"""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

import relief_core as rc


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve
    pixel_mm: float = 0.1            # mm per pixel (controls plate size)
    normals: str = "stable"         # "stable" | "marigold" (full mode only)
    use_depth_fusion: bool = True   # blend global depth + normal detail
    compress_beta: float = 0.55     # lower = flatter relief
    detail_gain: float = 1.4        # higher = punchier detail
    flip_y: bool = False            # toggle if relief comes out inverted
    invert: bool = False            # toggle white<->black height convention
    make_solid: bool = False        # True = watertight (3D print), False = CNC
    backend: str = None             # "lite" | "full" | "auto" | None (env default)


def _fuse_depth(height, depth, mask):
    """Low-frequency from depth, high-frequency from normal integration."""
    h = (height - height.min()) / (height.max() - height.min() + 1e-8)
    base = cv2.GaussianBlur(depth.astype(np.float32), (0, 0), sigmaX=8)
    detail = h - cv2.GaussianBlur(h.astype(np.float32), (0, 0), sigmaX=8)
    return base + detail


def generate_relief(image_path, out_dir, params: ReliefParams = ReliefParams(),
                    backend=None):
    from backends import get_backend
    be = get_backend(backend or getattr(params, "backend", None))

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")

    # 0. subject mask
    mask = be.remove_background(image)

    # 1. surface normals
    normal_map = be.estimate_normals(image, which=params.normals)

    # 3. integrate to a height field
    height = rc.integrate_normals(normal_map, flip_y=params.flip_y)

    # 2+. optional global-form fusion (depth is None in lite mode -> skipped)
    depth = be.estimate_depth(image)
    if params.use_depth_fusion and depth is not None:
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

> **Note vs the plan:** plan §5.3 imported `models` directly and hard-coded the model calls. This
> backend-aware version (handover §1) replaces those with `be.remove_background` /
> `be.estimate_normals` / `be.estimate_depth`. The `backend` field was added to `ReliefParams`
> so a request can pin a backend; otherwise the `RELIEF_BACKEND` env var decides.

---

## Steps

1. Create `pipeline.py` with the code above.
2. Run it end-to-end in lite mode on any photo (a portrait or an ornament works well):

```bash
RELIEF_BACKEND=lite python -c "
from pipeline import generate_relief, ReliefParams
print(generate_relief('input.jpg', 'out/', ReliefParams(make_solid=True)))
"
```

---

## Verify

- Console prints `{'heightmap': 'out/relief_heightmap.png', 'stl': 'out/relief.stl'}`.
- `out/relief_heightmap.png` is **16-bit** and shows a recognizable (crude) relief of the
  subject.
- `out/relief.stl` opens in an STL viewer; with `make_solid=True` it is watertight.
- Quality is intentionally rough — lite uses luminance-derived normals. Real quality comes on
  Windows (Parts 06–07). The point here is that the **whole flow works**.

## Done when

- [ ] `pipeline.py` exists with `ReliefParams` (incl. `backend` field), `_fuse_depth`,
      `generate_relief`.
- [ ] `RELIEF_BACKEND=lite generate_relief(...)` returns the dict and writes both files.
- [ ] 16-bit PNG + valid STL produced on the Mac with **no** models.
- [ ] Depth fusion is silently skipped in lite mode (no crash from `depth=None`).

## Source

Plan §5.3 (`pipeline.py`, `ReliefParams`, `_fuse_depth`) reconciled with handover §1
(backend-aware `generate_relief`).
