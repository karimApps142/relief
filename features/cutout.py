"""features/cutout.py — background removal (BiRefNet). Local, reuses the relief matte.

A standalone cutout tool: subject on a transparent / black / white backdrop, plus the
soft mask. No ComfyUI, no extra models (BiRefNet is already part of the relief stack).
"""
from pathlib import Path
import numpy as np
from PIL import Image

from .base import Feature, ParamSpec


class CutoutFeature(Feature):
    id = "cutout"
    name = "Cutout"
    description = "Remove the background (BiRefNet) — transparent, black, or white backdrop + the mask."
    inputs = ["image"]
    engine = "local"
    icon = "scissors"
    est_runtime = "~2–10 s"
    vram = "~1 GB"
    output_kinds = ["Cutout PNG", "Mask PNG"]
    params = [
        ParamSpec("background", "select", "transparent", "Background", control="seg",
                  help="Backdrop for the isolated subject.",
                  choices=[{"value": "transparent", "label": "Transparent"},
                           {"value": "black", "label": "Black"}, {"value": "white", "label": "White"}]),
    ]

    def run(self, inputs, params, out_dir):
        from backends import get_backend
        be = get_backend("auto")
        image = Image.open(inputs["image"]).convert("RGB")
        mask = np.clip(np.asarray(be.remove_background(image), np.float32), 0.0, 1.0)
        if mask.shape[:2] != (image.height, image.width):
            import cv2
            mask = cv2.resize(mask, (image.width, image.height))
        rgb = np.asarray(image)
        out = Path(out_dir)
        bg = params.get("background", "transparent")
        if bg == "transparent":
            alpha = (mask * 255).astype(np.uint8)
            Image.fromarray(np.dstack([rgb, alpha]), "RGBA").save(out / "cutout.png")
        else:
            c = 0 if bg == "black" else 255
            m = mask[..., None]
            Image.fromarray((rgb * m + c * (1.0 - m)).astype(np.uint8)).save(out / "cutout.png")
        Image.fromarray((mask * 255).astype(np.uint8)).save(out / "mask.png")
        return {"cutout": str(out / "cutout.png"), "mask": str(out / "mask.png")}
