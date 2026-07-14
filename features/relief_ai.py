"""features/relief_ai.py — photo → depth map → AI-refined 2.5D CNC height map.

One upload, three stages:
  1. LOCAL DEPTH — Depth-Anything (tiled) generates a depth map; it's normalized (white = highest
     relief), the user's detail tweaks are applied, and it's published to the UI canvas immediately
     (relief_progress.set_preview) so the user sees real progress while stage 2 runs.
  2. AI RELIEF — the depth map (image1, style/relief reference — also the sampling latent) and the
     original photo (image2, content reference) go to Qwen-Image-Edit-2511 as a 2-image edit with a
     fixed CNC-heightmap prompt → a production-style grayscale bas-relief height map.
  3. Optional CLARITY finish (off by default).

Detail tweaks (the user-adjustable "make hidden areas prominent" controls):
  detail_boost   — gamma-lifts dark/recessed depth values so faint elements brighten toward white
                   and the AI keeps them prominent (≥0.5 also strengthens the prompt).
  local_contrast — CLAHE on the depth so faint depth separations stand out before the AI pass.

12 GB sequencing: ComfyUI is freed FIRST (a prior Qwen run can hold ~10 GB and OOM the local
depth pass), the local models are unloaded before the Qwen stage, and the Qwen graph reuses the
verified Q3 GGUF + Lightning setup from image_edit. Needs the GPU depth weights (Relief tab) and
the Qwen-Edit models (Image Edit tab).
"""
import random
from pathlib import Path

import numpy as np
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from .image_edit import _UNET, _CLIP, _VAE, _LIGHTNING

# The user's CNC bas-relief height-map prompt, verbatim. image1 = depth map, image2 = photo.
_PROMPT = """Image 1 is the style reference. Match its carving style, relief depth, surface quality, edge treatment, ornamentation, and overall CNC craftsmanship as closely as possible.

Image 2 is the content reference. Preserve its subject, pose, proportions, anatomy, composition, and decorative elements, but recreate it entirely in the style of Image 1.

Generate a professional CNC bas-relief grayscale height map, not a painting, illustration, or photograph.

Requirements
Perfectly smooth, CNC-ready surfaces.
Clean, polished relief with crisp edges and smooth depth transitions.
Preserve all intentional sculpted details while keeping surfaces mathematically smooth.
Do not add or invent any extra details.
Strictly follow the reference style.
No surface noise, grain, bumps, orange-peel texture, AI micro-texture, scratches, procedural texture, fabric texture, skin pores, sharpening artifacts, scan artifacts, or random high-frequency details.
No lighting, shadows, reflections, ambient occlusion, or color information.
Height Map Rules
Use only grayscale.
White (#FFFFFF) = highest relief (closest to the camera).
Black (#000000) = deepest areas (farthest from the camera).
All gray values must represent only physical height.
Small details such as eyes, eyelids, nostrils, lips, hair, mane, leaves, flowers, and ornaments must have clear depth separation using grayscale only, making them prominent without adding texture.
Maintain a smooth, logical front-to-back depth hierarchy across the entire relief.

Final output: A production-quality CNC bas-relief height map with 95–100% style fidelity to Image 1, the content of Image 2, perfectly smooth machinable surfaces, and zero unwanted texture or noise."""

_BOOST_LINE = ("\nGive hidden and recessed details clearly brighter height values so they stay "
               "visible and prominent in the relief.")


def _count_passes(tile_detail, grids, face_crop):
    """Depth forward-passes for the progress bar — mirrors pipeline._count_passes:
    1 global + (2n-1)(2m-1) per grid (+1 body pass on the face-crop path)."""
    if tile_detail == "off":
        return 1
    (a, b), (c, d) = grids
    g = lambda x, y: (2 * x - 1) * (2 * y - 1)
    return 1 + g(a, b) + g(c, d) + (1 if face_crop else 0)


