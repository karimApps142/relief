"""features/room_mockup.py — place a CNC / bas-relief design onto a wall in a room photo.

Multi-image edit with Qwen-Image-Edit-2511 (up to 3 reference images):
  image1 = the customer's ROOM photo — the canvas; output keeps its perspective + lighting.
  image2 = the CNC DESIGN — the object to mount.
The model composites the design onto the wall as a REAL carved relief (genuine depth, cast
shadows, matched lighting), so it reads as a real installation photo rather than a flat paste.

Graph = the verified Qwen-Image-Edit-2511 topology (see features/image_edit.py) with a second
LoadImage wired into both TextEncodeQwenImageEditPlus nodes as image2. Reuses the same GGUF
models as Image Edit (comfy_manager.QWEN_EDIT_MODELS) — no extra download. Same 12 GB tricks:
client.free() first, Q3 unet, sequential offload, ~1 MP cap, 4-step Lightning.

Note: compositing into a real room photo (matched perspective + lighting) is the hard case —
it's good but not perfect every run; retry a seed or add a placement hint if the fit is off.
"""
import random
from pathlib import Path

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from .image_edit import _UNET, _CLIP, _VAE, _LIGHTNING

# material → how the carving should read (fed into the instruction)
_MATERIALS = {
    "wood": "carved wood relief with natural wood grain, warm tone",
    "marble": "carved polished white marble relief",
    "stone": "carved sandstone / stone relief, matte",
    "bronze": "cast bronze relief, patinated metal with subtle sheen",
    "plaster": "carved white plaster / gypsum relief, matte",
    "gold": "gilded gold-leaf relief with a soft metallic sheen",
}


# design-detail steer: prompt terms + how the Clarity finishing pass should behave. 'clean'
# fixes over-elaborated / noisy carvings; it also makes Clarity faithful so it sharpens without
# inventing extra micro-texture (the main source of a 'messy' look).
_DETAIL = {
    "clean": {"terms": (" The carving must be CLEAN and clearly defined — smooth clear forms, crisp "
                        "well-separated elements, uncluttered and elegant, with no messy or noisy micro-texture."),
              "clarity": {"creativity": 0.2, "resemblance": 0.9}},
    "balanced": {"terms": "", "clarity": {}},
    "ornate": {"terms": " Make the carving intricate, richly detailed and ornate.",
               "clarity": {"creativity": 0.45}},
}


def _cutout_design(design_path, out_dir):
    """Remove the CNC design's own background (BiRefNet, via the relief backend) and composite the
    bare motif onto clean white — so the edit model places ONLY the carving, not its rectangular
    slab/panel. Frees the local model before the ComfyUI run so it doesn't hold 12 GB VRAM. Returns
    the cutout path (or the original on any failure — cutout is best-effort)."""
    import numpy as np
    import cv2
    from PIL import Image
    try:
        from backends import get_backend
        img = Image.open(design_path).convert("RGB")
        mask = np.clip(np.asarray(get_backend("auto").remove_background(img), np.float32), 0.0, 1.0)
        if mask.shape[:2] != (img.height, img.width):
            mask = cv2.resize(mask, (img.width, img.height))
        arr = np.asarray(img, np.float32)
        comp = (arr * mask[..., None] + 255.0 * (1.0 - mask[..., None])).astype(np.uint8)  # motif on white
        p = Path(out_dir) / "design_cutout.png"
        Image.fromarray(comp).save(p)
        return str(p)
    except Exception as e:
        print(f"[room_mockup] design cutout skipped ({e}) — using the design as-is")
        return design_path
    finally:
        try:
            import models
            models.unload_all()                              # free BiRefNet before the ComfyUI gen
        except Exception:
            pass


def _build_graph(room_name, design_name, prompt, seed, lightning, steps, cfg):
    """image1 = FluxKontextImageScale(room) (also the VAEEncode sampling latent); image2 = the
    raw design LoadImage (the edit node scales references internally). Both TextEncode nodes
    receive image1 + image2 so the design is available as a reference latent."""
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": _UNET}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": _CLIP, "type": "qwen_image", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": _VAE}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.1}},
        "7": {"class_type": "LoadImage", "inputs": {"image": room_name}},
        "8": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["7", 0]}},
        "15": {"class_type": "LoadImage", "inputs": {"image": design_name}},
        "9": {"class_type": "VAEEncode", "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": prompt}},
        "11": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {
            "clip": ["2", 0], "vae": ["3", 0], "image1": ["8", 0], "image2": ["15", 0], "prompt": ""}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["3", 0]}},
        "14": {"class_type": "SaveImage", "inputs": {"filename_prefix": "mockup/m", "images": ["13", 0]}},
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


