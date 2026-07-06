"""features/apply_texture.py — wrap a real texture/material photo onto an object or carving.

Two-image edit with Qwen-Image-Edit-2511: image1 = the OBJECT / CNC design (kept in shape),
image2 = a TEXTURE / material swatch photo. The model wraps the texture over the object's form
and relief, following its contours and lighting — a real material preview from your own sample
(wood, marble, stone, metal, fabric…), unlike the text-only 'apply_texture' LoRA.

Native multi-image reference (no LoRA required): both images feed both TextEncodeQwenImageEditPlus
nodes; the object is the sampling latent. Reuses the same GGUF models + 12 GB tricks as Image
Edit / Room Mockup. The LoRA stack is exposed so you can still add tarn59's apply_texture LoRA
(or others) for a stronger push.
"""
import random
from pathlib import Path

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from .image_edit import _UNET, _CLIP, _VAE, _LIGHTNING
from . import _lora


def _build_graph(object_name, texture_name, prompt, seed, lightning, steps, cfg, loras=None):
    """object = image1 (FluxKontextImageScale + VAEEncode sampling latent); texture = image2
    (raw reference). Both go into both edit encoders. User LoRAs chain after the Lightning LoRA."""
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": _UNET}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": _CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": _VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "7": {"class_type": "LoadImage", "inputs": {"image": object_name}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["7", 0]}},
        "15": {"class_type": "LoadImage", "inputs": {"image": texture_name}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": prompt}},
        "11": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": ""}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": "texture/t", "images": ["13", 0]}},
    }
    model_ref = ["4", 0]
    if lightning:
        g["6"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["4", 0], "lora_name": _LIGHTNING, "strength_model": 1.0}}
        model_ref = ["6", 0]
    model_ref = _lora.model_ref_with_loras(g, model_ref, loras)
    g["12"] = {"class_type": "KSampler", "inputs": {
        "model": model_ref, "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["9", 0],
        "seed": int(seed), "steps": int(steps), "cfg": float(cfg),
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    return g


class ApplyTextureFeature(Feature):
    id = "apply_texture"
    name = "Apply Texture"
    description = ("Wrap a texture/material photo onto an object or carving (Qwen-Image-Edit, 2-image). "
                   "Real material preview from your own sample — wood, marble, stone, metal, fabric.")
    needs_comfy = True
    engine = "comfy"
    icon = "texture"
    est_runtime = "~20–50 s"
    vram = "~10–11 GB"
    output_kinds = ["Textured image"]
    inputs = ["image", "image2"]
    input_labels = {"image": "Object / design", "image2": "Texture image"}
    params = [
        ParamSpec("prompt", "text", "", "Where / how (optional)",
                  placeholder="e.g. 'apply to the carved petals only', 'weathered look'",
                  help="Which part to texture or any extra note. Blank = the whole object."),
        ParamSpec("quality", "select", "fast", "Quality", control="seg", group="advanced",
                  help="Fast = 4-step Lightning (fits 12 GB). High = 20-step, cfg 4, cleaner.",
                  choices=[{"value": "fast", "label": "Fast · 4-step"}, {"value": "high", "label": "High · 20-step"}]),
        ParamSpec("steps", "number", 4, "Steps", 4, 8, 1, control="slider", group="advanced",
                  depends_on={"param": "quality", "value": "fast"}, help="Lightning sweet spot 4–8 (Fast only)."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random. Retry a seed if the texture doesn't wrap cleanly."),
        ParamSpec("loras", "lora", [], "LoRAs", control="lora", group="advanced",
                  help="Optional Qwen-Image-Edit LoRAs (e.g. tarn59 apply_texture) for a stronger effect. "
                       "Order doesn't matter — model-only LoRAs are additive."),
        ParamSpec("clarity_upscale", "bool", False, "Clarity upscale (Balanced)", control="switch",
                  group="advanced", help="Sharpen + 2× the result afterwards. Off by default. Needs the Clarity models."),
    ]

    def run(self, inputs, params, out_dir):
        if not inputs.get("image2"):
            raise RuntimeError("Apply Texture needs BOTH images — the object and a texture photo.")
        client = ComfyUIClient()
        client.free()
        obj = client.upload_image(inputs["image"])
        tex = client.upload_image(inputs["image2"])

        note = (params.get("prompt") or "").strip()
        prompt = ("Apply the surface texture and material from the second image onto the main object in the "
                  "first image. Wrap the texture over the object's shape, following its contours, relief and "
                  "lighting; keep the object's form, geometry and outline unchanged. Realistic material, "
                  "seamless, high detail.")
        if note:
            prompt += f" {note}."

        lightning = params.get("quality", "fast") != "high"
        steps = max(4, min(8, int(params.get("steps") or 4))) if lightning else 20
        cfg = 1.0 if lightning else 4.0
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        graph = _build_graph(obj, tex, prompt, seed, lightning, steps, cfg, loras=params.get("loras"))
        out = Path(out_dir) / "apply_texture.png"
        out.write_bytes(client.generate(graph, label="apply-texture", max_wait=900))

        if params.get("clarity_upscale", False):
            from .clarity import ClarityFeature
            cf = ClarityFeature()
            return cf.run({"image": str(out)}, cf.coerce({}), out_dir)
        return {"image": str(out)}
