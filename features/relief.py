"""features/relief.py — image -> smooth depth-map relief heightmap + STL.

Thin wrapper around the existing pipeline.generate_relief (no math change): it
exposes the relief params as a UI schema and adapts run() to the Feature contract.
"""
from pathlib import Path
from .base import Feature, ParamSpec


class ReliefFeature(Feature):
    id = "relief"
    name = "Image → Relief"
    description = "Smooth monocular-depth heightmap (16-bit PNG) + STL from a photo."
    inputs = ["image"]
    params = [
        ParamSpec("depth_model", "select", "sapiens", "Depth model",
                  choices=["sapiens", "depth-anything-3", "depth-anything"]),
        ParamSpec("da3_variant", "select", "DA3-LARGE", "DA3 variant (when depth-anything-3)",
                  choices=["DA3MONO-LARGE", "DA3-LARGE", "DA3-LARGE-1.1",
                           "DA3-GIANT", "DA3-GIANT-1.1", "DA3-BASE", "DA3-SMALL"]),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth (mm)", 2, 20, 0.5),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size (mm)", 0.02, 0.5, 0.01),
        ParamSpec("refine", "number", 0.6, "Edge refine (snap to photo)", 0.0, 1.0, 0.05),
        ParamSpec("depth_smooth", "number", 0.5, "Depth smoothing", 0.0, 1.0, 0.05),
        ParamSpec("depth_compress", "number", 1.0, "Depth range (lower=flatter)", 0.4, 1.5, 0.05),
        ParamSpec("invert", "bool", False, "Invert (flip near/far)"),
        ParamSpec("flatten_bg", "bool", True, "Flatten background"),
        ParamSpec("tiling", "bool", False, "Hi-res tiling (depth-anything; slow)"),
        ParamSpec("make_solid", "bool", False, "Watertight solid (3D print)"),
    ]

    def run(self, inputs, params, out_dir):
        from pipeline import generate_relief, ReliefParams
        fields = ReliefParams.__dataclass_fields__
        rp = ReliefParams(**{k: v for k, v in params.items() if k in fields})
        return generate_relief(inputs["image"], str(out_dir), rp, backend="auto")
