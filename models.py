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
    for fn in (_birefnet, _stablenormal, _marigold_normals, _depth_pipe,
               _face_parser, _sapiens_depth):
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


# ---------- Stage 3 (optional): face parsing for per-material detail ----------
# jonathandinu/face-parsing — SegFormer (mit-b5) on CelebAMask-HQ, 19 classes,
# ~339 MB. Loads via the same transformers classes used above. Logits are
# H/4 x W/4: bilinear-upsample to input size BEFORE argmax. License: non-
# commercial research/education (CelebAMask-HQ heritage). Class indices verified
# against the model's config.json id2label.
_FACE_PARSE_ID = "jonathandinu/face-parsing"

# raw CelebAMask-HQ class id -> our 6 relief regions
_REGION_CLASSES = {
    "hair":  {13},
    "skin":  {1, 2, 8, 9, 17},          # skin, nose, ears, neck
    "eyes":  {3, 4, 5, 6, 7},           # glasses, eyes, brows
    "lips":  {10, 11, 12},              # mouth, upper/lower lip
    "cloth": {18},
    "bg":    {0, 14, 15, 16},           # background, hat, earring, necklace
}

# per-region feather widths in px (hair wide for a clean hairline)
_FEATHER_PX = {"hair": 11.0, "skin": 8.0, "eyes": 5.0,
               "lips": 4.0, "cloth": 8.0, "bg": 10.0}


@functools.lru_cache(maxsize=1)
def _face_parser():
    from transformers import (SegformerImageProcessor,
                              SegformerForSemanticSegmentation)
    proc = SegformerImageProcessor.from_pretrained(_FACE_PARSE_ID)
    model = SegformerForSemanticSegmentation.from_pretrained(_FACE_PARSE_ID)
    return proc, model.to(DEVICE).eval()


def _feather(binary, width):
    """Binary mask -> smooth [0,1] blend weight (Gaussian feather)."""
    m = (binary > 0).astype(np.float32)
    if width <= 0:
        return m
    return np.clip(cv2.GaussianBlur(m, (0, 0), max(0.3, width * 0.5)), 0.0, 1.0)


def parse_regions(image: Image.Image):
    """{region: feathered float32 HxW [0,1]} for the 6 regions, or None if no
    usable face is found (caller treats None as 'per-material disabled')."""
    image = image.convert("RGB")
    proc, model = _face_parser()
    with torch.no_grad():
        inputs = proc(images=image, return_tensors="pt").to(DEVICE)
        logits = model(**inputs).logits                       # (1,19,H/4,W/4)
        up = torch.nn.functional.interpolate(
            logits, size=image.size[::-1],                    # (H,W); image.size is (W,H)
            mode="bilinear", align_corners=False)
        labels = up.argmax(dim=1)[0].to("cpu").numpy().astype(np.uint8)
    # face-presence guard: skin+eyes+lips coverage must be non-trivial
    face_ids = list(_REGION_CLASSES["skin"] | _REGION_CLASSES["eyes"]
                    | _REGION_CLASSES["lips"])
    if np.isin(labels, face_ids).mean() < 0.02:              # face absent / too small
        return None
    return {region: _feather(np.isin(labels, list(ids)), _FEATHER_PX[region])
            for region, ids in _REGION_CLASSES.items()}


# ---------- Depth: Sapiens-1B (Meta, human-specialized; best portrait depth) ----------
# torchscript checkpoint (not transformers). Native input 1024x768 (H x W),
# ImageNet normalize. Output is relative depth; we negate so LARGER = NEARER to
# match the Depth-Anything convention (subject/face = high). ~4 GB download.
# License: CC-BY-NC (non-commercial research/education).
_SAPIENS_DEPTH_REPO = "facebook/sapiens-depth-1b-torchscript"
_SAPIENS_DEPTH_FILE = "sapiens_1b_render_people_epoch_88_torchscript.pt2"


@functools.lru_cache(maxsize=1)
def _sapiens_depth():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(_SAPIENS_DEPTH_REPO, _SAPIENS_DEPTH_FILE)
    return torch.jit.load(path, map_location=DEVICE).eval()


def estimate_depth_sapiens(image: Image.Image) -> np.ndarray:
    """Relative depth from Sapiens-1B (torchscript). Resized to the model's
    native 1024x768, output mapped back to the original resolution. Returns an
    HxW float where LARGER = NEARER (subject/face high)."""
    from torchvision import transforms
    img = image.convert("RGB")
    W0, H0 = img.size
    tf = transforms.Compose([
        transforms.Resize((1024, 768)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = tf(img).unsqueeze(0).to(DEVICE)
    with torch.inference_mode():
        out = _sapiens_depth()(x)
    if out.dim() == 3:                              # (1,H,W) -> (1,1,H,W)
        out = out.unsqueeze(1)
    out = torch.nn.functional.interpolate(out[:, :1], size=(H0, W0),
                                          mode="bilinear", align_corners=False)
    d = out.float().squeeze().cpu().numpy()         # HxW relative depth (near = small)
    return -d                                       # negate -> larger = nearer
