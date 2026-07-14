"""depth_worker.py — the depth stage of the 2.5D Relief (AI) pipeline, run as a SUBPROCESS.

Why a separate process: once PyTorch runs a model on CUDA it keeps a ~0.5–1 GB context alive
for the life of the process, and `torch.cuda.empty_cache()` cannot release it. If the FastAPI
server ran Depth-Anything in-process, that leftover context would shrink ComfyUI's free VRAM
below what the tight ~11 GB Qwen-Image-Edit stage needs on a 12 GB card → OOM crash mid-run
("ComfyUI not reachable"). Running depth here means the whole CUDA context frees when this
process exits, handing the full 12 GB to ComfyUI — the server itself never touches torch.

Protocol (stdout, line-buffered): prints `TILE` per depth forward-pass so the parent can drive
the progress bar, `DONE` on success. Exit code 2 = lite/no weights (parent also guards). Any
error text goes to stdout too (parent merges stderr) and the exit code is non-zero.
"""
import argparse
import sys

import numpy as np
import cv2
from PIL import Image


def _tweak_depth(d, boost, contrast):
    """CLAHE lift then a gamma lift that brightens dark/recessed depth so hidden details stay
    prominent. Mirrors features/relief_ai._tweak_depth (kept standalone so this worker doesn't
    import the heavy features package). Both are monotone; 0 = untouched."""
    d = np.clip(d, 0.0, 1.0).astype(np.float32)
    if contrast > 0:
        h16 = (d * 65535.0).astype(np.uint16)
        tiles = (max(2, d.shape[1] // 96), max(2, d.shape[0] // 96))
        clahe = cv2.createCLAHE(clipLimit=1.0 + 3.0 * contrast, tileGridSize=tiles)
        d = clahe.apply(h16).astype(np.float32) / 65535.0
    if boost > 0:
        d = np.power(d, 1.0 - 0.45 * boost)
    return np.clip(d, 0.0, 1.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tile", default="medium")
    ap.add_argument("--boost", type=float, default=0.3)
    ap.add_argument("--contrast", type=float, default=0.2)
    a = ap.parse_args()

    from backends import get_backend          # loads models/torch HERE, in the disposable subprocess
    from pipeline import _GRIDS
    be = get_backend("auto")
    if getattr(be, "name", "") == "lite":
        sys.exit(2)

    grids = _GRIDS.get(a.tile, _GRIDS["medium"])
    img = Image.open(a.image).convert("RGB")
    depth = be.estimate_depth(img, model="depth-anything", tiling=(a.tile != "off"),
                              grids=grids, face_crop=True,
                              on_tile=lambda n=1: print("TILE", flush=True))
    d = np.asarray(depth, np.float32)
    lo, hi = np.percentile(d, [1, 99])                       # spike-safe; white = highest relief
    d = np.clip((d - lo) / (hi - lo + 1e-8), 0.0, 1.0)
    d = _tweak_depth(d, a.boost, a.contrast)
    # 8-bit RGB: ComfyUI LoadImage chokes on 16-bit ('I;16' clips to white)
    Image.fromarray((d * 255.0 + 0.5).astype(np.uint8), "L").convert("RGB").save(a.out)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
