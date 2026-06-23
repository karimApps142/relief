"""
backends.py — pluggable inference backend.
  lite : pure CPU, NO models. Normals derived from image luminance.
         Runs on the MacBook. Crude quality — for testing the full
         pipeline + UI without downloading anything.
  full : real models (BiRefNet + StableNormal/Marigold + Depth Anything).
         Needs an NVIDIA GPU, requirements-gpu.txt, and downloaded weights.
Select with env var RELIEF_BACKEND=lite|full, or pass backend= explicitly.
"""
import os
import numpy as np
import cv2
from PIL import Image


def get_backend(name=None):
    name = name or os.environ.get("RELIEF_BACKEND", "lite")
    if name == "auto":                          # full if weights present, else lite
        import model_manager                    # light dep (huggingface_hub), no torch
        name = "full" if model_manager.models_present() else "lite"
    return FullBackend() if name == "full" else LiteBackend()


# ---------------- LITE (CPU, no models, Mac-friendly) ----------------
class LiteBackend:
    name = "lite"

    def remove_background(self, image: Image.Image) -> np.ndarray:
        # no real segmentation in lite mode: whole image is foreground
        return np.ones((image.height, image.width), np.float32)

    def estimate_normals(self, image: Image.Image, strength=2.5, **_) -> np.ndarray:
        rgb = np.asarray(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        gray = cv2.bilateralFilter(gray, d=-1, sigmaColor=0.1, sigmaSpace=5)
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=5)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=5)
        nx, ny, nz = -gx * strength, -gy * strength, np.ones_like(gray)
        n = np.stack([nx, ny, nz], -1)
        n /= (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8)
        return (n + 1.0) / 2.0                      # HxWx3 in [0,1]

    def estimate_depth(self, image: Image.Image):
        return None                                 # no depth fusion in lite mode

    def estimate_parts(self, image: Image.Image):
        return None                                 # no face parsing in lite mode


# ---------------- FULL (GPU, real models) ----------------
class FullBackend:
    name = "full"

    def __init__(self):
        import models                               # <-- lazy: only imported here
        self._m = models

    def remove_background(self, image):
        return self._m.remove_background(image)

    def estimate_normals(self, image, which="stable", **_):
        if which == "marigold":
            return self._m.estimate_normals_marigold(image)
        return self._m.estimate_normals_stable(image)

    def estimate_depth(self, image):
        return self._m.estimate_depth(image)

    def estimate_parts(self, image):
        try:
            return self._m.parse_regions(image)
        except Exception:
            return None                             # any parse failure -> feature off
