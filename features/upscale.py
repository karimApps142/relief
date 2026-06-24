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
    inputs = ["image"]
    params = [
        ParamSpec("model_name", "select", "4x-UltraSharp.pth", "Upscale model",
                  choices=["4x-UltraSharp.pth", "RealESRGAN_x4plus.pth", "4x_foolhardy_Remacri.pth"]),
    ]

    def run(self, inputs, params, out_dir):
        client = ComfyUIClient()
        name = client.upload_image(inputs["image"])
        out = Path(out_dir) / "upscale.png"
        out.write_bytes(client.generate(_build_graph(name, params["model_name"])))
        return {"image": str(out)}
