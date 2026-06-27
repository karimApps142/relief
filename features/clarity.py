"""features/clarity.py — Clarity-style *creative* upscale (adds detail), via ComfyUI.

Unlike the plain `upscale` feature (a deterministic ESRGAN enlarge that invents no new
detail), this re-diffuses the image tile-by-tile through SD1.5 under a **Tile ControlNet**
at a moderate denoise — so the model *hallucinates* plausible fine detail (skin pores,
hair strands, fabric weave, foliage) while the ControlNet locks the original structure.
This is exactly the recipe behind clarityai.co (philz1337x/clarity-upscaler):

  4x-UltraSharp base upscale → Ultimate SD Upscale (tiled SD1.5 img2img) + Tile ControlNet
  on a photoreal checkpoint (juggernaut_reborn), with an optional `more_details` LoRA.

The signature sliders map straight onto sampler params, same as Clarity's UI:
  Creativity  → denoise          (higher = invents more detail, lower = faithful)
  Resemblance → ControlNet weight (how tightly to keep the original structure)
  HDR         → cfg              (punch / contrast / micro-detail)
  Scale       → upscale_by

Ultimate SD Upscale (ssitu/ComfyUI_UltimateSDUpscale) auto-crops the ControlNet tile
hint per tile, so the canonical wiring is a single ControlNetApplyAdvanced on the base
image feeding the node's positive/negative — no manual tiling of the hint.

Prereqs on the box (provisioned by comfy_manager.CLARITY_MODELS + the USDU node clone):
  custom_nodes/ComfyUI_UltimateSDUpscale
  models/controlnet/control_v11f1e_sd15_tile.pth
  models/checkpoints/juggernaut_reborn.safetensors   (or reuse the SD1.5 base)
  models/loras/more_details.safetensors              (optional detail LoRA)
  models/upscale_models/4x-UltraSharp.pth            (already in the core gate)
"""
import random
from pathlib import Path

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

_UPSCALE_MODEL = "4x-UltraSharp.pth"
_TILE_CONTROLNET = "control_v11f1e_sd15_tile.pth"
# Injected on top of any user prompt so a blank prompt still steers toward crisp detail.
_POS_SUFFIX = "masterpiece, best quality, highres, sharp focus, fine detail, intricate texture"
_NEG = "blurry, lowres, low quality, worst quality, jpeg artifacts, oversharpened, noise, deformed"


