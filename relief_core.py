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


# ----- edge-preserving helpers (noise control) -----
def _edge_preserve(a, sigma_color=0.06, sigma_space=5):
    """Bilateral smooth of a float32 image: removes low-contrast grain while
    keeping high-contrast edges (hair strands, feature lines). Extracting detail
    from this instead of the raw photo stops sensor grain becoming relief."""
    a = a.astype(np.float32)
    if sigma_color <= 0:
        return a
    return cv2.bilateralFilter(a, 0, float(sigma_color), float(sigma_space))


def denoise_surface(height, strength=0.5):
    """Edge-preserving smooth of the FINISHED height field to kill sub-feature
    geometric grain (the 'sandpaper' that meshes into a rough STL) while keeping
    carved edges/grooves. strength in [0,1]; 0 = off."""
    if strength <= 0:
        return height.astype(np.float32)
    h = height.astype(np.float32)
    lo, hi = float(h.min()), float(h.max())
    hn = (h - lo) / (hi - lo + 1e-8)
    sm = cv2.bilateralFilter(hn, 0, 0.04 + 0.08 * float(strength),
                             3.0 + 7.0 * float(strength))
    return (sm * (hi - lo) + lo).astype(np.float32)


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
    luma = _edge_preserve(luma, 0.06)            # de-grain before extracting detail
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


# ----- Stage 3c: PER-MATERIAL detail modulation (face-parsing driven) -----
# Given feathered region weight masks, modulate the fine/micro detail per region
# (skin smoothed via guided filter, hair carved into directional grooves along
# the structure-tensor orientation, eyes/lips sharpened, cloth weave) and blend
# with the feathered alphas — no seams. Falls back to plain compose_relief()
# when region_masks is None (lite / no face / parse failure).
def _structure_tensor(h, rho=1.0, sigma_t=2.0):
    """Local orientation (theta = gradient angle, ACROSS the strand) + coherence."""
    h = h.astype(np.float32)
    if rho > 0:
        h = cv2.GaussianBlur(h, (0, 0), rho)
    Gx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3)
    Gy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3)
    Gxx = cv2.GaussianBlur(Gx * Gx, (0, 0), sigma_t)
    Gyy = cv2.GaussianBlur(Gy * Gy, (0, 0), sigma_t)
    Gxy = cv2.GaussianBlur(Gx * Gy, (0, 0), sigma_t)
    theta = 0.5 * np.arctan2(2 * Gxy, Gxx - Gyy)
    tmp = np.sqrt((Gxx - Gyy) ** 2 + 4 * Gxy * Gxy)
    l1 = 0.5 * (Gxx + Gyy + tmp)
    l2 = 0.5 * (Gxx + Gyy - tmp)
    coh = (l1 - l2) / (l1 + l2 + 1e-8)
    return theta.astype(np.float32), coh.astype(np.float32)


def hair_anisotropic(h, gain=0.6, K=12, lambd=6.0, gamma=0.5, ks=21):
    """Carve grooves ALONG hair strands via an oriented Gabor bank steered by the
    structure-tensor orientation, gated by coherence (flat areas stay untouched)."""
    h32 = h.astype(np.float32)
    theta, coh = _structure_tensor(h32, rho=1.0, sigma_t=2.0)
    sigma = 0.56 * lambd
    angs = np.linspace(0, np.pi, K, endpoint=False)
    resp = np.zeros((K,) + h32.shape, np.float32)
    for k, a in enumerate(angs):                          # a = stripe-normal = gradient angle
        kern = cv2.getGaborKernel((ks, ks), sigma, a, lambd, gamma,
                                  psi=0, ktype=cv2.CV_32F)
        kern -= kern.mean()                               # zero-DC -> pure high-pass
        resp[k] = cv2.filter2D(h32, cv2.CV_32F, kern)
    idx = np.argmin(np.abs(((theta[None] - angs[:, None, None] + np.pi / 2)
                            % np.pi) - np.pi / 2), axis=0)
    carve = np.take_along_axis(resp, idx[None], 0)[0]
    carve = carve / (np.abs(carve).max() + 1e-8)
    return (h32 + gain * coh * carve).astype(np.float32)


def _guided_filter(I, p, r=4, eps=4e-4):
    """He 2010 guided filter — edge-aware base, no ximgproc dependency."""
    I = I.astype(np.float32); p = p.astype(np.float32)
    k = (2 * r + 1, 2 * r + 1)
    mI = cv2.boxFilter(I, -1, k); mp = cv2.boxFilter(p, -1, k)
    cov = cv2.boxFilter(I * p, -1, k) - mI * mp
    var = cv2.boxFilter(I * I, -1, k) - mI * mI
    a = cov / (var + eps); b = mp - a * mI
    return cv2.boxFilter(a, -1, k) * I + cv2.boxFilter(b, -1, k)


def _local_unsharp(h, r=1.2, amount=0.8):
    h = h.astype(np.float32)
    return h + amount * (h - cv2.GaussianBlur(h, (0, 0), r))


