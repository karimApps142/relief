"""features/relief.py — image -> smooth depth-map relief heightmap + STL.

Thin wrapper around the existing pipeline.generate_relief (no math change): it
exposes the relief params as a UI schema and adapts run() to the Feature contract.
"""
from pathlib import Path
from .base import Feature, ParamSpec


class ReliefFeature(Feature):
    id = "relief"
    name = "Image → Relief"
    description = ("High-resolution TILED monocular-depth heightmap (16-bit PNG) + STL. "
                   "Tiling recovers facial detail a single depth pass smooths away.")
    inputs = ["image"]
    params = [
        ParamSpec("depth_model", "select", "depth-anything", "Depth model",
                  choices=["depth-anything", "depth-anything-3", "sapiens"]),
        ParamSpec("tile_detail", "select", "medium", "Facial detail (tiling — higher = slower)",
                  choices=["off", "low", "medium", "high", "ultra", "max"]),
        ParamSpec("face_crop", "bool", True, "Auto face-crop (focus detail on the face)"),
        ParamSpec("da3_variant", "select", "DA3MONO-LARGE", "DA3 variant (when depth-anything-3)",
                  choices=["DA3MONO-LARGE", "DA3-LARGE", "DA3-GIANT", "DA3-BASE", "DA3-SMALL"]),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth (mm)", 2, 20, 0.5),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size (mm)", 0.02, 0.5, 0.01),
        ParamSpec("black_bg", "bool", True, "Black background (vs mid-gray plate)"),
        ParamSpec("invert", "bool", False, "Invert (flip near/far)"),
        ParamSpec("flatten_bg", "bool", True, "Flatten background"),
        ParamSpec("make_solid", "bool", False, "Watertight solid (3D print)"),
    ]

    def run(self, inputs, params, out_dir):
        from pipeline import generate_relief, ReliefParams
        fields = ReliefParams.__dataclass_fields__
        rp = ReliefParams(**{k: v for k, v in params.items() if k in fields})
        return generate_relief(inputs["image"], str(out_dir), rp, backend="auto")
