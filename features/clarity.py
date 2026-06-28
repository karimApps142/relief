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
- PRESETS (Subtle/Balanced/Creative/Max detail) are a one-click quick-start that fills the
  Creativity / Resemblance / HDR / LoRA controls, which stay visible for hand-tuning (the UI
  fills the sliders and flips to 'Custom' when you nudge one — the sliders are authoritative).
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

# The Preset quick-start values live in the UI (web/src/Controls.tsx CLARITY_PRESETS); it fills
# the visible sliders, so the server just reads whatever the sliders hold — no override here.
# sensible per-LoRA strength (Detail Tweaker / slider want more push than more_details)
_LORA_STRENGTH = {
    "more_details.safetensors": 0.5, "add_detail.safetensors": 0.7,
    "detail_slider_v4.safetensors": 1.0, "add_sharpness.safetensors": 0.5,
}


def _estimate_runs(width, height, passes, tile, seam_fix):
    """Mirror UltimateSDUpscale's tiling to count sampler RUNS (each tile is one KSampler at
    `steps`). Used to predict total sampler steps so the progress bar fills once, cumulatively,
    instead of resetting per tile. Approximate — the cumulative % is capped at 99 until done."""
    import math
    w, h, runs, tiles = float(width), float(height), 0, 1
    for m in passes:
        w *= m; h *= m
        tiles = max(1, math.ceil(w / tile)) * max(1, math.ceil(h / tile))
        runs += tiles
    if seam_fix:
        runs += tiles                  # final-pass half-tile seam sweep ≈ one more tile pass
    return runs


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
    guide = [
        {"h": "What it does",
         "b": "A creative upscale that ADDS detail — skin pores, hair strands, fabric weave, "
              "foliage. It re-diffuses your image tile-by-tile through SD1.5 under a Tile "
              "ControlNet that locks the original structure, so it gets bigger AND more "
              "detailed (the plain Upscale tab just enlarges — it invents nothing)."},
        {"h": "How to add more fine detail",
         "b": "In order of impact: (1) Creativity ↑ to 0.45–0.6 — the main lever, but above "
              "~0.65 it starts changing the face. (2) Detail LoRA → Detail Tweaker (strongest). "
              "(3) HDR ↑ to 7–8 (stop at ~8 or it looks 'fried'). (4) Steps ↑ to 26–30. "
              "(5) Tile → 768 or 512 packs denser detail — turn Seam fix ON. (6) Add a Prompt "
              "describing the subject. (7) Resemblance ↓ to ~0.45 frees it to add more (watch drift)."},
        {"h": "Recipes",
         "b": "Max facial detail → start from the Creative preset: Creativity 0.55, Detail "
              "Tweaker, HDR 7.5, Steps 28, Tile 768, Seam fix on, a descriptive prompt.  "
              "Faithful sharpen (no identity change) → Subtle/Balanced: Creativity 0.3, "
              "Resemblance 0.75, more_details LoRA, HDR 6."},
        {"h": "Watch out / for Relief",
         "b": "Too much Creativity invents details that aren't real; too high HDR looks "
              "oversharpened; tiny tiles without Seam fix show grid seams. If you'll feed the "
              "result into Relief, keep it moderate (Creativity ~0.4, Detail Tweaker) — enough "
              "carve-able detail without hallucinating features the relief shouldn't have."},
    ]
    params = [
        ParamSpec("preset", "select", "balanced", "Preset",
                  help="Quick-start — fills the Creativity / Resemblance / HDR sliders below. "
                       "Nudge any slider and this switches to Custom.",
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
                  help="Denoise — higher invents more new detail; lower stays faithful to the source."),
        ParamSpec("resemblance", "number", 0.6, "Resemblance", 0.0, 2.0, 0.05, control="slider",
                  help="Tile-ControlNet strength — how tightly to keep the original structure. "
                       "Lower lets it drift; higher locks composition."),
        ParamSpec("checkpoint", "select", "juggernaut_reborn.safetensors", "Detail model",
                  group="advanced", help="Photoreal SD1.5 checkpoint the detail is dreamed with.",
                  choices=[{"value": "juggernaut_reborn.safetensors", "label": "Juggernaut Reborn (photoreal)"},
                           {"value": "v1-5-pruned-emaonly-fp16.safetensors", "label": "SD 1.5 base (lighter)"}]),
        ParamSpec("hdr", "number", 6, "HDR / contrast", 1, 12, 0.5, control="slider", group="advanced",
                  help="CFG — higher = punchier contrast & micro-detail; too high looks 'fried'."),
        ParamSpec("detail_lora", "select", "more_details.safetensors", "Detail LoRA", group="advanced",
                  help="Extra detail/sharpness. Detail Tweaker is the strongest.",
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

        # the sliders are authoritative; the UI 'preset' just pre-fills them client-side
        creativity = params["creativity"]
        resemblance = params["resemblance"]
        hdr = params["hdr"]
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
        # predict total sampler steps (tiles × passes × steps) so progress fills once, not per-tile
        runs = _estimate_runs(src.width, src.height, passes, int(params["tile"]),
                              bool(params.get("seam_fix", True)))
        total_steps = runs * int(params["steps"])

        out = out_dir / "clarity.png"
        out.write_bytes(client.generate(graph, label="clarity", max_wait=1200,
                                        total_steps=total_steps))
        return {"image": str(out)}
