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

# Prompt matched to THIS pipeline's two inputs: image1 = the generated DEPTH MAP, image2 = the
# original PHOTO. (The original style-transfer prompt assumed image1 was an example carving, so it
# told the model to copy a non-existent "carving style" from a smooth depth map and it just
# reproduced the photo.) Goal: depth hierarchy from image1 + real detail from image2 → height map.
_PROMPT = """You are given two inputs of the SAME subject:
- Image 1 is a grayscale DEPTH MAP: white = closest / highest, black = farthest / deepest.
- Image 2 is the original PHOTO, which carries the true shapes and fine detail.

TASK: produce a clean, professional CNC bas-relief GRAYSCALE HEIGHT MAP of the subject. The output MUST be a grayscale height map — never the photo, a painting, a colored image, or a flat copy of either input.

Use Image 1's depth to set a smooth, correct front-to-back height hierarchy, and use Image 2 to recover the subject's real shapes and details (eyes, eyelids, nostrils, lips, hair, mane, leaves, flowers, ornaments), giving each clear depth separation using grayscale ONLY.

Height-map rules:
- Grayscale only. White (#FFFFFF) = highest relief, black (#000000) = deepest. Every gray value represents physical height and nothing else.
- Perfectly smooth, machinable, CNC-ready surfaces; crisp edges and smooth depth transitions.
- Preserve all real sculpted detail while keeping surfaces mathematically smooth. Do NOT add or invent detail.
- NO color, lighting, shadows, reflections, or ambient occlusion. NO surface noise, grain, bumps, orange-peel, fabric texture, skin pores, procedural/AI micro-texture, scratches, or random high-frequency detail.
- Do NOT return the original photo or a near-copy of the input — it must be a true grayscale height map.

Final output: a production-quality grayscale CNC bas-relief height map of the subject, perfectly smooth machinable surfaces, with zero unwanted texture or noise."""

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
        import subprocess
        import sys as _sys
        import model_manager
        import relief_progress
        from pipeline import _GRIDS
        out_dir = Path(out_dir)
        repo_root = Path(__file__).resolve().parent.parent

        client = ComfyUIClient()
        client.free()

        # Lite guard WITHOUT importing torch (models_present only checks the HF cache) — so the
        # server process never initialises a CUDA context that would compete with the Qwen stage.
        if not model_manager.models_present():
            raise RuntimeError("2.5D Relief (AI) needs the GPU depth models — open the Relief tab "
                               "and click Download models (~2.3 GB) first.")

        td = params.get("tile_detail", "medium")
        grids = _GRIDS.get(td, _GRIDS["medium"])
        boost = float(params.get("detail_boost", 0.3) or 0)
        lc = float(params.get("local_contrast", 0.2) or 0)
        depth_path = out_dir / "depth_map.png"
        relief_progress.start(["Depth map", "AI relief"],
                              tiles_total=_count_passes(td, grids, face_crop=True))
        try:
            # ---- stage 1: depth in a SUBPROCESS. Its CUDA context frees on exit, so the full
            #      12 GB is available for the Qwen stage (see depth_worker.py). Stdout drives the
            #      per-tile bar. ----
            proc = subprocess.Popen(
                [_sys.executable, str(repo_root / "depth_worker.py"),
                 "--image", str(inputs["image"]), "--out", str(depth_path),
                 "--tile", td, "--boost", str(boost), "--contrast", str(lc)],
                cwd=str(repo_root), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            tail = []
            for line in proc.stdout:                      # TILE per pass → tick; keep other lines
                line = line.strip()
                if line == "TILE":
                    relief_progress.tick_tile()
                elif line and line != "DONE":
                    tail.append(line); del tail[:-20]
            proc.wait()
            if proc.returncode == 2:
                raise RuntimeError("2.5D Relief (AI) needs the GPU depth models — download them "
                                   "from the Relief tab first.")
            if proc.returncode != 0 or not depth_path.exists():
                raise RuntimeError("Depth stage failed: "
                                   + (" | ".join(tail[-6:]) or f"exit {proc.returncode}"))
            # publish only AFTER the file is written — the <img> src is constant, so a 404 on a
            # half-written file would never retry.
            relief_progress.set_preview(f"/api/jobs/{out_dir.name}/depth_map.png")

            # ---- stage 2: Qwen-Image-Edit refines depth+photo into the CNC height map ----
            relief_progress.phase(1)
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
