"""features/depthmap.py — export the raw depth + surface-normal maps (no relief/STL).

Local utility: runs the same tiled depth (and Sapiens/Marigold normals) the relief uses,
but exports the maps directly — a 16-bit depth/heightmap (carve-ready, ingestible by
Carveco/Vectric/etc.), an 8-bit preview, and the normal map. Reuses the relief models;
no ComfyUI, no extra downloads.
"""
from pathlib import Path
import numpy as np
from PIL import Image

from .base import Feature, ParamSpec


class DepthMapFeature(Feature):
    id = "depthmap"
    name = "Depth & Normal"
    description = "Export the raw depth map (16-bit, carve-ready) + a surface-normal map."
    inputs = ["image"]
    engine = "local"
    icon = "layers"
    est_runtime = "~5 s – 2 min"
    vram = "~2–4 GB"
    output_kinds = ["Depth 16-bit PNG", "Preview", "Normal PNG"]
    params = [
        ParamSpec("depth_model", "select", "depth-anything", "Depth model", control="seg",
                  choices=[{"value": "depth-anything", "label": "Depth-Anything"},
                           {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("tile_detail", "select", "medium", "Tile detail",
                  choices=[{"value": "off", "label": "Off"}, {"value": "low", "label": "Low"},
                           {"value": "medium", "label": "Medium"}, {"value": "high", "label": "High"}]),
        ParamSpec("face_crop", "bool", True, "Face crop"),
        ParamSpec("normals", "bool", True, "Include normal map"),
        ParamSpec("normal_source", "select", "sapiens", "Normal source", control="seg",
                  depends_on={"param": "normals", "value": True},
                  choices=[{"value": "sapiens", "label": "Sapiens"}, {"value": "marigold", "label": "Marigold"}]),
        ParamSpec("invert", "bool", False, "Invert depth", group="advanced",
                  help="Flip near/far. Default: brighter = nearer/higher."),
    ]

    def run(self, inputs, params, out_dir):
        from backends import get_backend
        from pipeline import _GRIDS
        import cv2
        be = get_backend("auto")
        image = Image.open(inputs["image"]).convert("RGB")
        td = params.get("tile_detail", "medium")
        depth = be.estimate_depth(image, model=params["depth_model"], tiling=(td != "off"),
                                  grids=_GRIDS.get(td, _GRIDS["medium"]), face_crop=params.get("face_crop", True))
        d = depth.astype(np.float32)
        lo, hi = np.percentile(d, [1, 99])
        d = np.clip((d - lo) / (hi - lo + 1e-8), 0.0, 1.0)
        if params.get("invert"):
            d = 1.0 - d
        out = Path(out_dir)
        cv2.imwrite(str(out / "depth_16bit.png"), (d * 65535).astype(np.uint16))   # carve-ready
        cv2.imwrite(str(out / "depth_preview.png"), (d * 255).astype(np.uint8))     # viewable
        arts = {"depth_16bit": str(out / "depth_16bit.png"), "depth_preview": str(out / "depth_preview.png")}
        if params.get("normals", True):
            n = np.clip(np.asarray(be.estimate_normals(image, which=params.get("normal_source", "sapiens")),
                                   np.float32), 0.0, 1.0)
            Image.fromarray((n * 255).astype(np.uint8)).save(out / "normal.png")
            arts["normal"] = str(out / "normal.png")
        return arts
