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

# raw depth + normals cache: geometry/refine/facial-detail sliders re-tune without
# re-invoking the GPU. Keyed on (image, model, tiling); holds only the most recent.
_RAW_CACHE = {}


@dataclass
class ReliefParams:
    relief_depth_mm: float = 8.0     # physical Z height of the carve (mm)
    pixel_mm: float = 0.1            # mm per pixel (plate size)
    depth_model: str = "sapiens"    # "sapiens" | "depth-anything-3" | "depth-anything"
    da3_variant: str = "DA3-LARGE"  # DA3 hub variant (when depth_model == depth-anything-3)
    invert: bool = False            # flip near<->far if the subject comes out sunken
    facial_detail: float = 0.7      # add surface-NORMAL facial detail (depth alone is featureless)
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

    # 1. raw depth (+ raw normal-integrated detail) — cached so the sliders below
    #    (incl. facial_detail) re-tune instantly without re-invoking the GPU models.
    try:
        ckey = (image_path, os.path.getmtime(image_path), params.depth_model, params.tiling)
    except OSError:
        ckey = None
    cache = _RAW_CACHE.get(ckey, {}) if ckey is not None else {}

    if "depth" not in cache:
        cache["depth"] = be.estimate_depth(image, model=params.depth_model,
                                           tiling=params.tiling, da3_variant=params.da3_variant)
    depth = cache["depth"]

    # surface-NORMAL facial detail (depth alone is smooth/featureless). Computed
    # once per image and cached. Unload the depth model first so two big models
    # don't co-reside on the 12 GB card.
    if params.facial_detail > 0 and "nh" not in cache:
        if getattr(be, "name", "") == "full":
            try:
                import models
                models.unload_all()
            except Exception:
                pass
        nm = be.estimate_normals(image, which="marigold")
        cache["nh"] = rc.integrate_normals(nm) if nm is not None else None

    if ckey is not None:
        _RAW_CACHE.clear(); _RAW_CACHE[ckey] = cache   # keep only the most recent image

    # 2. fuse depth (form) + normal detail (face), then mask for the flat base
    field = depth
    if params.facial_detail > 0 and cache.get("nh") is not None:
        field = rc.fuse_depth_normals(depth, cache["nh"], detail=params.facial_detail)
    mask = be.remove_background(image) if params.flatten_bg else None

    # 3. -> clean relief heightmap; guided refine snaps edges to the photo
    height = rc.depth_to_heightmap(field, mask, luma=luma,
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

    # lightweight downsampled GLB for the in-browser 3D viewer
    preview_path = out / "preview.glb"
    rc.heightmap_to_preview(height16, params.relief_depth_mm,
                            params.pixel_mm).export(str(preview_path))

    return {"heightmap": str(png_path), "stl": str(stl_path),
            "preview3d": str(preview_path)}
