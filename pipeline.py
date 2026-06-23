"""
pipeline.py — single image in, relief heightmap + STL out.
Depth-first: a smooth monocular DEPTH map IS the heightmap (near = high), seated
on a flat base. This is the right data for bas-relief / CNC / lithophane (a
continuous height field, not an engraving). Backend-aware: lite (Mac, luminance
pseudo-depth) and full (GPU: Sapiens / Depth-Anything) share one geometry path.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import cv2
import numpy as np
from PIL import Image

import relief_core as rc

# raw depth cache: geometry/refine sliders re-tune without re-invoking the GPU.
# Keyed on (image, model, tiling); holds only the most recent (bounded memory).
_DEPTH_CACHE = {}


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve (mm)
    pixel_mm: float = 0.1            # mm per pixel (plate size)
    depth_model: str = "sapiens"    # "sapiens" (human-specialized) | "depth-anything"
    invert: bool = False            # flip near<->far if the subject comes out sunken
    depth_smooth: float = 0.5       # edge-preserving smoothing of the depth (de-noise)
    depth_compress: float = 1.0     # gamma; <1 flattens the near -> shallower/flatter relief
    refine: float = 0.6             # guided-filter edge refine: snap depth edges to the photo
    tiling: bool = False            # high-res tile fusion (Depth-Anything only; slow, opt-in)
    flatten_bg: bool = True         # seat the subject on a flat base via the mask
    base_height: float = 0.50       # base plate level
    fig_span: float = 0.45          # subject relief height above the base
    make_solid: bool = False        # watertight solid (3D print) vs open surface (CNC)
    normals: str = "marigold"       # (unused by the depth pipeline; kept for API compat)
    backend: str = None             # "lite" | "full" | "auto" | None (env default)


def generate_relief(image_path, out_dir, params: ReliefParams = ReliefParams(),
                    backend=None):
    from backends import get_backend
    be = get_backend(backend or getattr(params, "backend", None))

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")
    luma = np.asarray(image.convert("L")).astype(np.float32) / 255.0  # guide for edge refine

    # 1. monocular depth — cached on (image, model, tiling) so the geometry/refine
    #    sliders below re-tune instantly without re-invoking the GPU depth model.
    try:
        ckey = (image_path, os.path.getmtime(image_path), params.depth_model, params.tiling)
    except OSError:
        ckey = None
    if ckey is not None and ckey in _DEPTH_CACHE:
        depth = _DEPTH_CACHE[ckey]
    else:
        depth = be.estimate_depth(image, model=params.depth_model, tiling=params.tiling)
        if ckey is not None:
            _DEPTH_CACHE.clear()                 # keep only the most recent (bounded memory)
            _DEPTH_CACHE[ckey] = depth

    # 2. subject mask, to seat the figure on a flat base
    mask = be.remove_background(image) if params.flatten_bg else None

    # 3. depth -> clean smooth relief heightmap; guided refine snaps edges to the photo
    height = rc.depth_to_heightmap(depth, mask, luma=luma,
                                   invert=params.invert,
                                   refine=params.refine,
                                   smooth=params.depth_smooth,
                                   compress=params.depth_compress,
                                   flatten_bg=params.flatten_bg,
                                   base=params.base_height,
                                   fig_span=params.fig_span)

    # 4. export 16-bit (no renormalize — keep the base/range from depth_to_heightmap)
    height16 = rc.to_heightmap_16bit(height, normalize=False)
    png_path = out / "relief_heightmap.png"
    cv2.imwrite(str(png_path), height16)         # 16-bit PNG

    # 5. STL
    if params.make_solid:
        mesh = rc.heightmap_to_solid(height16, params.relief_depth_mm, params.pixel_mm)
    else:
        mesh = rc.heightmap_to_surface(height16, params.relief_depth_mm, params.pixel_mm)
    stl_path = out / "relief.stl"
    mesh.export(str(stl_path))

    return {"heightmap": str(png_path), "stl": str(stl_path)}
