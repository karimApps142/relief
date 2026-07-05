"""features/img2img.py — Image -> Image with Krea-2-Turbo (GGUF) via ComfyUI.

Encodes the uploaded image to a latent and re-diffuses it under a prompt at partial
denoise (lower = closer to the original). Same loaders/sampler as text2img; the only
difference is VAEEncode(LoadImage) feeding the KSampler's latent instead of an empty one.
"""
from pathlib import Path
from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from . import _lora


def _build_graph(image_name, prompt, denoise, steps, seed, gguf, loras=None):
    graph = {
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
    graph["2"]["inputs"]["model"] = _lora.model_ref_with_loras(graph, ["16", 0], loras)
    return graph


class Img2ImgFeature(Feature):
    id = "img2img"
    name = "Image → Image"
    description = "Transform an image with a prompt (Krea-2-Turbo img2img, via ComfyUI)."
    needs_comfy = True
    engine = "comfy"
    icon = "image"
    est_runtime = "~5–20 s"
    vram = "~9–10 GB"
    output_kinds = ["Image PNG"]
    inputs = ["image"]
    params = [
        ParamSpec("prompt", "text", "", "Prompt", placeholder="Describe how to transform it…"),
        ParamSpec("denoise", "number", 0.6, "Denoise strength", 0.1, 1.0, 0.05, control="slider",
                  help="Lower stays close to the original; higher reinvents it."),
        ParamSpec("width", "number", 1024, "Width", 512, 2048, 64, control="slider", suffix=" px",
                  help="Output is scaled to fit within Width×Height (aspect ratio preserved)."),
        ParamSpec("height", "number", 1024, "Height", 512, 2048, 64, control="slider", suffix=" px",
                  help="Output is scaled to fit within Width×Height (aspect ratio preserved)."),
        ParamSpec("quant", "select", "Q4_K_M", "Quantization", control="seg", group="advanced",
                  help="Quality vs VRAM.",
                  choices=[{"value": "Q3_K_M", "label": "Q3"}, {"value": "Q4_K_M", "label": "Q4"},
                           {"value": "Q5_K_M", "label": "Q5"}, {"value": "Q6_K", "label": "Q6"}]),
        ParamSpec("steps", "number", 8, "Steps", 4, 20, 1, control="slider", group="advanced"),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random."),
        ParamSpec("clarity_upscale", "bool", False, "Clarity upscale (Balanced)", control="switch",
                  group="advanced",
                  help="After transforming, run Clarity Upscale (Balanced) on the result — adds fine "
                       "detail and 2× size. Needs the Clarity models installed (see the Clarity tab)."),
        ParamSpec("loras", "lora", [], "LoRAs", control="lora", group="advanced",
                  help="Stack one or more custom Krea-2 LoRAs, each with its own strength. "
                       "Drop a .safetensors file to add it to the list."),
    ]

    def run(self, inputs, params, out_dir):
        import random
        from PIL import Image
        client = ComfyUIClient()
        out_dir = Path(out_dir)

        # scale the source to fit within Width×Height (aspect preserved), snapped to /16 for the
        # VAE — this sets the img2img working/output resolution (like text2img's width/height).
        src = Image.open(inputs["image"]).convert("RGB")
        W, H = int(params.get("width", 1024)), int(params.get("height", 1024))
        f = min(W / src.width, H / src.height)
        nw = max(64, int(round(src.width * f)) // 16 * 16)
        nh = max(64, int(round(src.height * f)) // 16 * 16)
        tmp = out_dir / "img2img_input.png"
        src.resize((nw, nh), Image.LANCZOS).save(tmp)
        name = client.upload_image(str(tmp))

        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        graph = _build_graph(name, params.get("prompt", ""), params["denoise"],
                             params["steps"], seed, f"krea2_turbo-{params['quant']}.gguf",
                             loras=params.get("loras"))
        out = out_dir / "img2img.png"
        out.write_bytes(client.generate(graph))

        # optional finishing pass: reuse the Clarity feature (Balanced preset) on the result.
        if params.get("clarity_upscale"):
            from .clarity import ClarityFeature
            cf = ClarityFeature()
            return cf.run({"image": str(out)}, cf.coerce({}), out_dir)   # SD1.5 tile-CN detail upscale
        return {"image": str(out)}
