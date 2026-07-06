"""features/image_edit.py — instruction image editing with Qwen-Image-Edit-2511 (GGUF) via ComfyUI.

A TRUE image editor (unlike img2img's re-diffuse): upload an image + a text instruction and it
edits precisely — add/remove/replace objects, change art style, relight, restyle — keeping the
rest of the image consistent. Also does bas-relief / sculpture STYLE transforms by prompt (the
"Bas-relief (CNC)" preset is tuned to feed the Relief tab → clean carveable geometry).

Model: Qwen-Image-Edit-2511 (Qwen-Image / MMDiT) run as a GGUF unet so it fits a 12 GB card.
Graph verified against the official Comfy-Org 2511 template:
  UnetLoaderGGUF → ModelSamplingAuraFlow(shift 3.1) → [Lightning LoRA] → KSampler
  CLIPLoader(type=qwen_image) + VAELoader(qwen_image_vae, reused from the Krea core)
  LoadImage → FluxKontextImageScale (~1 MP bucket) → VAEEncode = the sampling latent (denoise 1.0)
  TextEncodeQwenImageEditPlus ×2 (positive = instruction, negative = empty) carry the reference
The reference image feeds BOTH the Qwen2.5-VL encoder (semantic) and the VAE (appearance).

12 GB VRAM tricks (Q3_K_M ≈ 9.68 GB weights, sampling peak ≈ 11 GB — only ~1 GB headroom):
  • run() calls ComfyUI /free first, so any resident model (Krea-2, Clarity SD1.5…) is unloaded
    and the ~19 GB of edit models load into clean VRAM.
  • ComfyUI natively offloads sequentially: the fp8 text encoder loads → encodes → offloads to
    CPU → the GGUF unet loads → samples → offloads → VAE decodes. Nothing is co-resident.
  • FluxKontextImageScale caps the working image at ~1 MP, so the VAE decode stays within budget.
  • 4-step Lightning LoRA at cfg 1.0 keeps the sampler cheap.
If a decode still OOMs on a busier box, launch ComfyUI with --lowvram (saves 3–6 GB, ~20–40% slower).

Prereqs (provisioned by comfy_manager.QWEN_EDIT_MODELS; needs a RECENT ComfyUI for the Qwen-Edit
nodes — git pull ComfyUI if you see 'node not found'):
  models/unet/qwen-image-edit-2511-Q3_K_M.gguf
  models/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors
  models/vae/qwen_image_vae.safetensors                     (already have it)
  models/loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors
"""
import random
from pathlib import Path

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from . import _lora

_UNET = "qwen-image-edit-2511-Q3_K_M.gguf"
_CLIP = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
_VAE = "qwen_image_vae.safetensors"
_LIGHTNING = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors"

# style quick-prompts. 'basrelief' is tuned for CNC: shallow + single light + matte + flat bg
# so the Relief/Depth tab reads it as clean geometry instead of baked shadows.
_PRESETS = {
    "custom": "",
    "basrelief": ("convert into a shallow bas-relief stone carving, carved in low relief, marble, "
                  "single soft raking light, matte surface, crisp clean carved edges, plain flat background"),
    "marble": "turn into a smooth carved white marble sculpture, polished stone, soft studio lighting",
    "bronze": "turn into a cast bronze sculpture, patinated metal, museum lighting",
    "lineart": "convert into a clean engraved line relief, shallow carving, high contrast, flat background",
}


