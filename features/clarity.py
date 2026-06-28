"""features/clarity.py — Clarity-style *creative* upscale (adds detail), via ComfyUI.

Unlike the plain `upscale` feature (a deterministic ESRGAN enlarge that invents no new
detail), this re-diffuses the image tile-by-tile through SD1.5 under a **Tile ControlNet**
at a moderate denoise — so the model *hallucinates* plausible fine detail (skin pores,
hair strands, fabric weave, foliage) while the ControlNet locks the original structure.
This is the recipe behind clarityai.co (philz1337x/clarity-upscaler).

Pipeline per run:
  optional source downscale → for each ≤2× pass: ControlNet-Tile + Ultimate SD Upscale
  (4x-UltraSharp base + tiled SD1.5 img2img) → optional final 4x-UltraSharp → optional
  output clamp → save.

Improvements over the first cut:
- PRESETS (Subtle/Balanced/Creative/Max detail) drive Creativity/Resemblance/HDR/LoRA in one
  pick; 'Custom' exposes the sliders.
- MULTI-PASS: Scale > 2 is decomposed into successive ≤2× diffusion passes (the real clarity
  recipe), each re-detailing — far cleaner at high scale than one oversized pass.
- SEAM FIX: a half-tile pass on the final stage removes faint tile seams.
- VRAM SAFETY: tiled VAE decode, a source-resolution cap (big inputs are detailed at a sane
  size then upscaled back), and a hard output-size clamp.

The sliders map straight onto clarity.ai's: Creativity→denoise, Resemblance→ControlNet
strength, HDR→cfg, Scale→upscale factor.

Prereqs on the box (provisioned by comfy_manager.CLARITY_MODELS + the USDU node clone):
  custom_nodes/ComfyUI_UltimateSDUpscale
  models/controlnet/control_v11f1e_sd15_tile.pth
  models/checkpoints/juggernaut_reborn.safetensors   (or reuse the SD1.5 base)
  models/loras/{more_details,add_detail,detail_slider_v4,add_sharpness}.safetensors
  models/upscale_models/4x-UltraSharp.pth            (already in the core gate)
"""
import random
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

_UPSCALE_MODEL = "4x-UltraSharp.pth"
_TILE_CONTROLNET = "control_v11f1e_sd15_tile.pth"
_POS_SUFFIX = "masterpiece, best quality, highres, sharp focus, fine detail, intricate texture"
_NEG = "blurry, lowres, low quality, worst quality, jpeg artifacts, oversharpened, noise, deformed"
_MAX_OUTPUT_PX = 8192          # hard cap on the output long edge → bounded VRAM / file size

# preset -> the four "feel" params it drives (clarity.ai-style). 'custom' uses the sliders.
_PRESETS = {
    "subtle":   {"creativity": 0.20, "resemblance": 0.85, "hdr": 5, "detail_lora": "more_details.safetensors"},
    "balanced": {"creativity": 0.35, "resemblance": 0.60, "hdr": 6, "detail_lora": "more_details.safetensors"},
    "creative": {"creativity": 0.55, "resemblance": 0.45, "hdr": 7, "detail_lora": "add_detail.safetensors"},
    "max":      {"creativity": 0.70, "resemblance": 0.35, "hdr": 8, "detail_lora": "add_detail.safetensors"},
}
# sensible per-LoRA strength (Detail Tweaker / slider want more push than more_details)
_LORA_STRENGTH = {
    "more_details.safetensors": 0.5, "add_detail.safetensors": 0.7,
    "detail_slider_v4.safetensors": 1.0, "add_sharpness.safetensors": 0.5,
}


def _calc_passes(scale):
    """Decompose the requested scale into successive ≤2× diffusion passes (the clarity
    recipe): 4×→[2,2], 3×→[2,1.5], 2×→[2], 1.5×→[1.5]. Each pass re-diffuses + re-details,
    which is far cleaner at high scale than one oversized pass."""
    s = float(scale)
    passes = []
    while s > 2.0 + 1e-6:
        passes.append(2.0)
        s /= 2.0
    passes.append(round(s, 4))
    return passes