def _tweak_depth(depth01, detail_boost, local_contrast):
    """Apply the user's detail tweaks to a 0–1 depth map: CLAHE lifts faint depth separations,
    then a gamma lift brightens dark/recessed areas (gamma < 1 → hidden details rise toward
    white). Both are monotone in their sliders; 0 = untouched."""
    import cv2
    d = np.clip(depth01, 0.0, 1.0).astype(np.float32)
    lc = float(local_contrast or 0)
    if lc > 0:
        h16 = (d * 65535.0).astype(np.uint16)
        tiles = (max(2, d.shape[1] // 96), max(2, d.shape[0] // 96))
        clahe = cv2.createCLAHE(clipLimit=1.0 + 3.0 * lc, tileGridSize=tiles)
        d = clahe.apply(h16).astype(np.float32) / 65535.0
    boost = float(detail_boost or 0)
    if boost > 0:
        d = np.power(d, 1.0 - 0.45 * boost)              # gamma < 1 brightens recessed areas
    return np.clip(d, 0.0, 1.0)


def _build_graph(depth_name, photo_name, prompt, seed, lightning, steps, cfg):
    """The verified 2-image Qwen-Image-Edit-2511 topology (see room_mockup): image1 = the depth
    map (style/relief reference AND the sampling latent via FluxKontextImageScale → VAEEncode,
    denoise 1.0); image2 = the original photo (content reference). Both feed both edit encoders."""
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": _UNET}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": _CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": _VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "7": {"class_type": "LoadImage", "inputs": {"image": depth_name}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["7", 0]}},
        "15": {"class_type": "LoadImage", "inputs": {"image": photo_name}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": prompt}},
        "11": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": ""}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": "relief_ai/r", "images": ["13", 0]}},
    }
    model_ref = ["4", 0]
    if lightning:
        g["6"] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["4", 0], "lora_name": _LIGHTNING, "strength_model": 1.0}}
        model_ref = ["6", 0]
    g["12"] = {"class_type": "KSampler", "inputs": {
        "model": model_ref, "positive": ["10", 0], "negative": ["11", 0], "latent_image": ["9", 0],
        "seed": int(seed), "steps": int(steps), "cfg": float(cfg),
        "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}}
    return g


class ReliefAIFeature(Feature):
    id = "relief_ai"
    name = "2.5D Relief (AI)"
    description = ("Photo → depth map (shown live) → AI-refined high-detail 2.5D CNC height map "
                  "(Qwen-Image-Edit). Optional Clarity finish.")
    needs_comfy = True
    engine = "comfy"
    icon = "mountain"
    est_runtime = "~1–4 min"
    vram = "~10–11 GB"
    output_kinds = ["Height map PNG", "Depth map", "16-bit relief"]
    inputs = ["image"]
    params = [
        ParamSpec("detail_boost", "number", 0.3, "Detail boost", 0.0, 1.0, 0.05, control="slider",
                  help="Brightens hidden/recessed areas of the depth map so faint details (eyes, "
                       "leaves, ornaments) stay prominent in the final relief. 0 = raw depth."),
        ParamSpec("clarity_upscale", "bool", False, "Clarity upscale (Balanced)", control="switch",
                  help="After the AI relief, run Clarity Upscale (Balanced) — sharper + 2× size. "
                       "Needs the Clarity models installed (see the Clarity tab)."),
        ParamSpec("local_contrast", "number", 0.2, "Local contrast", 0.0, 1.0, 0.05, control="slider",
                  group="advanced",
                  help="CLAHE lift on the depth map — makes faint depth separations stand out "
                       "before the AI pass. 0 = off."),
        ParamSpec("tile_detail", "select", "medium", "Depth tile detail", group="advanced",
                  help="Depth-pass quality: finer tiling recovers more real detail (slower).",
                  choices=[{"value": "off", "label": "Off · 1 pass"}, {"value": "low", "label": "Low"},
                           {"value": "medium", "label": "Medium"}, {"value": "high", "label": "High"}]),
        ParamSpec("quality", "select", "fast", "AI quality", control="seg", group="advanced",
                  help="Fast = 4-step Lightning (fits 12 GB). High = 20-step, cfg 4, slower/cleaner.",
                  choices=[{"value": "fast", "label": "Fast · 4-step"},
                           {"value": "high", "label": "High · 20-step"}]),
        ParamSpec("steps", "number", 4, "Steps", 4, 8, 1, control="slider", group="advanced",
                  depends_on={"param": "quality", "value": "fast"},
                  help="Lightning sweet spot 4–8 (Fast only)."),
        ParamSpec("prompt", "text", "", "Extra instructions (optional)", group="advanced",
                  placeholder="e.g. 'keep the frame border plain'",
                  help="Appended to the built-in CNC height-map prompt."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random each run."),
    ]

    def run(self, inputs, params, out_dir):
        from backends import get_backend
        from pipeline import _GRIDS
        import relief_progress
        out_dir = Path(out_dir)

        client = ComfyUIClient()
        client.free()                                     # a prior Qwen run can hold ~10 GB → free
                                                          # ComfyUI BEFORE loading local depth models
        be = get_backend("auto")
        if getattr(be, "name", "") == "lite":
            raise RuntimeError("2.5D Relief (AI) needs the GPU depth models — open the Relief tab "
                               "and click Download models (~2.3 GB) first.")

        # ---- stage 1: local depth map (live-published to the canvas) ----
        td = params.get("tile_detail", "medium")
        grids = _GRIDS.get(td, _GRIDS["medium"])
        relief_progress.start(["Depth map", "AI relief"],
                              tiles_total=_count_passes(td, grids, face_crop=True))
        try:
            image = Image.open(inputs["image"]).convert("RGB")
            depth = be.estimate_depth(image, model="depth-anything", tiling=(td != "off"),
                                      grids=grids, face_crop=True,
                                      on_tile=relief_progress.tick_tile)
            d = np.asarray(depth, np.float32)
            lo, hi = np.percentile(d, [1, 99])            # spike-safe normalize; white = highest
            d = np.clip((d - lo) / (hi - lo + 1e-8), 0.0, 1.0)
            d = _tweak_depth(d, params.get("detail_boost", 0.3), params.get("local_contrast", 0.2))

            depth_path = out_dir / "depth_map.png"        # 8-bit RGB: ComfyUI LoadImage chokes on
            d8 = (d * 255.0 + 0.5).astype(np.uint8)       # 16-bit ('I;16' clips to white)
            Image.fromarray(d8, "L").convert("RGB").save(depth_path)
            # publish only AFTER the file is fully written — the <img> src is constant, so a 404
            # on a half-written file would never retry.
            relief_progress.set_preview(f"/api/jobs/{out_dir.name}/depth_map.png")

            # ---- stage 2: Qwen-Image-Edit refines depth+photo into the CNC height map ----
            relief_progress.phase(1)
            try:
                import models
                models.unload_all()                       # free the depth model for ComfyUI
            except Exception:
                pass
            relief_progress.stop()                        # comfy progress takes over from here
            client.free()

            depth_name = client.upload_image(str(depth_path))
            photo_name = client.upload_image(inputs["image"])

            boost = float(params.get("detail_boost") or 0)
            note = (params.get("prompt") or "").strip()
            prompt = _PROMPT + (_BOOST_LINE if boost >= 0.5 else "") + (f"\n{note}" if note else "")

            lightning = params.get("quality", "fast") != "high"
            steps = max(4, min(8, int(params.get("steps") or 4))) if lightning else 20
            cfg = 1.0 if lightning else 4.0
            seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

            graph = _build_graph(depth_name, photo_name, prompt, seed, lightning, steps, cfg)
            out = out_dir / "relief_ai.png"
            out.write_bytes(client.generate(graph, label="relief-ai", max_wait=900))

            # 16-bit grayscale export for CNC software (same pixels, wider container)
            g16_path = out_dir / "relief_16bit.png"
            g16 = (np.asarray(Image.open(out).convert("L"), np.uint16) * 257)
            import cv2
            cv2.imwrite(str(g16_path), g16)

            arts = {"image": str(out), "depth_map": str(depth_path), "relief_16bit": str(g16_path)}

            # ---- stage 3: optional Clarity finish (merge — keep the depth artifacts) ----
            if params.get("clarity_upscale", False):
                from .clarity import ClarityFeature
                cf = ClarityFeature()
                arts = {**arts, **cf.run({"image": str(out)}, cf.coerce({}), out_dir)}
            return arts
        finally:
            relief_progress.stop()
            relief_progress.set_preview(None)
