"""features/depthmap.py — depth + surface-normal maps, a clean relief heightmap, and a 3D preview.

Runs the same tiled depth (and Sapiens/Marigold normals) the relief uses, then:
  • masks the subject (BiRefNet) so the background is pure black,
  • fuses the surface-normal's crisp detail (eyes/hair/lips) onto the depth's global form,
  • exports a carve-ready 16-bit depth/heightmap (black bg, grayscale surface), an 8-bit
    preview, the normal map, AND a lightweight GLB the UI renders as an interactive 3D view.
Reuses the relief models + relief_core math; no ComfyUI, no extra downloads.
"""
from pathlib import Path
import numpy as np
from PIL import Image

from .base import Feature, ParamSpec


class DepthMapFeature(Feature):
    id = "depthmap"
    name = "Depth & Normal"
    description = "Masked depth heightmap (16-bit, black-bg, carve-ready) + normal map + interactive 3D preview."
    inputs = ["image"]
    engine = "local"
    icon = "layers"
    est_runtime = "~10 s – 3 min"
    vram = "~2–4 GB"
    output_kinds = ["Depth 16-bit PNG", "3D preview GLB", "Normal PNG"]
    params = [
        ParamSpec("depth_model", "select", "depth-anything", "Depth model", control="seg",
                  choices=[{"value": "depth-anything", "label": "Depth-Anything"},
                           {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("tile_detail", "select", "medium", "Tile detail",
                  choices=[{"value": "off", "label": "Off"}, {"value": "low", "label": "Low"},
                           {"value": "medium", "label": "Medium"}, {"value": "high", "label": "High"}]),
        ParamSpec("face_crop", "bool", True, "Face crop"),
        ParamSpec("mask_background", "bool", True, "Black background",
                  help="Cut out the subject (BiRefNet) and set the background to pure black."),
        ParamSpec("normals", "bool", True, "Fuse normal detail",
                  help="Estimate a surface-normal map and fuse its crisp detail (eyes/hair/lips) into the depth."),
        ParamSpec("normal_source", "select", "marigold", "Normal source", control="seg",
                  depends_on={"param": "normals", "value": True},
                  help="Marigold = general (cleaner background); Sapiens = human-specialist (sharpest faces).",
                  choices=[{"value": "marigold", "label": "Marigold"}, {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("normal_gain", "number", 0.7, "Detail strength", 0.0, 1.5, 0.05, control="slider",
                  depends_on={"param": "normals", "value": True},
                  help="How strongly the normal-derived detail stands out in the depth."),
        ParamSpec("relief_depth_mm", "number", 8.0, "3D depth", 2, 20, 0.5, control="slider", suffix=" mm",
                  group="advanced", help="Z height of the interactive 3D preview."),
        ParamSpec("invert", "bool", False, "Invert depth", group="advanced",
                  help="Flip near/far. Default: brighter = nearer/higher."),
    ]

    def run(self, inputs, params, out_dir):
        from backends import get_backend
        from pipeline import _GRIDS
        import relief_core as rc
        import cv2
        be = get_backend("auto")
        image = Image.open(inputs["image"]).convert("RGB")
        out = Path(out_dir)

        # 1. tiled high-res depth (global form lives here)
        td = params.get("tile_detail", "medium")
        depth = be.estimate_depth(image, model=params["depth_model"], tiling=(td != "off"),
                                  grids=_GRIDS.get(td, _GRIDS["medium"]), face_crop=params.get("face_crop", True))

        # 2. optional surface normals (their high-frequency detail gets fused into the depth)
        use_normals = params.get("normals", True)
        normal_map = None
        if use_normals:
            try:
                normal_map = np.clip(np.asarray(
                    be.estimate_normals(image, which=params.get("normal_source", "marigold")), np.float32), 0.0, 1.0)
            except Exception as e:                       # graceful: depth-only if normals unavailable
                print(f"[depthmap] normals skipped ({e}) — depth only")

        # 3. subject mask -> black background. Resized to the depth grid so the seat lands.
        mask = None
        if params.get("mask_background", True):
            mask = be.remove_background(image)
            if mask.shape[:2] != depth.shape[:2]:
                mask = cv2.resize(mask, (depth.shape[1], depth.shape[0]))

        # 4. fuse depth (form) + normals (detail), seat on a black plate -> the relief-style
        #    "black background + grayscale surface" heightmap. base>0 keeps the figure off pure
        #    black so the silhouette stays crisp; fig_span uses the rest of the range.
        height = rc.tiled_relief_heightmap(
            depth, mask, invert=params.get("invert", False), base=0.12, fig_span=0.88,
            bg=(0.0 if mask is not None else None),
            normal_map=(normal_map if use_normals else None),
            normal_detail=params.get("normal_gain", 0.7))
        height16 = rc.to_heightmap_16bit(height, normalize=False)

        cv2.imwrite(str(out / "depth_16bit.png"), height16)                    # carve-ready
        cv2.imwrite(str(out / "depth_preview.png"), (height16 >> 8).astype(np.uint8))  # 8-bit viewable
        arts = {"depth_16bit": str(out / "depth_16bit.png"),
                "depth_preview": str(out / "depth_preview.png")}

        # 5. normal map export — background neutralised when masking (kills the noisy bg)
        if use_normals and normal_map is not None:
            n = normal_map.copy()
            if mask is not None and mask.shape[:2] == n.shape[:2]:
                n[mask <= 0.5] = (0.5, 0.5, 1.0)         # flat, camera-facing normal on the background
            Image.fromarray((np.clip(n, 0.0, 1.0) * 255).astype(np.uint8)).save(out / "normal.png")
            arts["normal"] = str(out / "normal.png")

        # 6. interactive 3D preview (GLB) — auto-rendered by the UI's <model-viewer>
        preview = out / "preview.glb"
        rc.heightmap_to_preview(height16, z_scale_mm=float(params.get("relief_depth_mm", 8.0)),
                                pixel_mm=0.1).export(str(preview))
        arts["preview3d"] = str(preview)
        return arts
