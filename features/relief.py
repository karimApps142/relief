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
    engine = "local"
    icon = "box"
    est_runtime = "~5 s – 4 min"
    vram = "~2–4 GB"
    output_kinds = ["Heightmap PNG", "STL mesh"]
    params = [
        ParamSpec("depth_model", "select", "depth-anything", "Depth model", control="seg",
                  help="Monocular-depth model that estimates 3D shape from one photo.",
                  choices=[{"value": "depth-anything", "label": "Depth-Anything"},
                           {"value": "depth-anything-3", "label": "DA3"},
                           {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("tile_detail", "select", "medium", "Tile detail",
                  help="Finer tiling recovers facial detail. Off = 1 pass, Max = 144 tiles (slower). "
                       "Each tile now runs at higher resolution for a crisper carve.",
                  choices=[{"value": "off", "label": "Off · 1 pass"}, {"value": "low", "label": "Low · 9"},
                           {"value": "medium", "label": "Medium · 36"}, {"value": "high", "label": "High · 64"},
                           {"value": "ultra", "label": "Ultra · 100"}, {"value": "max", "label": "Max · 144"}]),
        ParamSpec("face_crop", "bool", True, "Face crop",
                  help="Auto-detect the face and concentrate the tile budget there (sharper + faster)."),
        ParamSpec("da3_variant", "select", "DA3MONO-LARGE", "DA3 variant",
                  help="Model size — only for Depth-Anything-3.",
                  depends_on={"param": "depth_model", "value": "depth-anything-3"},
                  choices=[{"value": "DA3MONO-LARGE", "label": "DA3MONO-LARGE"},
                           {"value": "DA3-LARGE", "label": "DA3-LARGE"}, {"value": "DA3-GIANT", "label": "DA3-GIANT"},
                           {"value": "DA3-BASE", "label": "DA3-BASE"}, {"value": "DA3-SMALL", "label": "DA3-SMALL"}]),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth", 2, 20, 0.5, control="slider",
                  suffix=" mm", help="Physical carve depth of the relief."),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size", 0.02, 0.5, 0.01, control="slider",
                  suffix=" mm/px", help="Real-world size of one pixel → sets STL dimensions."),
    ]

    def run(self, inputs, params, out_dir):
        from pipeline import generate_relief, ReliefParams
        fields = ReliefParams.__dataclass_fields__
        rp = ReliefParams(**{k: v for k, v in params.items() if k in fields})
        rp.colormap = "off"        # heat-map view removed from this feature
        rp.make_preview = False    # 3D render removed — heightmap (16-bit PNG) + STL only
        rp.surface_smooth = 0.0    # no polish blur — the tiled depth IS the detail; the hidden
                                   # 0.3 bilateral (sigmaSpace ~5px) was softening the carve
        return generate_relief(inputs["image"], str(out_dir), rp, backend="auto")
