"""
relief_core.py — CPU geometry stages of the bas-relief pipeline.
Normal integration, bas-relief compression, detail enhancement,
16-bit export, and STL export. No GPU / no models needed here.
"""
import numpy as np
import cv2
from scipy.fft import dctn, idctn
from PIL import Image
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
    p, q = normal_to_gradients(normal_map, flip_y)      # p=dz/dx, q=dz/dy
    # Divergence via BACKWARD differences so it matches the 5-point Laplacian the DCT
    # Neumann solver inverts. (Central np.gradient is a wider stencil → inconsistent →
    # the surface is NOT recovered: round-trip corr 0.46 vs 0.99 for backward.)
    div = np.zeros_like(p)
    div[:, 1:] += p[:, 1:] - p[:, :-1]; div[:, 0] += p[:, 0]
    div[1:, :] += q[1:, :] - q[:-1, :]; div[0, :] += q[0, :]
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


def guided_refine_depth(depth, luma, r=8, eps=1e-3, strength=0.6):
    """Snap a smooth depth map onto the PHOTO's edges via the He-2010 JOINT guided
    filter (guide = photo luma, input = depth). Unlike a self-bilateral it relocates
    & sharpens depth edges to the image's true edges (jaw/hairline/collar) and is
    halo-free. Blended (strength<1) and the guide is de-grained first, so the photo's
    albedo/texture is NOT engraved into the geometry."""
    d = depth.astype(np.float32)
    I = _edge_preserve(luma.astype(np.float32), 0.06)        # de-grain the guide
    if I.shape[:2] != d.shape[:2]:
        I = cv2.resize(I, (d.shape[1], d.shape[0]))
    I = (I - I.min()) / (I.max() - I.min() + 1e-8)
    q = _guided_filter(I, d, r=int(r), eps=float(eps))       # joint: guide=photo, input=depth
    return ((1.0 - strength) * d + strength * q).astype(np.float32)


def fuse_depth_normals(depth, normal_height, detail=0.7, sigma=12.0):
    """Combine a smooth DEPTH map (reliable global form) with surface-NORMAL detail
    (the crisp facial geometry depth smooths away): global low-frequency shape from
    depth + high-frequency facial relief (eyes / nose / lips / cheekbones) from the
    integrated normals. This is what turns a featureless depth blob into a defined
    face. `detail` scales how strongly the normal-derived features stand out."""
    norm = lambda a: (a - a.min()) / (a.max() - a.min() + 1e-8)
    d = norm(depth.astype(np.float32))
    n = norm(normal_height.astype(np.float32))
    if n.shape[:2] != d.shape[:2]:
        n = cv2.resize(n, (d.shape[1], d.shape[0]))
    form = cv2.GaussianBlur(d, (0, 0), sigma)               # global shape from depth
    feat = n - cv2.GaussianBlur(n, (0, 0), sigma)           # facial detail from normals
    return (form + float(detail) * feat).astype(np.float32)


