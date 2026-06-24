"""features/img2img.py — Image -> Image with Krea-2-Turbo (GGUF) via ComfyUI.

Encodes the uploaded image to a latent and re-diffuses it under a prompt at partial
denoise (lower = closer to the original). Same loaders/sampler as text2img; the only
difference is VAEEncode(LoadImage) feeding the KSampler's latent instead of an empty one.
"""
from pathlib import Path
from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient


def _build_graph(image_name, prompt, denoise, steps, seed, gguf):
    return {
        "16": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": gguf}},
        "18": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "4":  {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["18", 0]}},
        "8":  {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "12": {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["4", 0]}},
        "2":  {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": 1.0,
            "sampler_name": "er_sde", "scheduler": "simple", "denoise": float(denoise),
            "model": ["16", 0], "positive": ["6", 0], "negative": ["8", 0],
            "latent_image": ["12", 0]}},
        "3":  {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["4", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"filename_prefix": "krea2/i2i", "images": ["3", 0]}},
    }


class Img2ImgFeature(Feature):
    id = "img2img"
    name = "Image → Image"
    description = "Transform an image with a prompt (Krea-2-Turbo img2img, via ComfyUI)."
    needs_comfy = True
    inputs = ["image"]
    params = [
        ParamSpec("prompt", "text", "", "Prompt"),
        ParamSpec("denoise", "number", 0.6, "Strength (lower = closer to original)", 0.1, 1.0, 0.05),
        ParamSpec("quant", "select", "Q4_K_M", "Model quant (VRAM)",
                  choices=["Q3_K_M", "Q4_K_M", "Q5_K_M", "Q6_K"]),
        ParamSpec("steps", "number", 8, "Steps", 4, 20, 1),
        ParamSpec("seed", "number", 0, "Seed (0 = random)", 0, 2_147_483_647, 1),
    ]

    def run(self, inputs, params, out_dir):
        import random
        client = ComfyUIClient()
        name = client.upload_image(inputs["image"])
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        graph = _build_graph(name, params.get("prompt", ""), params["denoise"],
                             params["steps"], seed, f"krea2_turbo-{params['quant']}.gguf")
        out = Path(out_dir) / "img2img.png"
        out.write_bytes(client.generate(graph))
        return {"image": str(out)}