def _build_graph(image_name, checkpoint, pos, neg, creativity, resemblance, hdr,
                 scale, steps, seed, tile, detail_lora, final_upscale, detail_strength=0.5):
    """Hand-authored API graph: checkpoint (+ optional detail LoRA) → CLIP encode →
    Tile-ControlNet apply → Ultimate SD Upscale (4x-UltraSharp + tiled SD1.5) → save.
    With final_upscale, a closing ImageUpscaleWithModel (4x-UltraSharp) crispens the
    finished image (×4 on top of `scale`), reusing the already-loaded upscale model."""
    graph = {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": _UPSCALE_MODEL}},
        "4": {"class_type": "ControlNetLoader", "inputs": {"control_net_name": _TILE_CONTROLNET}},
    }
    model_ref, clip_ref = ["1", 0], ["1", 1]
    if detail_lora and detail_lora != "none":               # more_details: extra micro-detail
        graph["10"] = {"class_type": "LoraLoader", "inputs": {
            "model": ["1", 0], "clip": ["1", 1], "lora_name": detail_lora,
            "strength_model": float(detail_strength), "strength_clip": float(detail_strength)}}
        model_ref, clip_ref = ["10", 0], ["10", 1]

    graph["5"] = {"class_type": "CLIPTextEncode", "inputs": {"text": pos, "clip": clip_ref}}
    graph["6"] = {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": clip_ref}}
    # One ControlNetApplyAdvanced on the BASE image — USDU crops the hint per tile itself.
    graph["7"] = {"class_type": "ControlNetApplyAdvanced", "inputs": {
        "positive": ["5", 0], "negative": ["6", 0], "control_net": ["4", 0],
        "image": ["2", 0], "strength": float(resemblance),
        "start_percent": 0.0, "end_percent": 1.0}}
    graph["8"] = {"class_type": "UltimateSDUpscale", "inputs": {
        "image": ["2", 0], "model": model_ref, "positive": ["7", 0], "negative": ["7", 1],
        "vae": ["1", 2], "upscale_by": float(scale), "seed": int(seed), "steps": int(steps),
        "cfg": float(hdr), "sampler_name": "dpmpp_3m_sde", "scheduler": "karras",
        "denoise": float(creativity), "upscale_model": ["3", 0], "mode_type": "Linear",
        "tile_width": int(tile), "tile_height": int(tile), "mask_blur": 8, "tile_padding": 32,
        "seam_fix_mode": "None", "seam_fix_denoise": 1.0, "seam_fix_width": 64,
        "seam_fix_mask_blur": 8, "seam_fix_padding": 16, "force_uniform_tiles": True,
        "tiled_decode": False, "batch_size": 1}}
    save_ref = ["8", 0]
    if final_upscale:                                       # closing 4x-UltraSharp crispen pass
        graph["11"] = {"class_type": "ImageUpscaleWithModel", "inputs": {
            "upscale_model": ["3", 0], "image": ["8", 0]}}
        save_ref = ["11", 0]
    graph["9"] = {"class_type": "SaveImage", "inputs": {
        "filename_prefix": "clarity/c", "images": save_ref}}
    return graph


class ClarityFeature(Feature):
    id = "clarity"
    name = "Clarity Upscale"
    description = ("Creative upscale that *adds* detail (skin, hair, texture) — re-diffuses "
                  "tile-by-tile under a Tile ControlNet, à la clarity.ai. Not a plain enlarge.")
    needs_comfy = True
    engine = "comfy"
    icon = "upscale"
    est_runtime = "~20 s – 2 min"
    vram = "~4–8 GB"
    output_kinds = ["Image PNG · detailed"]
    inputs = ["image"]
    params = [
        ParamSpec("prompt", "text", "", "Prompt (optional)",
                  placeholder="Describe the subject to steer the detail…",
                  help="Blank works fine — a hint like 'portrait of a woman' sharpens results."),
        ParamSpec("scale", "number", 2, "Scale", 1, 4, 0.5, control="slider", suffix="×",
                  help="Output size multiplier (the diffusion stage)."),
        ParamSpec("final_upscale", "bool", True, "Final 4×-UltraSharp", control="switch",
                  help="Run 4×-UltraSharp on the finished image for extra crispness. "
                       "Multiplies the final size by 4 (so Scale 2× → 8× total). Off to keep Scale."),
        ParamSpec("creativity", "number", 0.35, "Creativity", 0.1, 1.0, 0.05, control="slider",
                  help="Denoise — higher invents more new detail; lower stays faithful. "
                       "Sweet spot 0.3–0.5; push to 0.6–0.9 for a heavier remaster."),
        ParamSpec("resemblance", "number", 0.6, "Resemblance", 0.0, 2.0, 0.05, control="slider",
                  help="Tile-ControlNet strength — how tightly to keep the original structure. "
                       "Lower lets it drift; higher locks composition."),
        ParamSpec("checkpoint", "select", "juggernaut_reborn.safetensors", "Detail model",
                  group="advanced", help="Photoreal SD1.5 checkpoint the detail is dreamed with.",
                  choices=[{"value": "juggernaut_reborn.safetensors", "label": "Juggernaut Reborn (photoreal)"},
                           {"value": "v1-5-pruned-emaonly-fp16.safetensors", "label": "SD 1.5 base (lighter)"}]),
        ParamSpec("hdr", "number", 6, "HDR / contrast", 1, 12, 0.5, control="slider", group="advanced",
                  help="CFG — higher = punchier contrast & micro-detail; too high looks 'fried'."),
        ParamSpec("steps", "number", 18, "Steps", 8, 40, 1, control="slider", group="advanced",
                  help="More steps = finer detail, slower."),
        ParamSpec("tile", "select", "1024", "Tile size", control="seg", group="advanced",
                  help="Smaller = less VRAM & more fractal detail (more seams); larger = cleaner.",
                  choices=[{"value": "512", "label": "512"}, {"value": "768", "label": "768"},
                           {"value": "1024", "label": "1024"}, {"value": "1280", "label": "1280"}]),
        ParamSpec("detail_lora", "select", "more_details.safetensors", "Detail LoRA", group="advanced",
                  help="The 'more_details' LoRA Clarity uses for extra pop. 'None' to skip.",
                  choices=[{"value": "more_details.safetensors", "label": "more_details"},
                           {"value": "none", "label": "None"}]),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random each run."),
    ]

    def run(self, inputs, params, out_dir):
        client = ComfyUIClient()
        name = client.upload_image(inputs["image"])
        user = (params.get("prompt") or "").strip()
        pos = f"{user}, {_POS_SUFFIX}" if user else _POS_SUFFIX
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        graph = _build_graph(
            name, params["checkpoint"], pos, _NEG, params["creativity"], params["resemblance"],
            params["hdr"], params["scale"], params["steps"], seed, params["tile"],
            params.get("detail_lora", "more_details.safetensors"), params.get("final_upscale", True))
        out = Path(out_dir) / "clarity.png"
        out.write_bytes(client.generate(graph, label="clarity", max_wait=900))
        return {"image": str(out)}