# ----- DEPTH-FIRST: raw monocular depth -> clean smooth relief heightmap -----
# The correct data for bas-relief / CNC / lithophane is a SMOOTH CONTINUOUS depth
# field (near = high), NOT an emboss/edge map. This robust-normalizes the depth,
# optionally inverts (if the subject comes out sunken), edge-preserving-smooths
# away model noise, gently gamma-compresses the range, and seats the subject on a
# flat base via the mask. No detail bands, no CLAHE, no engraving.
def depth_to_heightmap(depth, mask=None, luma=None, invert=False, refine=0.6,
                       smooth=0.5, compress=1.0, flatten_bg=True, base=0.50,
                       fig_span=0.45):
    d = depth.astype(np.float32)
    lo, hi = np.percentile(d, [1, 99])           # robust normalize (ignore outliers)
    d = np.clip((d - lo) / (hi - lo + 1e-8), 0.0, 1.0).astype(np.float32)
    if invert:
        d = (1.0 - d).astype(np.float32)
    if luma is not None and refine > 0:          # snap depth edges to the photo's edges
        d = guided_refine_depth(d, luma, strength=float(refine))
    if smooth > 0:                               # de-noise the model output, keep form
        d = cv2.bilateralFilter(d, 0, 0.04 + 0.16 * float(smooth),
                                3.0 + 9.0 * float(smooth))
    if compress != 1.0:                          # gamma <1 flattens the near -> shallower
        d = np.power(np.clip(d, 0.0, 1.0), float(compress)).astype(np.float32)
    if flatten_bg and mask is not None and mask.shape[:2] == d.shape[:2]:
        m = mask > 0.5
        if m.any():                              # rescale within the subject region
            slo, shi = np.percentile(d[m], [1, 99])
            d = np.clip((d - slo) / (shi - slo + 1e-8), 0.0, 1.0)
        out = np.where(m, base + d * fig_span, base)   # subject on a flat base
    else:
        out = base + np.clip(d, 0.0, 1.0) * fig_span
    return out.astype(np.float32)


def tiled_relief_heightmap(depth, mask=None, invert=False, base=0.50, fig_span=0.45, bg=None,
                           normal_map=None, normal_detail=0.7, normal_sigma=12.0):
    """LEAN heightmap for TILED depth: the tiling already baked the facial detail
    into the depth, so do only robust percentile-normalize -> (invert) -> re-stretch
    inside the subject -> seat on a flat base. NO bilateral / guided-refine / gamma /
    CLAHE / unsharp — any blur > ~1.5px would erase the sub-2px detail tiling recovered.
    `bg` = background level: None -> `base` (mid-gray slab); 0.0 -> pure black.

    If `normal_map` is given, fuse the surface-NORMAL high-frequency detail onto the
    depth's low-frequency form (Poisson-integrate the normals, then keep depth's global
    shape + the normals' crisp facial relief). This is the depth+normal fusion the
    bas-relief literature uses for clean eyes/hair/lips; `normal_detail` scales it."""
    d = depth.astype(np.float32)
    lo, hi = np.percentile(d, [1, 99])                   # seam-spike-safe normalize
    d = np.clip((d - lo) / (hi - lo + 1e-8), 0.0, 1.0).astype(np.float32)
    if invert:
        d = (1.0 - d).astype(np.float32)
    if normal_map is not None and float(normal_detail) > 0:
        nh = integrate_normals(np.asarray(normal_map, np.float32))   # normals -> height
        d = fuse_depth_normals(d, nh, detail=float(normal_detail), sigma=float(normal_sigma))
        d = np.clip((d - d.min()) / (d.max() - d.min() + 1e-8), 0.0, 1.0).astype(np.float32)
    bg_lvl = base if bg is None else float(bg)
    if mask is not None and mask.shape[:2] == d.shape[:2]:
        m = mask > 0.5
        if m.any():                                      # use the full Z budget on the subject
            slo, shi = np.percentile(d[m], [1, 99])
            d = np.clip((d - slo) / (shi - slo + 1e-8), 0.0, 1.0)
        out = np.where(m, base + d * fig_span, bg_lvl)
    else:
        out = base + d * fig_span
    return out.astype(np.float32)


