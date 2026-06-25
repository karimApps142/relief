"""features/portrait_relief.py — one-click 'Pro' relief: delight → (upscale) → relief.

Operationalizes the relief-quality research as a single button:
  1. DELIGHT the photo (IC-Light 'even') so baked shadows aren't carved as false geometry,
  2. optionally UPSCALE to recover resolution (the SD1.5 delight caps at ~1024),
  3. run the local depth + NORMAL-FUSION relief (Sapiens normals) for crisp faces.

Cross-engine: steps 1–2 run in ComfyUI; step 3 runs locally. ComfyUI's VRAM is freed
before the local depth/normal models load, so the whole thing sequences within 12 GB.
"""
import random
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from .relight import _build_graph as _relight_graph, _PRESETS
from .upscale import _build_graph as _upscale_graph


def _prep_upload(client, image_path, out_dir, max_side=1024):
    """Resize to an SD1.5-friendly size (multiple of 8) and upload to ComfyUI."""
    src = Image.open(image_path).convert("RGB")
    m = max(src.size)
    scale = max_side / m if m > max_side else 1.0
    w = max(64, int(src.width * scale) // 8 * 8)
    h = max(64, int(src.height * scale) // 8 * 8)
    tmp = Path(out_dir) / "pr_input.png"
    src.resize((w, h)).save(tmp)
    return client.upload_image(str(tmp))


class PortraitReliefFeature(Feature):
    id = "portrait"
    name = "Portrait Relief"
    description = ("One-click Pro relief: delight (flatten shadows) → optional upscale → "
                  "depth + normal-fusion relief. Cleaner faces than relief alone.")
    needs_comfy = True
    inputs = ["image"]
    engine = "comfy"
    icon = "box"
    est_runtime = "~1–5 min"
    vram = "~6–10 GB"
    output_kinds = ["Heightmap PNG", "3D preview GLB", "STL mesh"]
    params = [
        ParamSpec("delight", "bool", True, "Delight first (flatten shadows)",
                  help="IC-Light 'even' relight removes directional shadows so they aren't carved "
                       "as false depth. Turn off to A/B against the raw photo."),
        ParamSpec("upscale", "bool", False, "Upscale before relief",
                  help="4x-upscale the delit image to recover resolution (the delight caps at ~1024). "
                       "Needs the upscaler model."),
        ParamSpec("depth_model", "select", "depth-anything", "Depth model", control="seg",
                  help="Low-frequency form. Normals (the crisp facial detail) always come from Sapiens.",
                  choices=[{"value": "depth-anything", "label": "Depth-Anything"},
                           {"value": "sapiens", "label": "Sapiens"}]),
        ParamSpec("tile_detail", "select", "high", "Tile detail",
                  choices=[{"value": "medium", "label": "Medium · 36"}, {"value": "high", "label": "High · 64"},
                           {"value": "ultra", "label": "Ultra · 100"}, {"value": "max", "label": "Max · 144"}]),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth", 2, 20, 0.5, control="slider", suffix=" mm"),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size", 0.02, 0.5, 0.01, control="slider", suffix=" mm/px"),
        ParamSpec("normal_gain", "number", 0.7, "Detail strength", 0.0, 1.5, 0.05, control="slider", group="advanced",
                  help="How strongly the Sapiens normal detail stands out."),
        ParamSpec("black_bg", "bool", True, "Black background", group="advanced"),
        ParamSpec("make_solid", "bool", False, "Make solid", group="advanced"),
    ]

    def run(self, inputs, params, out_dir):
        from pipeline import generate_relief, ReliefParams
        out = Path(out_dir)
        work = inputs["image"]
        artifacts = {}
        client = ComfyUIClient()

        # 1. delight (IC-Light 'even') — the clean intermediate the research calls for
        if params.get("delight", True):
            name = _prep_upload(client, work, out_dir)
            seed = random.randint(1, 2_147_483_647)
            png = client.generate(_relight_graph(name, _PRESETS["even"], 25, seed), label="portrait·delight")
            relit = out / "relit.png"; relit.write_bytes(png)
            artifacts["relit"] = str(relit); work = str(relit)

        # 2. optional upscale — recover resolution lost to the SD1.5 delight cap
        if params.get("upscale"):
            name = client.upload_image(work)
            png = client.generate(_upscale_graph(name, "4x-UltraSharp.pth"), label="portrait·upscale")
            up = out / "upscaled.png"; up.write_bytes(png); work = str(up)

        # 3. free ComfyUI VRAM before the local depth/normal models load (12 GB budget)
        client.free()

        # 4. local relief with depth + Sapiens-normal fusion
        rp = ReliefParams(
            depth_model=params["depth_model"], tile_detail=params["tile_detail"],
            relief_depth_mm=params["relief_depth_mm"], pixel_mm=params["pixel_mm"],
            normal_detail=True, normal_source="sapiens", normal_gain=params.get("normal_gain", 0.7),
            black_bg=params.get("black_bg", True), make_solid=params.get("make_solid", False),
            face_crop=True)
        artifacts.update(generate_relief(work, str(out_dir), rp, backend="auto"))
        return artifacts
