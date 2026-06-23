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
    use_depth_fusion: bool = True   # use global depth for the (now shallow) base form
    compress_beta: float = 0.55     # (legacy; unused by the new engraved engine)
    detail_gain: float = 1.4        # (legacy; unused by the new engraved engine)
    # --- form vs. detail composition (sculpt.ok-style: shallow form, dominant detail) ---
    form_strength: float = 0.18     # global dome share; lower = flatter / more engraved
    normal_detail: float = 0.6      # surface relief from the AI normals
    image_detail: float = 1.0       # medium photographic texture (planes / fabric)
    fine_detail: float = 0.7        # fine strands / lip lines
    micro_detail: float = 0.5       # pores / lashes / micro-texture
    detail_sigma: float = 6.0       # base high-pass cutoff in px (smaller = finer)
    # --- local contrast + base plate ---
    clahe_clip: float = 2.5         # local-contrast strength ("detail everywhere")
    clahe_tile: int = 96            # CLAHE tile size in px
    micro_gain: float = 0.6         # final crisp sharpen
    base_height: float = 0.50       # mid-gray base plate level
    fig_span: float = 0.45          # shallow figure relief above the base
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

    # 2. compose a SHALLOW global form + DOMINANT multi-scale detail (kills the
    #    inflated-balloon look). depth is None in lite mode -> form from normals.
    depth = be.estimate_depth(image) if params.use_depth_fusion else None
    height = rc.compose_relief(height, depth, luma,
                               form=params.form_strength,
                               normal_detail=params.normal_detail,
                               image_detail=params.image_detail,
                               fine_detail=params.fine_detail,
                               micro_detail=params.micro_detail,
                               sigma=params.detail_sigma)

    # 3. local-contrast normalize (CLAHE) + crisp micro-unsharp -> "detail everywhere"
    height = rc.normalize_local(height, clip=params.clahe_clip,
                                tile=params.clahe_tile, micro_gain=params.micro_gain)

    # 4. seat the figure on a flat mid-gray base with a crisp silhouette step
    height = rc.compose_onto_base(height, mask, base=params.base_height,
                                  fig_span=params.fig_span)

    # 5. export 16-bit WITHOUT renormalizing, so the shallow base/range survives
    height16 = rc.to_heightmap_16bit(height, invert=params.invert, normalize=False)

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
