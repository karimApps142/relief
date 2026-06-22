# Part 01 — CPU geometry core (`relief_core.py`)

**Goal:** create `relief_core.py`, the **only hand-written algorithm** in the whole project:
normal→height integration, the bas-relief compression "secret sauce", detail enhancement,
16-bit export, and STL export. Pure CPU/numpy — runs identically on Mac and Windows. This code
is already verified end-to-end in the plan (valid 16-bit output, watertight STL), so it's the
**lowest-risk** part.

**Runs on:** 🍎 Mac + 🪟 Windows (CPU only — no GPU, no models)

**Prerequisites:** Part 00 (scaffold + light requirements installed).

**Files created:** `relief_core.py`

---

## The big idea

Depth ≠ relief. The carved-looking detail (feathers, folds, hair) lives in **surface normals**,
not coarse depth. So the pipeline integrates normals → a height field, then applies
**gradient-domain bas-relief compression** (Fattal-2002 / Weyrich-2007 style): attenuate large
gradients (big depth jumps) while preserving/boosting small ones (fine detail), then
re-integrate. The Poisson solver (Neumann BC via DCT) is reused twice — once to integrate
normals, once after compression.

Everything in this file is public-domain math; no licensing concerns.

---

## The code

### `relief_core.py`

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

---

## Steps

1. Create `relief_core.py` with the code above.
2. Smoke-test it standalone with a synthetic normal map (no models needed) — paste this into a
   scratch file or a Python REPL:

```python
import numpy as np, cv2
import relief_core as rc

# a fake "bump": a smooth hemisphere normal map, HxWx3 in [0,1]
H = W = 256
yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
cx, cy, r = W / 2, H / 2, 90
dx, dy = (xx - cx) / r, (yy - cy) / r
zz = np.sqrt(np.clip(1 - dx**2 - dy**2, 0, 1))
n = np.stack([-dx, -dy, np.maximum(zz, 1e-3)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
normal_map = ((n + 1) / 2).astype(np.float32)
mask = (dx**2 + dy**2 <= 1).astype(np.float32)

height = rc.integrate_normals(normal_map)
height = rc.bas_relief_compress(height, beta=0.55)
height = rc.enhance_detail(height, detail_gain=1.4)
height = rc.flatten_background(height, mask)
h16 = rc.to_heightmap_16bit(height)
cv2.imwrite("test_relief.png", h16)

solid = rc.heightmap_to_solid(h16, z_scale_mm=8.0, pixel_mm=0.1)
solid.export("test_relief.stl")
print("16-bit?", h16.dtype, h16.max())          # uint16, up to 65535
print("watertight?", solid.is_watertight)        # expect True
```

---

## Verify

```bash
python test_geom.py            # the scratch script above
```
- `test_relief.png` is written and is **16-bit** (`h16.dtype == uint16`).
- `solid.is_watertight` prints **True**.
- `test_relief.stl` opens in any STL viewer and looks like a raised dome on a flat base.

## Done when

- [ ] `relief_core.py` exists with all functions: `solve_poisson_neumann`,
      `normal_to_gradients`, `integrate_normals`, `bas_relief_compress`, `enhance_detail`,
      `flatten_background`, `to_heightmap_16bit`, `heightmap_to_surface`, `heightmap_to_solid`.
- [ ] Synthetic-normal smoke test produces a 16-bit PNG.
- [ ] `heightmap_to_solid(...).is_watertight` is `True`.
- [ ] STL opens in a viewer.

## Source

Plan §5.1 (`relief_core.py`, verified-runs-as-is) and §2 (why normal-driven, not depth).
