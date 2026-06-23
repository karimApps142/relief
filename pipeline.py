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
    normals: str = "marigold"       # "marigold" | "stable" (StableNormal is broken on Windows)
    use_depth_fusion: bool = True   # use global depth for the base form
    compress_beta: float = 0.55     # lower = flatter relief
    detail_gain: float = 1.4        # higher = punchier detail
    # --- detail composition (the portrait-quality knobs) ---
    form_strength: float = 1.0      # global 3D form (depth) weight; lower = flatter / more engraved
    normal_detail: float = 0.6      # surface relief from the AI normals
    image_detail: float = 0.8       # photographic texture from the photo's luminance (hair/fabric/skin)
    detail_sigma: float = 6.0       # high-pass cutoff in px; smaller = finer detail
    flip_y: bool = False            # toggle if relief comes out inverted
    invert: bool = False            # toggle white<->black height convention
    make_solid: bool = False        # True = watertight (3D print), False = CNC
    backend: str = None             # "lite" | "full" | "auto" | None (env default)


def generate_relief(image_path, out_dir, params: ReliefParams = ReliefParams(),
                    backend=None):
    from backends import get_backend
    be = get_backend(backend or getattr(params, "backend", None))

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")
    luma = np.asarray(image.convert("L")).astype(np.float32) / 255.0  # photo detail source

    # 0. subject mask
    mask = be.remove_background(image)

    # 1. surface normals -> integrate to a height field
    normal_map = be.estimate_normals(image, which=params.normals)
    height = rc.integrate_normals(normal_map, flip_y=params.flip_y)

    # 2. compose global form (depth) + surface detail (normals + photo luminance).
    #    The photographic luminance detail is the big quality lever for portraits;
    #    depth/normals alone smooth into a blob. depth is None in lite mode, where
    #    compose_relief falls back to the normal height for the base form.
    depth = be.estimate_depth(image) if params.use_depth_fusion else None
    height = rc.compose_relief(height, depth, luma,
                               form=params.form_strength,
                               normal_detail=params.normal_detail,
                               image_detail=params.image_detail,
                               sigma=params.detail_sigma)

    # 3. bas-relief compression (tame big depth jumps, keep the fine gradients)
    height = rc.bas_relief_compress(height, beta=params.compress_beta)

    # 4. enhance + flatten + 16-bit
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
