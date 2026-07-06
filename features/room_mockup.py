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
    icon = "image"
    est_runtime = "~20–50 s"
    vram = "~10–11 GB"
    output_kinds = ["Room mockup"]
    inputs = ["image", "image2"]
    input_labels = {"image": "Room photo", "image2": "CNC design"}
    params = [
        ParamSpec("material", "select", "wood", "Material", control="seg",
                  help="What the carving is made of — drives its look on the wall.",
                  choices=[{"value": "wood", "label": "Wood"}, {"value": "marble", "label": "Marble"},
                           {"value": "stone", "label": "Stone"}, {"value": "bronze", "label": "Bronze"},
                           {"value": "plaster", "label": "Plaster"}, {"value": "gold", "label": "Gold"}]),
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
    ]

    def run(self, inputs, params, out_dir):
        if not inputs.get("image2"):
            raise RuntimeError("Room Mockup needs BOTH images — a room photo and a CNC design.")
        client = ComfyUIClient()
        client.free()                                        # clean 12 GB before the ~19 GB edit models
        room = client.upload_image(inputs["image"])
        design = client.upload_image(inputs["image2"])

        mat = _MATERIALS.get(params.get("material", "wood"), _MATERIALS["wood"])
        note = (params.get("prompt") or "").strip()
        prompt = ("Mount the relief design from the second image onto the wall in the first image as a "
                  f"real {mat}. Give it genuine carved relief depth with cast shadows and highlights that "
                  "match the room's lighting and perspective; seamlessly integrated, photorealistic, natural.")
        if note:
            prompt += f" {note}."

        lightning = params.get("quality", "fast") != "high"
        steps = max(4, min(8, int(params.get("steps") or 4))) if lightning else 20
        cfg = 1.0 if lightning else 4.0
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        graph = _build_graph(room, design, prompt, seed, lightning, steps, cfg)
        out = Path(out_dir) / "room_mockup.png"
        out.write_bytes(client.generate(graph, label="room-mockup", max_wait=900))
        return {"image": str(out)}
