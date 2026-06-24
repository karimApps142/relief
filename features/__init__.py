"""
features/ — modular AI feature registry.

To add a feature (text2img, img2img, upscale, …):
  1. create features/<name>.py with a `Feature` subclass,
  2. import + register() it below.
The API (server.py) and UI enumerate REGISTRY automatically — no other changes.
"""
from .relief import ReliefFeature
from .text2img import Text2ImgFeature

REGISTRY = {}


def register(feature):
    REGISTRY[feature.id] = feature


register(ReliefFeature())
register(Text2ImgFeature())          # Krea-2-Turbo GGUF via ComfyUI (needs ComfyUI on :8188)
# Phase 3 — more drop-ins here:
# register(Img2ImgFeature())
# register(UpscaleFeature())
