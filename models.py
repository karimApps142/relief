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
               _face_parser, _sapiens_depth, _sapiens_normal, _da3,
               _face_restore_model, _face_helper):
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
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    repo = "depth-anything/Depth-Anything-V2-Large-hf"
    proc = AutoImageProcessor.from_pretrained(repo)
    model = AutoModelForDepthEstimation.from_pretrained(repo).to(DEVICE).eval()
    return proc, model


def estimate_depth(image: Image.Image, input_size: int = 518) -> np.ndarray:
    """Depth-Anything-V2-Large. `input_size` = the model working resolution; the
    tiling wrapper raises it per tile (~768) so each crop yields finer relief.
    Returns HxW [0,1] at the input resolution (near = high)."""
    proc, model = _depth_pipe()
    img = image.convert("RGB")
    W0, H0 = img.size
    s = max(14, int(round(input_size / 14)) * 14)        # multiple of 14 (DPT patch size)
    try:
        inputs = proc(images=img, size={"height": s, "width": s}, return_tensors="pt")
    except Exception:
        inputs = proc(images=img, return_tensors="pt")   # fall back to processor default
    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}
    with torch.inference_mode():
        pred = model(**inputs).predicted_depth
    if pred.dim() == 3:
        pred = pred.unsqueeze(1)                          # (1,h,w) -> (1,1,h,w)
    d = torch.nn.functional.interpolate(pred, size=(H0, W0), mode="bicubic",
                                        align_corners=False)[0, 0].float().cpu().numpy()
    return (d - d.min()) / (d.max() - d.min() + 1e-8)


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


# ---------- Surface normals: Sapiens-1B (human-specialist, sharpest faces/hair) ----------
_SAPIENS_NORMAL_REPO = "facebook/sapiens-normal-1b-torchscript"
_SAPIENS_NORMAL_FILE = "sapiens_1b_normal_render_people_epoch_115_torchscript.pt2"


@functools.lru_cache(maxsize=1)
def _sapiens_normal():
    from huggingface_hub import hf_hub_download
    path = hf_hub_download(_SAPIENS_NORMAL_REPO, _SAPIENS_NORMAL_FILE)
    return torch.jit.load(path, map_location=DEVICE).eval()


