"""features/relight.py — relight / delight a portrait via IC-Light (SD1.5) in ComfyUI.

Foreground-conditioned (FC) relighting: keep the subject, change the lighting. The
**Even** preset flattens directional shadows (delighting) — a clean intermediate to feed
the relief depth pass, since baked shadows otherwise get carved as false geometry
(the lighting-as-geometry failure mode). Also a standalone relight tool.

Needs the IC-Light node (kijai/ComfyUI-IC-Light) + iclight_sd15_fc.safetensors + an SD1.5
checkpoint — provisioned by comfy_manager's install/download.
"""
import random
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

_SD15 = "v1-5-pruned-emaonly-fp16.safetensors"
_ICLIGHT = "IC-Light/iclight_sd15_fc.safetensors"   # relative to models/unet/

# lighting preset → prompt (IC-Light FC is prompt-driven). 'even' = delight for relief.
_PRESETS = {
    "even":  "soft even studio lighting, neutral diffuse illumination, no harsh shadows, flat lighting",
    "front": "bright frontal lighting, evenly lit face, soft fill light",
    "left":  "soft directional light from the left, gentle shadow on the right",
    "right": "soft directional light from the right, gentle shadow on the left",
    "top":   "soft light from above, gentle downward illumination",
}


def _build_graph(image_name, prompt, steps, seed):
    return {
        "1":  {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": _SD15}},
        "2":  {"class_type": "LoadAndApplyICLightUnet", "inputs": {"model": ["1", 0], "model_path": _ICLIGHT}},
        "3":  {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "4":  {"class_type": "VAEEncode", "inputs": {"pixels": ["3", 0], "vae": ["1", 2]}},
        "5":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {
            "text": "harsh shadow, specular highlight, lowres, deformed, bad quality", "clip": ["1", 1]}},
        "7":  {"class_type": "ICLightConditioning", "inputs": {
            "positive": ["5", 0], "negative": ["6", 0], "vae": ["1", 2],
            "foreground": ["4", 0], "multiplier": 0.182}},
        "8":  {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": 2.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
            "model": ["2", 0], "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2]}},
        "9":  {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["1", 2]}},
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": "relight/r", "images": ["9", 0]}},
    }


class RelightFeature(Feature):
    id = "relight"
    name = "Relight"
    description = ("Relight or delight a portrait (IC-Light). 'Even' flattens shadows — a clean "
                  "intermediate before relief (baked shadows carve as false depth).")
    needs_comfy = True
    inputs = ["image"]
    engine = "comfy"
    icon = "image"
    est_runtime = "~10–30 s"
    vram = "~4–6 GB"
    output_kinds = ["Relit image"]
    params = [
        ParamSpec("lighting", "select", "even", "Lighting", control="seg",
                  help="Even = delight (flat, shadow-free) for relief; others add soft direction.",
                  choices=[{"value": "even", "label": "Even (delight)"}, {"value": "front", "label": "Front"},
                           {"value": "left", "label": "Left"}, {"value": "right", "label": "Right"},
                           {"value": "top", "label": "Top"}]),
        ParamSpec("prompt", "text", "", "Extra prompt (optional)",
                  help="Appended to the lighting preset, e.g. 'warm tone'."),
        ParamSpec("steps", "number", 25, "Steps", 8, 40, 1, control="slider"),
        ParamSpec("seed", "number", 0, "Seed (0 = random)", 0, 2_147_483_647, 1, control="stepper"),
    ]

    def run(self, inputs, params, out_dir):
        client = ComfyUIClient()
        # SD1.5/IC-Light is happiest ≤1024 px; snap to a multiple of 8 before upload.
        src = Image.open(inputs["image"]).convert("RGB")
        m = max(src.size)
        scale = 1024 / m if m > 1024 else 1.0
        w = max(64, int(src.width * scale) // 8 * 8)
        h = max(64, int(src.height * scale) // 8 * 8)
        src = src.resize((w, h))
        tmp = Path(out_dir) / "relight_input.png"; src.save(tmp)
        name = client.upload_image(str(tmp))

        base = _PRESETS.get(params.get("lighting", "even"), _PRESETS["even"])
        extra = (params.get("prompt") or "").strip()
        prompt = f"{base}, {extra}" if extra else base
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        out = Path(out_dir) / "relight.png"
        out.write_bytes(client.generate(_build_graph(name, prompt, params["steps"], seed), label="relight"))
        return {"image": str(out)}