def _build_graph(image_name, checkpoint, pos, neg, creativity, resemblance, hdr,
                 passes, steps, seed, tile, detail_lora, detail_strength,
                 final_upscale, seam_fix, clamp_to):
    """Hand-authored API graph with a dynamic node count (multi-pass). Each pass applies the
    Tile ControlNet to its OWN input image (so the per-tile hint stays accurate), then runs
    Ultimate SD Upscale; the next pass chains off its output."""
    g = {}
    n = [0]

    def add(node):
        n[0] += 1
        g[str(n[0])] = node
        return str(n[0])

    ck = add({"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}})
    img0 = add({"class_type": "LoadImage", "inputs": {"image": image_name}})
    up = add({"class_type": "UpscaleModelLoader", "inputs": {"model_name": _UPSCALE_MODEL}})
    cn = add({"class_type": "ControlNetLoader", "inputs": {"control_net_name": _TILE_CONTROLNET}})

    model_ref, clip_ref = [ck, 0], [ck, 1]
    if detail_lora and detail_lora != "none":               # detail LoRA: extra micro-detail
        lr = add({"class_type": "LoraLoader", "inputs": {
            "model": [ck, 0], "clip": [ck, 1], "lora_name": detail_lora,
            "strength_model": float(detail_strength), "strength_clip": float(detail_strength)}})
        model_ref, clip_ref = [lr, 0], [lr, 1]

    pos_id = add({"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": clip_ref}})
    neg_id = add({"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": clip_ref}})

    cur, last = [img0, 0], len(passes) - 1
    for i, m in enumerate(passes):
        cna = add({"class_type": "ControlNetApplyAdvanced", "inputs": {
            "positive": [pos_id, 0], "negative": [neg_id, 0], "control_net": [cn, 0],
            "image": cur, "strength": float(resemblance), "start_percent": 0.0, "end_percent": 1.0}})
        sfx = "Half Tile" if (seam_fix and i == last) else "None"   # only seam-fix the final pass
        usdu = add({"class_type": "UltimateSDUpscale", "inputs": {
            "image": cur, "model": model_ref, "positive": [cna, 0], "negative": [cna, 1],
            "vae": [ck, 2], "upscale_by": float(m), "seed": int(seed), "steps": int(steps),
            "cfg": float(hdr), "sampler_name": "dpmpp_3m_sde", "scheduler": "karras",
            "denoise": float(creativity), "upscale_model": [up, 0], "mode_type": "Linear",
            "tile_width": int(tile), "tile_height": int(tile), "mask_blur": 8, "tile_padding": 32,
            "seam_fix_mode": sfx, "seam_fix_denoise": 0.3, "seam_fix_width": 64,
            "seam_fix_mask_blur": 8, "seam_fix_padding": 16, "force_uniform_tiles": True,
            "tiled_decode": True, "batch_size": 1}})        # tiled_decode → VAE never OOMs on big tiles
        cur = [usdu, 0]

    if final_upscale:                                        # closing 4x-UltraSharp crispen pass
        cur = [add({"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": [up, 0], "image": cur}}), 0]
    if clamp_to:                                             # bound the output long edge
        cur = [add({"class_type": "ImageScale", "inputs": {
            "image": cur, "upscale_method": "lanczos",
            "width": int(clamp_to[0]), "height": int(clamp_to[1]), "crop": "disabled"}}), 0]

    add({"class_type": "SaveImage", "inputs": {"filename_prefix": "clarity/c", "images": cur}})
    return g


