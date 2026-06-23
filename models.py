"""
models.py — model wrappers. Each loader is lazy + cached. For a low-VRAM
local GPU, call unload_all() between stages so peak VRAM ≈ the single
heaviest model instead of the sum.

GPU box only — imported lazily by backends.FullBackend, never on the Mac.
Needs requirements-gpu.txt (torch/diffusers/transformers).
"""
import functools
import gc
import numpy as np
import cv2
import torch
from PIL import Image

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def unload_all():
    """Free cached models + VRAM. Call between heavy stages on small GPUs."""
    for fn in (_birefnet, _stablenormal, _marigold_normals, _depth_pipe):
        fn.cache_clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


# ---------- Stage 0: background removal (BiRefNet, MIT) ----------
@functools.lru_cache(maxsize=1)
def _birefnet():
    from transformers import AutoModelForImageSegmentation
    m = AutoModelForImageSegmentation.from_pretrained(
        "ZhengPeng7/BiRefNet", trust_remote_code=True
    ).to(DEVICE)
    # transformers >=5 loads the checkpoint in its native fp16; remove_background
    # feeds an fp32 tensor, so force fp32 to avoid "Input type (float) and bias
    # type (c10::Half) should be the same" in the first conv. fp32 BiRefNet is
    # only ~0.9 GB — fine on the 12 GB 3060, and keeps the mask in fp32 for cv2.
    return m.float().eval()


def remove_background(image: Image.Image) -> np.ndarray:
    """Return a soft foreground mask HxW in [0,1]."""
    from torchvision import transforms
    tf = transforms.Compose([
        transforms.Resize((1024, 1024)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = tf(image).unsqueeze(0).to(DEVICE)
    with torch.no_grad():
        pred = _birefnet()(x)[-1].sigmoid().cpu()[0, 0].numpy()
    return cv2.resize(pred, image.size)  # back to (W,H)


# ---------- Stage 1: surface normals ----------
# Option A — StableNormal (best detail). Returns a PIL normal map.
@functools.lru_cache(maxsize=1)
def _stablenormal():
    return torch.hub.load("Stable-X/StableNormal", "StableNormal",
                          trust_repo=True)


def estimate_normals_stable(image: Image.Image) -> np.ndarray:
    normal_pil = _stablenormal()(image)
    return np.asarray(normal_pil).astype(np.float32) / 255.0  # HxWx3 [0,1]


# Option B — Marigold-Normals v1-1 (full quality, more steps = sharper).
@functools.lru_cache(maxsize=1)
def _marigold_normals():
    from diffusers import MarigoldNormalsPipeline
    return MarigoldNormalsPipeline.from_pretrained(
        "prs-eth/marigold-normals-v1-1",
        torch_dtype=torch.float16,
    ).to(DEVICE)


def estimate_normals_marigold(image: Image.Image) -> np.ndarray:
    out = _marigold_normals()(image, num_inference_steps=10, ensemble_size=5)
    n = np.asarray(out.prediction[0])          # HxWx3 in [-1,1]
    return (n + 1.0) / 2.0                       # -> [0,1]


# ---------- Stage 2 (optional): depth for global form ----------
@functools.lru_cache(maxsize=1)
def _depth_pipe():
    from transformers import pipeline
    return pipeline("depth-estimation",
                    model="depth-anything/Depth-Anything-V2-Large-hf",
                    device=0 if DEVICE == "cuda" else -1)


def estimate_depth(image: Image.Image) -> np.ndarray:
    d = np.asarray(_depth_pipe()(image)["depth"]).astype(np.float32)
    return (d - d.min()) / (d.max() - d.min() + 1e-8)  # HxW [0,1]
