"""features/upscale.py — Image upscaling via an ESRGAN-style model in ComfyUI.

No diffusion model needed — just an upscale model in ComfyUI/models/upscale_models/
(e.g. 4x-UltraSharp.pth). Fast and light. Reuses the shared ComfyUI client.
"""
from pathlib import Path
from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient


def _build_graph(image_name, model_name):
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model_name}},
        "3": {"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": ["2", 0], "image": ["1", 0]}},
        "4": {"class_type": "SaveImage", "inputs": {"filename_prefix": "upscale/u", "images": ["3", 0]}},
    }


class UpscaleFeature(Feature):
    id = "upscale"
    name = "Upscale"
    description = "Upscale an image with an ESRGAN model (ComfyUI; no diffusion model)."
    needs_comfy = True
    engine = "comfy"
    icon = "upscale"
    est_runtime = "~2–8 s"
    vram = "~1–2 GB"
    output_kinds = ["Image PNG · ~4×"]
    inputs = ["image"]
    params = [
        ParamSpec("model_name", "select", "4x-UltraSharp.pth", "Upscale model",
                  help="ESRGAN upscaler (all ~4×).",
                  choices=[{"value": "4x-UltraSharp.pth", "label": "4x-UltraSharp"},
                           {"value": "RealESRGAN_x4plus.pth", "label": "RealESRGAN x4plus"},
                           {"value": "4x_foolhardy_Remacri.pth", "label": "4x Foolhardy Remacri"}]),
    ]

    def run(self, inputs, params, out_dir):
        import comfy_manager
        model = params["model_name"]
        # fetch the chosen ESRGAN model on demand if it isn't on the box yet (~64 MB), so
        # picking Remacri/RealESRGAN works without a separate Download step. ComfyUI rescans
        # the upscale_models folder (dir mtime changes) and sees the new file on this run.
        comfy_manager.ensure_upscaler(model)
        client = ComfyUIClient()
        name = client.upload_image(inputs["image"])
        out = Path(out_dir) / "upscale.png"
        out.write_bytes(client.generate(_build_graph(name, model)))
        return {"image": str(out)}
