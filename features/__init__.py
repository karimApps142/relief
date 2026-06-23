"""
features/ — modular AI feature registry.

To add a feature (text2img, img2img, upscale, …):
  1. create features/<name>.py with a `Feature` subclass,
  2. import + register() it below.
The API (server.py) and UI enumerate REGISTRY automatically — no other changes.
"""
from .relief import ReliefFeature

REGISTRY = {}


def register(feature):
    REGISTRY[feature.id] = feature


register(ReliefFeature())
# Phase 3 — drop-in here:
# register(Text2ImgFeature())
# register(Img2ImgFeature())
# register(UpscaleFeature())
