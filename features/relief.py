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
    output_kinds = ["Heightmap PNG", "Heat map", "3D preview GLB", "STL mesh"]
    params = [
        ParamSpec("depth_model", "select", "depth-anything", "Depth model", control="seg",
                  help="Monocular-depth model that estimates 3D shape from one photo.",
                  choices=[{"value": "depth-anything", "label": "Depth-Anything"},
                           {"value": "depth-anything-3", "label": "DA3"},
                           {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("tile_detail", "select", "medium", "Tile detail",
                  help="Finer tiling recovers facial detail. Off = 1 pass, Max = 144 tiles (slower).",
                  choices=[{"value": "off", "label": "Off · 1 pass"}, {"value": "low", "label": "Low · 9"},
                           {"value": "medium", "label": "Medium · 36"}, {"value": "high", "label": "High · 64"},
                           {"value": "ultra", "label": "Ultra · 100"}, {"value": "max", "label": "Max · 144"}]),
        ParamSpec("face_crop", "bool", True, "Face crop",
                  help="Auto-detect the face and concentrate detail there."),
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
        ParamSpec("surface_detail", "number", 0.0, "Surface detail", 0.0, 1.5, 0.05, control="slider",
                  help="Inject fine, EDGE-AWARE line detail (hair strands, fabric, feature lines) from the "
                       "photo. Carves only along real lines and leaves flat areas clean — 0 = smooth depth "
                       "only. Try ~0.4 for portraits."),
        ParamSpec("surface_smooth", "number", 0.3, "Surface polish", 0.0, 1.0, 0.05, control="slider",
                  help="Edge-preserving polish that removes grainy 'sandpaper' noise while keeping grooves "
                       "and feature lines crisp — for a clean, neat surface. 0 = off; raise for a cleaner "
                       "carve (too high softens fine lines)."),
        ParamSpec("colormap", "select", "turbo", "Heat-map view", control="seg",
                  help="Also render a colour 'surface heat map' of the relief (PNG + 3D). Visualization "
                       "only — the grayscale heightmap and STL are unchanged. Off skips it.",
                  choices=[{"value": "off", "label": "Off"}, {"value": "turbo", "label": "Turbo"},
                           {"value": "inferno", "label": "Inferno"}, {"value": "viridis", "label": "Viridis"},
                           {"value": "magma", "label": "Magma"}]),
        ParamSpec("black_bg", "bool", True, "Black background", group="advanced",
                  help="Background sits at zero height vs a mid-gray plate."),
        ParamSpec("invert", "bool", False, "Invert depth", group="advanced",
                  help="Flip near/far (raised ↔ recessed)."),
        ParamSpec("flatten_bg", "bool", True, "Flatten background", group="advanced",
                  help="Push the background to a flat plane."),
        ParamSpec("make_solid", "bool", False, "Make solid", group="advanced",
                  help="Watertight solid (3D printing) vs surface (CNC)."),
        ParamSpec("normal_detail", "bool", False, "Normal detail (fuse facial relief)", group="advanced",
                  help="Estimate a surface-normal map and fuse its crisp facial detail (eyes/hair/lips) "
                       "onto the depth. Sharper than depth alone; adds a slower normal pass."),
        ParamSpec("normal_gain", "number", 0.7, "Detail strength", 0.0, 1.5, 0.05, control="slider",
                  group="advanced", depends_on={"param": "normal_detail", "value": True},
                  help="How strongly the normal-derived relief stands out."),
        ParamSpec("normal_source", "select", "sapiens", "Normal source", control="seg",
                  group="advanced", depends_on={"param": "normal_detail", "value": True},
                  help="Sapiens = human-specialist (sharpest faces/hair); Marigold = general.",
                  choices=[{"value": "sapiens", "label": "Sapiens"},
                           {"value": "marigold", "label": "Marigold"}]),
    ]

    def run(self, inputs, params, out_dir):
        from pipeline import generate_relief, ReliefParams
        fields = ReliefParams.__dataclass_fields__
        rp = ReliefParams(**{k: v for k, v in params.items() if k in fields})
        return generate_relief(inputs["image"], str(out_dir), rp, backend="auto")