def compose_relief_perpart(normal_height, depth, luma, region_masks,
                           form=0.18, normal_detail=0.6, image_detail=1.0,
                           fine_detail=0.7, micro_detail=0.5, sigma=6.0,
                           hair_gain=2.2, skin_smooth=0.35, eye_gain=1.5,
                           lip_gain=1.1, cloth_gain=1.0):
    """Per-material variant of compose_relief. region_masks is None -> returns
    exactly compose_relief(...) (graceful fallback for lite / no-face)."""
    if region_masks is None:
        return compose_relief(normal_height, depth, luma, form, normal_detail,
                              image_detail, fine_detail, micro_detail, sigma)

    H, W = luma.shape
    luma = _edge_preserve(luma, 0.06)            # de-grain before extracting detail
    norm = lambda a: (a - a.min()) / (a.max() - a.min() + 1e-8)

    def fit(a):
        a = a.astype(np.float32)
        return a if a.shape[:2] == (H, W) else cv2.resize(a, (W, H))

    def band(a, s):
        a = norm(fit(a))
        hp = a - cv2.GaussianBlur(a, (0, 0), s)
        rstd = 1.4826 * np.median(np.abs(hp - np.median(hp))) + 1e-6
        return hp / rstd

    # global form (identical to compose_relief)
    src = depth if depth is not None else normal_height
    g = norm(cv2.GaussianBlur(fit(src), (0, 0), sigma * 2.5))
    g = norm(g - cv2.GaussianBlur(g, (0, 0), sigma * 8.0))

    # split detail: mid (structure, kept ~1.0) vs fine+micro (region-modulated)
    detail_mid = (normal_detail * band(normal_height, sigma)
                  + image_detail * band(luma, sigma))
    detail_fine = (fine_detail * band(luma, sigma * 0.5)
                   + micro_detail * band(luma, sigma * 0.25))

    def M(name):
        m = region_masks.get(name)
        return fit(m) if m is not None else np.zeros((H, W), np.float32)
    m_hair, m_skin = M("hair"), M("skin")
    m_eyes, m_lips = M("eyes"), M("lips")
    m_cloth, m_bg = M("cloth"), M("bg")

    # per-region GAIN field for fine+micro (feathered partition of unity)
    GAIN = {"hair": hair_gain, "skin": skin_smooth, "eyes": eye_gain,
            "lips": lip_gain, "cloth": cloth_gain, "bg": 0.0}
    s = np.full((H, W), 1e-6, np.float32)
    gain_field = np.zeros((H, W), np.float32)
    for name, m in (("hair", m_hair), ("skin", m_skin), ("eyes", m_eyes),
                    ("lips", m_lips), ("cloth", m_cloth), ("bg", m_bg)):
        gain_field += m * GAIN[name]
        s += m
    gain_field = gain_field / s
    covered = np.clip(s - 1e-6, 0, 1)                     # uncovered pixels -> gain 1.0
    gain_field = covered * gain_field + (1.0 - covered) * 1.0
    gain_field = gain_field * (1.0 - m_bg)               # hard-kill background detail

    relief = form * g + detail_mid + gain_field * detail_fine

    # targeted per-region treatments, alpha-blended by the feathered mask
    if m_skin.max() > 0:                                 # skin: edge-aware smoothing
        base = _guided_filter(relief, relief, r=4, eps=4e-4)
        skin_treated = base + skin_smooth * (relief - base)
        relief = m_skin * skin_treated + (1.0 - m_skin) * relief
    if m_hair.max() > 0:                                 # hair: directional grooves
        relief = (m_hair * hair_anisotropic(relief, gain=0.6, lambd=6.0)
                  + (1.0 - m_hair) * relief)
    if m_eyes.max() > 0:                                 # eyes/brows: targeted sharpen
        relief = (m_eyes * _local_unsharp(relief, r=1.2, amount=0.8)
                  + (1.0 - m_eyes) * relief)
    if m_lips.max() > 0:                                 # lips: vermilion ridge + striations
        gx = cv2.Sobel(m_lips, cv2.CV_32F, 1, 0, 3)
        gy = cv2.Sobel(m_lips, cv2.CV_32F, 0, 1, 3)
        vermilion = 0.05 * np.sqrt(gx * gx + gy * gy)
        striate = relief - cv2.GaussianBlur(relief, (0, 0), sigmaX=1.0, sigmaY=3.0)
        relief = (m_lips * (relief + vermilion + 0.6 * striate)
                  + (1.0 - m_lips) * relief)
    # (cloth keeps the photo's own weave via the gain field; no synthetic noise
    #  added — that was geometric sandpaper on the STL.)

    return relief.astype(np.float32)


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


def heightmap_to_preview(height16, z_scale_mm=8.0, pixel_mm=0.1, max_px=400):
    """Lightweight DOWNSAMPLED surface mesh for the in-browser 3D viewer — the
    full-res STL can be 100+ MB / millions of faces, too heavy for a browser."""
    h = height16
    rows, cols = h.shape
    scale = min(1.0, float(max_px) / max(rows, cols))
    if scale < 1.0:
        h = cv2.resize(h.astype(np.float32),
                       (max(2, int(cols * scale)), max(2, int(rows * scale))),
                       interpolation=cv2.INTER_AREA).astype(np.uint16)
        pixel_mm = pixel_mm / scale            # keep the physical dimensions
    return heightmap_to_surface(h, z_scale_mm, pixel_mm)


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