class RoomMockupFeature(Feature):
    id = "room_mockup"
    name = "Room Mockup"
    description = ("Place a CNC / bas-relief design onto a wall in your room photo — rendered as a "
                  "real carved relief with matched lighting (Qwen-Image-Edit).")
    needs_comfy = True
    engine = "comfy"
    icon = "frame"
    est_runtime = "~20–50 s"
    vram = "~10–11 GB"
    output_kinds = ["Room mockup"]
    inputs = ["image", "image2"]
    input_labels = {"image": "Room photo", "image2": "CNC design"}
    params = [
        ParamSpec("cutout_design", "bool", True, "Cut out design (natural integration)", control="switch",
                  help="Remove the design's own background first, so ONLY the carved motif is placed on the "
                       "wall — it reads as integrated art, not a slab stuck on. Off = paste the whole design "
                       "(with its background/panel) as a mounted panel."),
        ParamSpec("material", "select", "match", "Material",
                  help="What the carving is made of. 'Match wall' carves it in the wall's own tone/material "
                       "for the most natural, built-in look; the rest are distinct art materials.",
                  choices=[{"value": "match", "label": "Match wall (blend)"},
                           {"value": "wood", "label": "Wood"}, {"value": "marble", "label": "Marble"},
                           {"value": "stone", "label": "Stone"}, {"value": "bronze", "label": "Bronze"},
                           {"value": "plaster", "label": "Plaster"}, {"value": "gold", "label": "Gold"}]),
        ParamSpec("detail", "select", "balanced", "Design detail", control="seg",
                  help="Clean = crisp, well-defined, uncluttered carving — use this when it comes out "
                       "messy/noisy. Ornate = more intricate. Also tunes the Clarity pass so it sharpens "
                       "without inventing extra texture.",
                  choices=[{"value": "clean", "label": "Clean"}, {"value": "balanced", "label": "Balanced"},
                           {"value": "ornate", "label": "Ornate"}]),
        ParamSpec("prompt", "text", "", "Placement / notes (optional)",
                  placeholder="e.g. 'centered on the wall above the sofa, large'",
                  help="Where and how big to place it. Blank = the model picks a natural spot."),
        ParamSpec("quality", "select", "fast", "Quality", control="seg", group="advanced",
                  help="Fast = 4-step Lightning (fits 12 GB). High = 20-step, cfg 4, slower/cleaner.",
                  choices=[{"value": "fast", "label": "Fast · 4-step"}, {"value": "high", "label": "High · 20-step"}]),
        ParamSpec("steps", "number", 4, "Steps", 4, 8, 1, control="slider", group="advanced",
                  depends_on={"param": "quality", "value": "fast"},
                  help="Lightning sweet spot 4–8 (Fast only)."),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random. Retry a few seeds if the placement/perspective isn't right."),
        ParamSpec("clarity_upscale", "bool", True, "Clarity upscale (Balanced)", control="switch",
                  group="advanced",
                  help="After the mockup, run Clarity Upscale (Balanced) on the result — sharpens the whole "
                       "render and 2× size. Off to skip. Needs the Clarity models installed."),
    ]

    def run(self, inputs, params, out_dir):
        if not inputs.get("image2"):
            raise RuntimeError("Room Mockup needs BOTH images — a room photo and a CNC design.")
        out_dir = Path(out_dir)

        # optionally remove the design's own background BEFORE the edit (runs local BiRefNet, then
        # frees it) so only the carved motif is composited — not its rectangular slab.
        cutout = bool(params.get("cutout_design", True))
        design_path = _cutout_design(inputs["image2"], out_dir) if cutout else inputs["image2"]

        client = ComfyUIClient()
        client.free()                                        # clean 12 GB before the ~19 GB edit models
        room = client.upload_image(inputs["image"])
        design = client.upload_image(design_path)

        material = params.get("material", "match")
        if material == "match":                              # carve in the wall's own tone/material
            mat_phrase = ("the same material and colour as the wall — tone-matched to the wall's surface "
                          "and finish, as if the wall itself were carved in relief")
        else:
            mat_phrase = _MATERIALS.get(material, _MATERIALS["wood"])   # e.g. "carved wood relief …"
        note = (params.get("prompt") or "").strip()
        if cutout:
            prompt = (f"Carve ONLY the relief motif from the second image directly into the wall in the "
                      f"first image, in {mat_phrase}. There must be NO separate panel, board, frame or "
                      "rectangular background — just the carved motif, its edges blending naturally into the "
                      "wall, with a soft contact shadow and subtle ambient occlusion where it meets the "
                      "surface. Genuine relief depth, cast shadows and highlights matching the room's lighting "
                      "and perspective; seamless, photorealistic, natural.")
        else:
            prompt = (f"Mount the relief design from the second image onto the wall in the first image in "
                      f"{mat_phrase}. Give it genuine carved relief depth with cast shadows and highlights "
                      "matching the room's lighting and perspective; seamlessly integrated, photorealistic.")
        detail = _DETAIL.get(params.get("detail", "balanced"), _DETAIL["balanced"])
        prompt += detail["terms"]                            # steer clean vs ornate
        if note:
            prompt += f" {note}."

        lightning = params.get("quality", "fast") != "high"
        steps = max(4, min(8, int(params.get("steps") or 4))) if lightning else 20
        cfg = 1.0 if lightning else 4.0
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        graph = _build_graph(room, design, prompt, seed, lightning, steps, cfg)
        out = Path(out_dir) / "room_mockup.png"
        out.write_bytes(client.generate(graph, label="room-mockup", max_wait=900))

        # optional finishing pass: reuse the Clarity feature to sharpen. 'Clean' makes it faithful
        # (low creativity) so it crisps the render instead of adding invented micro-texture.
        if params.get("clarity_upscale", True):
            from .clarity import ClarityFeature
            cf = ClarityFeature()
            return cf.run({"image": str(out)}, cf.coerce(detail["clarity"]), out_dir)
        return {"image": str(out)}