def estimate_normals_sapiens(image: Image.Image) -> np.ndarray:
    """Per-pixel surface normals from Sapiens-1B (trained on human 3D scans → the
    crispest facial/hair normals among the options). Returns HxWx3 in [0,1], camera
    frame, with +Z forced toward the camera so it's compatible with integrate_normals
    regardless of the model's sign convention (front-facing detail raises, not carves)."""
    from torchvision import transforms
    img = image.convert("RGB"); W0, H0 = img.size
    tf = transforms.Compose([
        transforms.Resize((1024, 768)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = tf(img).unsqueeze(0).to(DEVICE)
    with torch.inference_mode():
        out = _sapiens_normal()(x)                  # (1,3,H,W) normals
    if out.dim() == 3:
        out = out.unsqueeze(0)
    out = torch.nn.functional.interpolate(out[:, :3], size=(H0, W0),
                                          mode="bilinear", align_corners=False)
    n = out.float().squeeze(0).permute(1, 2, 0).cpu().numpy()    # HxWx3
    n = n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-8)   # unit normals
    if float(np.nanmean(n[..., 2])) < 0:            # ensure +Z faces the camera
        n = -n
    return ((n + 1.0) / 2.0).astype(np.float32)     # -> [0,1]


# ---------- Face restoration (GFPGAN weights via spandrel + facexlib; NO basicsr) ----------
# basicsr breaks on torchvision>=0.17 (functional_tensor removed) and numpy 2, so we drive
# the GFPGAN network through spandrel (clean loader) and use facexlib for detect/align/paste
# — the same libraries ComfyUI uses. Faces are restored; the background is left untouched.
_GFPGAN_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"


@functools.lru_cache(maxsize=1)
def _face_restore_model():
    from pathlib import Path
    from spandrel import ModelLoader
    cache = Path(torch.hub.get_dir()) / "facerestore"
    cache.mkdir(parents=True, exist_ok=True)
    mp = cache / "GFPGANv1.4.pth"
    if not mp.exists():
        torch.hub.download_url_to_file(_GFPGAN_URL, str(mp))
    return ModelLoader().load_from_file(str(mp)).to(DEVICE).eval()


@functools.lru_cache(maxsize=1)
def _face_helper():
    from facexlib.utils.face_restoration_helper import FaceRestoreHelper
    return FaceRestoreHelper(upscale_factor=1, face_size=512, crop_ratio=(1, 1),
                             det_model="retinaface_resnet50", save_ext="png",
                             use_parse=True, device=DEVICE)


def restore_faces(image: Image.Image, weight: float = 0.5) -> np.ndarray:
    """Detect every face, restore it with GFPGAN, paste back onto the original image.
    `weight` 0..1 blends restored↔original (0 = full restoration, 1 = untouched).
    Returns an RGB ndarray. No-op (returns the input) if no face is detected."""
    helper = _face_helper()
    model = _face_restore_model()
    bgr = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    helper.clean_all()
    helper.read_image(bgr)
    helper.get_face_landmarks_5(only_center_face=False, resize=640, eye_dist_threshold=5)
    helper.align_warp_face()
    for cropped in helper.cropped_faces:                  # BGR uint8 512x512
        t = (torch.from_numpy(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
             .float().div(255.0).permute(2, 0, 1).unsqueeze(0).to(DEVICE))
        with torch.inference_mode():
            out = _spandrel_call(model, t)
        rgb = (out.clamp(0, 1).squeeze(0).permute(1, 2, 0).cpu().numpy() * 255).astype(np.uint8)
        restored = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        if weight and weight > 0:                         # fidelity blend toward original
            restored = cv2.addWeighted(restored, 1.0 - weight, cropped, weight, 0)
        helper.add_restored_face(restored)
    helper.get_inverse_affine(None)
    result = helper.paste_faces_to_input_image()
    return cv2.cvtColor(result, cv2.COLOR_BGR2RGB)


def _spandrel_call(model, t):
    """Call a spandrel descriptor across versions (descriptor is callable; fall back to .model)."""
    try:
        return model(t)
    except Exception:
        return model.model(t)


# ---------- Depth: Depth Anything 3 (ByteDance, SOTA monocular/geometry) ----------
# Uses the standalone `depth_anything_3` package (NOT transformers). Install on the
# box once:  pip install xformers
#            pip install git+https://github.com/ByteDance-Seed/Depth-Anything-3
# CC-BY-NC. DA3-LARGE ~0.35B, fits 12 GB. inference([path]) -> prediction.depth [1,H,W].
_DA3_DEFAULT = "DA3-LARGE"


@functools.lru_cache(maxsize=1)
def _da3(repo):
    # DA3's api.py eagerly imports its multi-view / video / point-cloud EXPORT
    # stack (moviepy, open3d, pycolmap, …) at module load. We only need monocular
    # depth (inference().depth) and never call those exporters, so stub them with
    # mocks instead of installing them — open3d in particular would force numpy<2
    # and break the cu121 stack. The depth path never touches these.
    import sys
    from unittest.mock import MagicMock
    for _m in ("moviepy", "moviepy.editor", "open3d", "pycolmap", "evo",
               "pillow_heif", "gsplat",
               "depth_anything_3.utils.export",      # whole export chain (gs/ply/video/matplotlib)
               "depth_anything_3.utils.pose_align"):  # multi-view pose alignment (evo)
        sys.modules.setdefault(_m, MagicMock())
    from depth_anything_3.api import DepthAnything3
    return DepthAnything3.from_pretrained(repo).to(device=DEVICE)


def estimate_depth_da3(image: Image.Image, variant: str = _DA3_DEFAULT) -> np.ndarray:
    """Monocular depth from Depth Anything 3 (single image), mapped back to the
    input resolution. Returns HxW float where LARGER = NEARER (matches the other
    depth backends). `variant` selects the hub repo, e.g. DA3MONO-LARGE / DA3-GIANT."""
    import tempfile
    import os as _os
    img = image.convert("RGB")
    W0, H0 = img.size
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
    img.save(tmp)
    try:
        pred = _da3("depth-anything/" + variant).inference([tmp])
    finally:
        try:
            _os.unlink(tmp)
        except OSError:
            pass
    d = pred.depth
    if hasattr(d, "detach"):
        d = d.detach().float().cpu().numpy()
    d = np.asarray(d, dtype=np.float32).squeeze()       # [1,H,W] -> HxW
    if d.shape[:2] != (H0, W0):
        d = cv2.resize(d, (W0, H0))
    return -d                                           # negate -> larger = nearer
