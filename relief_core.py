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


# ----- Stage 3b: compose a SHALLOW form + DOMINANT multi-scale detail -----
# sculpt.ok-class reliefs are ~85% multi-scale edge-aware DETAIL riding on a
# deliberately crushed (~15%) global form. The previous version did the
# opposite: a full-range depth dome at form=1.0 plus tiny high-pass residuals,
# so form swamped detail ~15:1 -> an inflated soft bust. Fixes here:
#   (1) plane-subtract the depth dome and keep only a small slice (form~0.18);
#   (2) build detail from MAD-normalized octaves so each weight is a REAL
#       amplitude (a raw high-pass is only a few % p-p), incl. a ~1.5px micro
#       band for lashes/pores. The detail sum (~2.8) now dominates the thin form.
# (Fattal 2002 / Weyrich 2007 gradient-domain bas-relief family.)
def compose_relief(normal_height, depth, luma, form=0.18, normal_detail=0.6,
                   image_detail=1.0, fine_detail=0.7, micro_detail=0.5, sigma=6.0):
    H, W = luma.shape
    norm = lambda a: (a - a.min()) / (a.max() - a.min() + 1e-8)

    def fit(a):                                  # align every layer to the photo
        a = a.astype(np.float32)
        return a if a.shape[:2] == (H, W) else cv2.resize(a, (W, H))

    def band(a, s):                              # zero-mean octave, ~unit amplitude
        a = norm(fit(a))
        hp = a - cv2.GaussianBlur(a, (0, 0), s)
        rstd = 1.4826 * np.median(np.abs(hp - np.median(hp))) + 1e-6
        return hp / rstd                         # MAD-normalize: weight -> real amplitude

    # GLOBAL FORM: crush the balloon — strip the broad low-freq dome, keep a sliver
    src = depth if depth is not None else normal_height
    g = norm(cv2.GaussianBlur(fit(src), (0, 0), sigma * 2.5))
    g = norm(g - cv2.GaussianBlur(g, (0, 0), sigma * 8.0))

    # MULTI-SCALE DETAIL: finest octaves dominate (~1/f spectrum)
    detail = normal_detail * band(normal_height, sigma)          # mid (AI normals)
    detail = detail + image_detail * band(luma, sigma)           # medium texture
    detail = detail + fine_detail * band(luma, sigma * 0.5)      # fine strands
    detail = detail + micro_detail * band(luma, sigma * 0.25)    # micro (lashes/pores)

    return form * g + detail


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


# ----- Stage 5b (new engine): local-contrast normalize + flat mid-gray base -----
def _clahe_tiles(h, px):
    return (max(2, h.shape[1] // px), max(2, h.shape[0] // px))


def normalize_local(height, clip=2.5, tile=96, gamma=0.85, micro_gain=0.6):
    """CLAHE local-contrast + crisp micro-unsharp so detail reads with comparable
    amplitude EVERYWHERE (smooth cheek vs. dense hair) — the engraved character.
    Replaces enhance_detail in the new flow; a 0.5/99.5 percentile stretch makes
    it robust to the spiky outliers MAD-normalized detail bands can produce."""
    lo, hi = np.percentile(height, [0.5, 99.5])
    h = np.clip((height - lo) / (hi - lo + 1e-8), 0.0, 1.0).astype(np.float32)
    h16 = (h * 65535.0).astype(np.uint16)
    clahe = cv2.createCLAHE(clipLimit=float(clip), tileGridSize=_clahe_tiles(h, tile))
    h = clahe.apply(h16).astype(np.float32) / 65535.0
    h = np.power(h, gamma)                                # mild mid-tone lift
    hp = h - cv2.GaussianBlur(h, (0, 0), 1.5)            # true fine high-pass
    return np.clip(h + micro_gain * hp, 0.0, 1.0)


def compose_onto_base(figure, mask, base=0.50, fig_span=0.45):
    """Seat the figure on a flat mid-gray plate with a crisp silhouette step, so it
    looks engraved into a slab (sculpt.ok-style) instead of a full-range dome
    floating in black. Caller must NOT renormalize after this (keeps it shallow)."""
    f = (figure - figure.min()) / (figure.max() - figure.min() + 1e-8)
    out = (base + f * fig_span).astype(np.float32)       # figure rides base..base+span
    if mask is not None and mask.shape[:2] == out.shape[:2]:
        out = np.where(mask > 0.5, out, base).astype(np.float32)  # flat base + crisp edge
    return out


def to_heightmap_16bit(height, invert=False, normalize=True):
    h = height.astype(np.float64)
    if normalize:                                # legacy callers: stretch to full range
        h = (h - h.min()) / (h.max() - h.min() + 1e-8)
    else:                                        # new flow: keep the shallow base/range
        h = np.clip(h, 0.0, 1.0)
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
