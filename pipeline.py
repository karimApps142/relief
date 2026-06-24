"""
pipeline.py — single image in, relief heightmap + STL out.

TILED depth IS the heightmap. A single-pass depth model downscales the whole
photo (~500px) so the face collapses to a smooth blob; running depth on
overlapping TILES at full model resolution recovers eye/nose/lip geometry, then
stitches it back. Once tiling bakes that detail into the depth map, the job of
post-processing is only: normalize -> seat the subject on a flat base -> mm mesh.
No emboss, no CLAHE, no normal-fusion, no smoothing — those only erase the detail.
"""
from dataclasses import dataclass
from pathlib import Path
import os
import cv2
import numpy as np
from PIL import Image

import relief_core as rc

# tile_detail -> (coarse grid, fine grid). Coarse stays <=3x3 for global scale
# stability; fine sized so one tile ~ the face box ~ the model's native res.
_GRIDS = {"low": ((2, 2), (4, 4)), "medium": ((3, 3), (6, 6)), "high": ((4, 4), (8, 8)),
          "ultra": ((5, 5), (10, 10)), "max": ((6, 6), (12, 12))}

# raw depth cache: geometry sliders re-tune instantly without re-running the GPU.
# Keyed on (image, model, tile_detail, da3_variant); holds only the most recent.
_RAW_CACHE = {}


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve (mm)
    pixel_mm: float = 0.1            # mm per pixel (plate size / XY resolution)
    depth_model: str = "depth-anything"  # DA-V2-L: crop-friendly + input_size scalable (best for tiling)
    da3_variant: str = "DA3MONO-LARGE"   # only when depth_model == depth-anything-3
    tile_detail: str = "medium"     # off | low | medium | high  (tile density = facial detail)
    face_crop: bool = True          # focus the tile budget on a detected face crop (sharper + faster)
    black_bg: bool = True           # pure-black background (vs a mid-gray base plate)
    invert: bool = False            # flip near<->far if the subject comes out sunken
    flatten_bg: bool = True         # seat the subject on a flat base via the mask
    base_height: float = 0.50       # base plate level
    fig_span: float = 0.45          # subject relief height above the base
    make_solid: bool = False        # watertight solid (3D print) vs open surface (CNC)
    backend: str = None             # "lite" | "full" | "auto" | None (env default)
    # --- legacy fields (ignored by the tiled engine; kept so service.py / app_gradio
    #     don't break). Detail now comes from tiling, not these. ---
    normals: str = "marigold"
    facial_detail: float = 0.0
    depth_smooth: float = 0.0
    depth_compress: float = 1.0
    refine: float = 0.0
    tiling: bool = True


def generate_relief(image_path, out_dir, params: ReliefParams = ReliefParams(),
                    backend=None):
    from backends import get_backend
    be = get_backend(backend or getattr(params, "backend", None))

    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    image = Image.open(image_path).convert("RGB")

    # 1. TILED high-res depth (the detail lives here). Cached on (image, model,
    #    detail level) so the geometry sliders below re-tune instantly.
    tiling = params.tile_detail != "off"
    grids = _GRIDS.get(params.tile_detail, _GRIDS["medium"])
    try:
        ckey = (image_path, os.path.getmtime(image_path), params.depth_model,
                params.tile_detail, params.da3_variant, params.face_crop)
    except OSError:
        ckey = None
    cache = _RAW_CACHE.get(ckey, {}) if ckey is not None else {}
    if "depth" not in cache:
        cache["depth"] = be.estimate_depth(image, model=params.depth_model, tiling=tiling,
                                           grids=grids, da3_variant=params.da3_variant,
                                           face_crop=params.face_crop)
    depth = cache["depth"]
    if ckey is not None:
        _RAW_CACHE.clear(); _RAW_CACHE[ckey] = cache

    # 2. subject mask -> seat on a flat base. NO smoothing / refine / fusion / emboss.
    mask = be.remove_background(image) if params.flatten_bg else None
    height = rc.tiled_relief_heightmap(depth, mask, invert=params.invert,
                                       base=params.base_height, fig_span=params.fig_span,
                                       bg=(0.0 if params.black_bg else None))

    # 3. export 16-bit (no renormalize — keep the shallow base/range we built)
    height16 = rc.to_heightmap_16bit(height, normalize=False)
    png_path = out / "relief_heightmap.png"
    cv2.imwrite(str(png_path), height16)         # 16-bit PNG

    # 4. STL
    if params.make_solid:
        mesh = rc.heightmap_to_solid(height16, params.relief_depth_mm, params.pixel_mm)
    else:
        mesh = rc.heightmap_to_surface(height16, params.relief_depth_mm, params.pixel_mm)
    stl_path = out / "relief.stl"
    mesh.export(str(stl_path))

    # lightweight downsampled GLB for the in-browser 3D viewer
    preview_path = out / "preview.glb"
    rc.heightmap_to_preview(height16, params.relief_depth_mm,
                            params.pixel_mm).export(str(preview_path))

    return {"heightmap": str(png_path), "stl": str(stl_path),
            "preview3d": str(preview_path)}