# ----- MESH -> heightmap (orthographic Z render; the pro 'project a 3D model' path) -----
def mesh_to_heightmap(mesh, view="front", resolution=1024):
    """Orthographic depth render of a 3D mesh → a front-surface height field + mask.

    Rotates `view` to face the camera (+Z), then z-buffers the NEAREST surface per pixel
    with a small numpy triangle rasteriser (headless — no OpenGL). This is how ZBrush
    'Bas Relief' / Carveco / Aspire turn a 3D model into a carve-able heightmap, and it
    captures true z-order (ears, nose, profiles) that monocular depth cannot.
    Returns (depth HxW float32 [near=high], mask HxW float32 in {0,1})."""
    import trimesh
    rot = {
        "front": None,
        "back":   trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]),
        "left":   trimesh.transformations.rotation_matrix(-np.pi / 2, [0, 1, 0]),
        "right":  trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]),
        "top":    trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]),
        "bottom": trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]),
    }.get(view)
    m = mesh.copy()
    if rot is not None:
        m.apply_transform(rot)
    v = np.asarray(m.vertices, np.float64)
    f = np.asarray(m.faces, np.int64)
    mn = v.min(0)
    ex = np.maximum(v.max(0) - mn, 1e-9)
    scale = (resolution - 1) / max(ex[0], ex[1])
    W = max(2, int(round(ex[0] * scale)) + 1)
    H = max(2, int(round(ex[1] * scale)) + 1)
    px = (v[:, 0] - mn[0]) * scale
    py = (v[:, 1] - mn[1]) * scale
    pz = v[:, 2]
    zbuf = np.full((H, W), -np.inf)
    tris = np.stack([px[f], py[f], pz[f]], -1)            # (T, 3, 3): rows = [x, y, z]
    for (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) in tris:
        lox = max(int(np.floor(min(x0, x1, x2))), 0); hix = min(int(np.ceil(max(x0, x1, x2))), W - 1)
        loy = max(int(np.floor(min(y0, y1, y2))), 0); hiy = min(int(np.ceil(max(y0, y1, y2))), H - 1)
        if hix < lox or hiy < loy:
            continue
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(den) < 1e-12:
            continue
        gy, gx = np.mgrid[loy:hiy + 1, lox:hix + 1]
        a = ((y1 - y2) * (gx - x2) + (x2 - x1) * (gy - y2)) / den
        b = ((y2 - y0) * (gx - x2) + (x0 - x2) * (gy - y2)) / den
        c = 1.0 - a - b
        ins = (a >= 0) & (b >= 0) & (c >= 0)
        if not ins.any():
            continue
        z = a * z0 + b * z1 + c * z2
        sub = zbuf[loy:hiy + 1, lox:hix + 1]              # view into zbuf
        upd = ins & (z > sub)
        sub[upd] = z[upd]
    mask = np.isfinite(zbuf)
    fill = float(zbuf[mask].min()) if mask.any() else 0.0
    depth = np.where(mask, zbuf, fill).astype(np.float32)
    return depth[::-1].copy(), mask[::-1].astype(np.float32).copy()   # flip → upright image


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


def heightmap_to_preview(height16, z_scale_mm=8.0, pixel_mm=0.1, max_px=320):
    """Lightweight DOWNSAMPLED, viewer-oriented SOLID mesh for the in-browser 3D
    preview. A closed solid renders correctly lit from any angle (an open surface
    goes dark/invisible from the back). The full-res STL (100+ MB) is too heavy
    for a browser, so we downsample. The image Y axis points DOWN while the 3D
    viewer is Y-up, so flip Y to make it upright, then re-fix outward normals."""
    h = height16
    rows, cols = h.shape
    scale = min(1.0, float(max_px) / max(rows, cols))
    if scale < 1.0:
        h = cv2.resize(h.astype(np.float32),
                       (max(2, int(cols * scale)), max(2, int(rows * scale))),
                       interpolation=cv2.INTER_AREA).astype(np.uint16)
        pixel_mm = pixel_mm / scale            # keep the physical dimensions
    m = heightmap_to_solid(h, z_scale_mm, pixel_mm)
    m.apply_transform([[1, 0, 0, 0],
                       [0, -1, 0, 0],            # flip image-Y -> viewer up
                       [0, 0, 1, 0],
                       [0, 0, 0, 1]])
    trimesh.repair.fix_normals(m)               # outward normals after the reflection
    # matte, non-metallic material so the viewer's lighting reveals the relief
    # surface instead of washing out as flat white.
    m.visual = trimesh.visual.TextureVisuals(
        material=trimesh.visual.material.PBRMaterial(
            name="relief", baseColorFactor=[200, 202, 210, 255],
            metallicFactor=0.0, roughnessFactor=0.85))
    return m


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