class ClarityFeature(Feature):
    id = "clarity"
    name = "Clarity Upscale"
    description = ("Creative upscale that *adds* detail (skin, hair, texture) — re-diffuses "
                  "tile-by-tile under a Tile ControlNet, à la clarity.ai. Not a plain enlarge.")
    needs_comfy = True
    engine = "comfy"
    icon = "upscale"
    est_runtime = "~20 s – 3 min"
    vram = "~4–8 GB"
    output_kinds = ["Image PNG · detailed"]
    inputs = ["image"]
    _CUSTOM = {"param": "preset", "value": "custom"}
    params = [
        ParamSpec("preset", "select", "balanced", "Preset",
                  help="Quick looks. Pick Custom to drive Creativity / Resemblance / HDR / LoRA by hand.",
                  choices=[{"value": "subtle", "label": "Subtle (faithful cleanup)"},
                           {"value": "balanced", "label": "Balanced"},
                           {"value": "creative", "label": "Creative (more invention)"},
                           {"value": "max", "label": "Max detail (heavy remaster)"},
                           {"value": "custom", "label": "Custom"}]),
        ParamSpec("prompt", "text", "", "Prompt (optional)",
                  placeholder="Describe the subject to steer the detail…",
                  help="Blank works fine — a hint like 'portrait of a woman' sharpens results."),
        ParamSpec("scale", "number", 2, "Scale", 1, 4, 0.5, control="slider", suffix="×",
                  help="Diffusion enlargement. Above 2× runs in multiple ≤2× passes for cleaner detail."),
        ParamSpec("final_upscale", "bool", True, "Final 4×-UltraSharp", control="switch",
                  help="Run 4×-UltraSharp on the finished image for extra crispness. "
                       "Multiplies the final size by 4 (so Scale 2× → 8× total). Off to keep Scale."),
        ParamSpec("creativity", "number", 0.35, "Creativity", 0.1, 1.0, 0.05, control="slider",
                  depends_on=_CUSTOM,
                  help="Denoise — higher invents more new detail; lower stays faithful."),
        ParamSpec("resemblance", "number", 0.6, "Resemblance", 0.0, 2.0, 0.05, control="slider",
                  depends_on=_CUSTOM,
                  help="Tile-ControlNet strength — how tightly to keep the original structure."),
        ParamSpec("checkpoint", "select", "juggernaut_reborn.safetensors", "Detail model",
                  group="advanced", help="Photoreal SD1.5 checkpoint the detail is dreamed with.",
                  choices=[{"value": "juggernaut_reborn.safetensors", "label": "Juggernaut Reborn (photoreal)"},
                           {"value": "v1-5-pruned-emaonly-fp16.safetensors", "label": "SD 1.5 base (lighter)"}]),
        ParamSpec("hdr", "number", 6, "HDR / contrast", 1, 12, 0.5, control="slider", group="advanced",
                  depends_on=_CUSTOM,
                  help="CFG — higher = punchier contrast & micro-detail; too high looks 'fried'."),
        ParamSpec("detail_lora", "select", "more_details.safetensors", "Detail LoRA", group="advanced",
                  depends_on=_CUSTOM, help="Extra detail/sharpness. Detail Tweaker is the strongest.",
                  choices=[{"value": "more_details.safetensors", "label": "more_details (subtle)"},
                           {"value": "add_detail.safetensors", "label": "Detail Tweaker (strong)"},
                           {"value": "detail_slider_v4.safetensors", "label": "Detail slider"},
                           {"value": "add_sharpness.safetensors", "label": "Sharpness (edges)"},
                           {"value": "none", "label": "None"}]),
        ParamSpec("steps", "number", 18, "Steps", 8, 40, 1, control="slider", group="advanced",
                  help="More steps = finer detail, slower."),
        ParamSpec("tile", "select", "1024", "Tile size", control="seg", group="advanced",
                  help="Smaller = less VRAM & more fractal detail (more seams); larger = cleaner.",
                  choices=[{"value": "512", "label": "512"}, {"value": "768", "label": "768"},
                           {"value": "1024", "label": "1024"}, {"value": "1280", "label": "1280"}]),
        ParamSpec("seam_fix", "bool", True, "Seam fix", control="switch", group="advanced",
                  help="Half-tile pass on the final stage that removes faint tile seams."),
        ParamSpec("source_limit", "number", 1536, "Source limit", 768, 3072, 64, control="slider",
                  suffix=" px", group="advanced",
                  help="Big inputs are downscaled to this long edge before detailing — saves VRAM/time; "
                       "the upscale restores size. Raise to keep more of a large source."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random each run."),
    ]

    def run(self, inputs, params, out_dir):
        client = ComfyUIClient()
        out_dir = Path(out_dir)

        # preset drives the four "feel" params unless Custom is chosen
        preset = params.get("preset", "balanced")
        if preset != "custom" and preset in _PRESETS:
            p = _PRESETS[preset]
            creativity, resemblance, hdr, detail_lora = p["creativity"], p["resemblance"], p["hdr"], p["detail_lora"]
        else:
            creativity, resemblance, hdr = params["creativity"], params["resemblance"], params["hdr"]
            detail_lora = params.get("detail_lora", "more_details.safetensors")
        detail_strength = _LORA_STRENGTH.get(detail_lora, 0.6)

        # VRAM/speed safety: detail a sanely-sized source, then upscale back
        src = Image.open(inputs["image"]).convert("RGB")
        limit = int(params.get("source_limit", 1536))
        if max(src.size) > limit:
            f = limit / max(src.size)
            src = src.resize((max(8, round(src.width * f)), max(8, round(src.height * f))), Image.LANCZOS)
        base = out_dir / "clarity_input.png"
        src.save(base)
        name = client.upload_image(str(base))

        scale = float(params["scale"])
        final_up = bool(params.get("final_upscale", True))
        passes = _calc_passes(scale)

        # predict the final long edge → clamp it if Scale × final pass would blow past the cap
        total = scale * (4 if final_up else 1)
        fw, fh = round(src.width * total), round(src.height * total)
        clamp_to = None
        if max(fw, fh) > _MAX_OUTPUT_PX:
            cf = _MAX_OUTPUT_PX / max(fw, fh)
            clamp_to = (max(8, round(fw * cf)), max(8, round(fh * cf)))

        user = (params.get("prompt") or "").strip()
        pos = f"{user}, {_POS_SUFFIX}" if user else _POS_SUFFIX
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        graph = _build_graph(name, params["checkpoint"], pos, _NEG, creativity, resemblance, hdr,
                             passes, params["steps"], seed, params["tile"], detail_lora,
                             detail_strength, final_up, bool(params.get("seam_fix", True)), clamp_to)
        out = out_dir / "clarity.png"
        out.write_bytes(client.generate(graph, label="clarity", max_wait=1200))
        return {"image": str(out)}
