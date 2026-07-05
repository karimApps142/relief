"""features/text2img.py — Text -> Image via Krea-2-Turbo (GGUF) running in ComfyUI.

We don't run the 12B model in-process — ComfyUI (headless, with ComfyUI-GGUF) hosts
it, and this module drives it over the HTTP API. The API-format graph below is
hand-authored from the official Krea workflow's GGUF path (UnetLoaderGGUF -> KSampler
-> VAEDecode -> SaveImage), so no manual "Save (API Format)" export is needed.

Prereqs on the box (see docs/TEXT2IMG_KREA_PLAN.md): ComfyUI + ComfyUI-GGUF running
on :8188 with these files present:
  models/unet/krea2_turbo-Q4_K_M.gguf   (or another quant)
  models/text_encoders/qwen3vl_4b_fp8_scaled.safetensors
  models/vae/qwen_image_vae.safetensors
Point this module at it with COMFYUI_URL (default 127.0.0.1:8188).
"""
import random
from pathlib import Path

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from . import _lora


def _build_graph(prompt, width, height, steps, seed, gguf, loras=None):
    """Minimal API-format graph for the Krea-2-Turbo GGUF path (from the official
    Vantage workflow, with the UI-only rgthree helper nodes dropped). Any custom LoRAs are
    chained onto the model line via LoraLoaderModelOnly nodes (each with its own strength)."""
    graph = {
        "16": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": gguf}},
        "18": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "4":  {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["18", 0]}},
        "8":  {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "10": {"class_type": "EmptyLatentImage", "inputs": {
            "width": int(width), "height": int(height), "batch_size": 1}},
        "2":  {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": 1.0,
            "sampler_name": "er_sde", "scheduler": "simple", "denoise": 1.0,
            "model": ["16", 0], "positive": ["6", 0], "negative": ["8", 0],
            "latent_image": ["10", 0]}},
        "3":  {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["4", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"filename_prefix": "krea2/i", "images": ["3", 0]}},
    }
    graph["2"]["inputs"]["model"] = _lora.model_ref_with_loras(graph, ["16", 0], loras)
    return graph


class Text2ImgFeature(Feature):
    id = "text2img"
    name = "Text → Image"
    description = "Generate an image from a prompt with Krea-2-Turbo (GGUF, via ComfyUI)."
    needs_comfy = True
    engine = "comfy"
    icon = "text"
    est_runtime = "~5–20 s"
    vram = "~9–10 GB"
    output_kinds = ["Image PNG"]
    inputs = []                                          # no image upload; prompt is a param
    params = [
        ParamSpec("prompt", "text", "", "Prompt", placeholder="Describe what to generate…"),
        ParamSpec("width", "number", 1024, "Width", 512, 2048, 64, control="slider", suffix=" px"),
        ParamSpec("height", "number", 1024, "Height", 512, 2048, 64, control="slider", suffix=" px"),
        ParamSpec("quant", "select", "Q4_K_M", "Quantization", control="seg", group="advanced",
                  help="Quality vs VRAM — higher is heavier.",
                  choices=[{"value": "Q3_K_M", "label": "Q3"}, {"value": "Q4_K_M", "label": "Q4"},
                           {"value": "Q5_K_M", "label": "Q5"}, {"value": "Q6_K", "label": "Q6"}]),
        ParamSpec("steps", "number", 8, "Steps", 4, 20, 1, control="slider", group="advanced",
                  help="Turbo is tuned for 8 steps."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random each run."),
        ParamSpec("loras", "lora", [], "LoRAs", control="lora", group="advanced",
                  help="Stack one or more custom Krea-2 LoRAs, each with its own strength. "
                       "Drop a .safetensors file to add it to the list."),
    ]

    def run(self, inputs, params, out_dir):
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        graph = _build_graph(prompt=params.get("prompt", ""),
                             width=params["width"], height=params["height"],
                             steps=params["steps"], seed=seed,
                             gguf=f"krea2_turbo-{params['quant']}.gguf",
                             loras=params.get("loras"))
        png = ComfyUIClient().generate(graph)
        out = Path(out_dir) / "text2img.png"
        out.write_bytes(png)
        return {"image": str(out)}