# ----- High-res depth via overlapping-tile fusion (TilingZoeDepth method) -----
# Opt-in, for a GENERIC depth model (Depth-Anything) ONLY — a whole-person model
# (Sapiens) degrades on context-free crops. Runs D on a global pass + two
# overlapping tile grids, moment-matches each tile to the global depth, blends
# with cos^2 windows (explicit /sum-of-weights), then merges fine detail where the
# photo has edges. Many forward passes -> slow; gate behind a UI toggle. Pure CPU.
def _tzd_windows(M, N, peak=0.998):
    i = np.arange(M)[:, None]; j = np.arange(N)[None, :]
    xw = np.broadcast_to(peak * np.cos((np.abs(M / 2 - i) / M) * np.pi) ** 2, (M, N))
    yw = np.broadcast_to(peak * np.cos((np.abs(N / 2 - j) / N) * np.pi) ** 2, (M, N))
    full = xw * yw
    top = np.broadcast_to(i < M / 2, (M, N)); left = np.broadcast_to(j < N / 2, (M, N))
    W = {'filter': full,
         'left_filter': np.where(left, xw, full), 'right_filter': np.where(~left, xw, full),
         'top_filter': np.where(top, yw, full), 'bottom_filter': np.where(~top, yw, full)}

    def corner(vert, horz):
        out = full.copy()
        out = np.where(horz & ~vert, xw, out)
        out = np.where(vert & ~horz, yw, out)
        return np.where(vert & horz, peak, out)
    W['top_left_filter'] = corner(top, left); W['top_right_filter'] = corner(top, ~left)
    W['bottom_left_filter'] = corner(~top, left); W['bottom_right_filter'] = corner(~top, ~left)
    return W


def _tzd_select(W, x, y, x_all, y_all):
    xmin, xmax, ymin, ymax = min(x_all), max(x_all), min(y_all), max(y_all)
    if y == ymin and x == xmin: return W['top_left_filter']
    if y == ymin and x == xmax: return W['bottom_left_filter']
    if y == ymax and x == xmin: return W['top_right_filter']
    if y == ymax and x == xmax: return W['bottom_right_filter']
    if y == ymin: return W['left_filter']
    if y == ymax: return W['right_filter']
    if x == xmin: return W['top_filter']
    if x == xmax: return W['bottom_filter']
    return W['filter']


def _tzd_norm(a):
    return (a - a.min()) / (a.max() - a.min() + 1e-12)


