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
