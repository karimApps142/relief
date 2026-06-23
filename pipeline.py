"""
pipeline.py — single image in, relief heightmap + STL out.
Depth-first: a smooth monocular DEPTH map IS the heightmap (near = high), seated
on a flat base. This is the right data for bas-relief / CNC / lithophane (a
continuous height field, not an engraving). Backend-aware: lite (Mac, luminance
pseudo-depth) and full (GPU: Sapiens / Depth-Anything) share one geometry path.
"""
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

import relief_core as rc


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve (mm)
    pixel_mm: float = 0.1            # mm per pixel (plate size)
    depth_model: str = "sapiens"    # "sapiens" (human-specialized) | "depth-anything"
    invert: bool = False            # flip near<->far if the subject comes out sunken
    depth_smooth: float = 0.5       # edge-preserving smoothing of the depth (de-noise)
    depth_compress: float = 1.0     # gamma; <1 flattens the near -> shallower/flatter relief
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

    # 1. monocular depth — the heightmap source (smooth, continuous surface height)
    depth = be.estimate_depth(image, model=params.depth_model)

    # 2. subject mask, to seat the figure on a flat base
    mask = be.remove_background(image) if params.flatten_bg else None

    # 3. depth -> clean smooth relief heightmap (NO emboss / edge detail)
    height = rc.depth_to_heightmap(depth, mask,
                                   invert=params.invert,
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