def _tzd_grid(im_uint8, D, global01, num_x, num_y):
    H, Wd = im_uint8.shape[:2]
    M, N = H // num_x, Wd // num_y
    win = _tzd_windows(M, N)
    x_all = (list(range(0, H, H // num_x))[:num_x]
             + list(range((H // num_x) // 2, H, H // num_x))[:num_x - 1])
    y_all = (list(range(0, Wd, Wd // num_y))[:num_y]
             + list(range((Wd // num_y) // 2, Wd, Wd // num_y))[:num_y - 1])
    acc = np.zeros((H, Wd), np.float64); wsum = np.zeros((H, Wd), np.float64)
    for x in x_all:
        for y in y_all:
            t = _tzd_norm(np.asarray(D(Image.fromarray(im_uint8[x:x + M, y:y + N])),
                                     dtype=np.float64))
            g = global01[x:x + M, y:y + N]
            t_al = g.mean() + g.std() * ((t - t.mean()) / (t.std() + 1e-12))  # moment-match
            w = _tzd_select(win, x, y, x_all, y_all)
            acc[x:x + M, y:y + N] += w * t_al
            wsum[x:x + M, y:y + N] += w
    acc /= np.maximum(wsum, 1e-6)
    acc[acc < 0] = 0
    return acc


def detect_face_box(image, expand=0.6):
    """Largest frontal-face bbox (expanded by `expand` on each side), or None.
    OpenCV Haar cascade — CPU, no model download."""
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    try:
        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
    except Exception:
        return None
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    H, W = gray.shape
    ex, ey = int(w * expand), int(h * expand)
    return (max(0, x - ex), max(0, y - ey), min(W, x + w + ex), min(H, y + h + ey))


def _crop_feather(h, w, frac=0.12):
    fy, fx = max(1, int(h * frac)), max(1, int(w * frac))
    wy, wx = np.ones(h, np.float64), np.ones(w, np.float64)
    wy[:fy] = np.linspace(0, 1, fy); wy[-fy:] = np.linspace(1, 0, fy)
    wx[:fx] = np.linspace(0, 1, fx); wx[-fx:] = np.linspace(1, 0, fx)
    return np.outer(wy, wx)


def _call_D(D, pil, input_size):
    import inspect
    try:
        if "input_size" in inspect.signature(D).parameters:
            return D(pil, input_size=input_size)
    except (TypeError, ValueError):
        pass
    return D(pil)


def tiled_depth_facecrop(image, D, grids=((3, 3), (6, 6)), input_size=768,
                         expand=0.6, feather=0.12):
    """Spend the tile budget on the FACE: one cheap global pass for the body form,
    the full overlapping-tile grid on a tight face crop (so the face fills the
    model input -> max detail), then composite the face depth back in (scale/shift
    aligned to the body depth + feathered). Falls back to whole-frame tiling if no
    face is found. More facial detail for fewer passes than tiling the whole frame."""
    img = image.convert("RGB")
    box = detect_face_box(img, expand)
    if box is None:
        return tiled_depth(img, D, grids=grids, input_size=input_size)
    body = _tzd_norm(np.asarray(_call_D(D, img, input_size), dtype=np.float64))  # 1 pass
    x0, y0, x1, y1 = box
    face = _tzd_norm(tiled_depth(img.crop(box), D, grids=grids,
                                 input_size=input_size).astype(np.float64))
    region = body[y0:y1, x0:x1]
    if face.std() > 1e-6:                                 # match the body's local scale/shift
        face = region.mean() + region.std() * (face - face.mean()) / face.std()
    w = _crop_feather(y1 - y0, x1 - x0, feather)
    out = body.copy()
    out[y0:y1, x0:x1] = (1 - w) * region + w * face
    return _tzd_norm(out).astype(np.float32)


def tiled_depth(image, D, grids=((3, 3), (6, 6)), input_size=768):
    """High-res depth by fusing a global pass with two overlapping-tile grids
    (TilingZoeDepth). D(PIL[, input_size])->HxW float. Returns HxW [0,1] (near=large).
    Each tile is run at the model's full resolution (input_size) so the face fills
    the receptive field and fine geometry is recovered, then stitched seamlessly."""
    import inspect
    try:
        accepts = "input_size" in inspect.signature(D).parameters
    except (TypeError, ValueError):
        accepts = False
    Dt = (lambda pil: D(pil, input_size=input_size)) if accepts else D
    img = image.convert("RGB")
    im = np.asarray(img)
    global01 = _tzd_norm(np.asarray(Dt(img), dtype=np.float64))
    (nx0, ny0), (nx1, ny1) = grids
    coarse = _tzd_grid(im, Dt, global01, nx0, ny0)
    fine = _tzd_grid(im, Dt, global01, nx1, ny1)
    grey = im.mean(axis=2).astype(np.float32)
    diff = cv2.GaussianBlur(grey, (0, 0), 20) - grey
    diff = diff / (np.max(diff) + 1e-12)
    diff = cv2.GaussianBlur(diff, (0, 0), 40) * 5.0
    mask = np.clip(diff, 0, 0.999)
    combined = (mask * fine + (1 - mask) * ((coarse + global01) / 2)) / 2
    return (combined / (np.max(combined) + 1e-12)).astype(np.float32)