def _build_graph(image_name, prompt, seed, lightning, steps, cfg, loras=None):
    """Hand-authored 2511 edit graph (single reference image). The FluxKontextMultiReference
    nodes are omitted — the official note says they're only needed for multi-image / third-party
    repackaged unets, not a single-image edit with the standard loaders. Any user LoRAs are
    chained (model-only) after the Lightning LoRA — order is irrelevant (additive deltas)."""
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": _UNET}},
        "2": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": _CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": _VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "7": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["7", 0]}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "prompt": prompt}},
        "11": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "prompt": ""}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": "qwenedit/e", "images": ["13", 0]}},
    }
    model_ref = ["4", 0]
    if lightning:                                            # 4-step speed LoRA (model-only)
        g["6"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["4", 0], "lora_name": _LIGHTNING, "strength_model": 1.0}}
        model_ref = ["6", 0]
    model_ref = _lora.model_ref_with_loras(g, model_ref, loras)   # user LoRAs chained after Lightning
    g["12"] = {"class_type": "KSampler", "inputs": {
        "model": model_ref, "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["9", 0],
        "seed": int(seed), "steps": int(steps), "cfg": float(cfg),
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    return g


class ImageEditFeature(Feature):
    id = "image_edit"
    name = "Image Edit"
    description = ("Edit an image from a text instruction (Qwen-Image-Edit-2511) — add/remove/replace, "
                  "change art style, relight. Bas-relief (CNC) preset feeds the Relief tab.")
    needs_comfy = True
    engine = "comfy"
    icon = "pencil"
    est_runtime = "~15–45 s"
    vram = "~10–11 GB"
    output_kinds = ["Edited image"]
    inputs = ["image"]
    params = [
        ParamSpec("prompt", "text", "", "Edit instruction",
                  placeholder="e.g. 'change the background to a forest', 'make it a marble statue'…",
                  help="Plain-language edit. Combines with the Style preset below."),
        ParamSpec("preset", "select", "custom", "Style preset",
                  help="Quick prompts. Bas-relief (CNC) is tuned to feed the Relief/Depth tab. "
                       "Prepended to your instruction.",
                  choices=[{"value": "custom", "label": "Custom (prompt only)"},
                           {"value": "basrelief", "label": "Bas-relief (CNC)"},
                           {"value": "marble", "label": "Marble sculpt"},
                           {"value": "bronze", "label": "Bronze sculpt"},
                           {"value": "lineart", "label": "Engraved line relief"}]),
        ParamSpec("quality", "select", "fast", "Quality", control="seg", group="advanced",
                  help="Fast = 4-step Lightning (recommended, fits 12 GB). High = 20-step, cfg 4, slower.",
                  choices=[{"value": "fast", "label": "Fast · 4-step"},
                           {"value": "high", "label": "High · 20-step"}]),
        ParamSpec("steps", "number", 4, "Steps", 4, 8, 1, control="slider", group="advanced",
                  depends_on={"param": "quality", "value": "fast"},
                  help="Lightning sweet spot 4–8 (only for Fast; High is fixed at 20)."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random each run."),
        ParamSpec("loras", "lora", [], "LoRAs", control="lora", group="advanced",
                  help="Stack Qwen-Image-Edit LoRAs (e.g. Multiple-Angles, Relight), each with its own "
                       "strength. Order does NOT change the result — model-only LoRAs are additive weight "
                       "deltas that combine commutatively; each LoRA's strength scales its effect. Use "
                       "LoRAs trained for Qwen-Image-Edit — a non-matching one silently does nothing."),
        ParamSpec("clarity_upscale", "bool", True, "Clarity upscale (Balanced)", control="switch",
                  group="advanced",
                  help="After editing, run Clarity Upscale (Balanced) on the result — adds fine detail "
                       "and 2× size. Off to skip. Needs the Clarity models installed (see the Clarity tab)."),
    ]

    def run(self, inputs, params, out_dir):
        client = ComfyUIClient()
        client.free()                                        # unload any resident model → clean 12 GB
        name = client.upload_image(inputs["image"])

        preset = params.get("preset", "custom")
        user = (params.get("prompt") or "").strip()
        base = _PRESETS.get(preset, "")
        prompt = f"{base}, {user}" if (base and user) else (base or user)

        lightning = params.get("quality", "fast") != "high"
        steps = max(4, min(8, int(params.get("steps") or 4))) if lightning else 20
        cfg = 1.0 if lightning else 4.0
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        graph = _build_graph(name, prompt, seed, lightning, steps, cfg, loras=params.get("loras"))
        out = Path(out_dir) / "image_edit.png"
        out.write_bytes(client.generate(graph, label="image-edit", max_wait=900))

        # optional finishing pass: reuse the Clarity feature (Balanced preset) on the edited image.
        if params.get("clarity_upscale"):
            from .clarity import ClarityFeature
            cf = ClarityFeature()
            return cf.run({"image": str(out)}, cf.coerce({}), out_dir)
        return {"image": str(out)}
