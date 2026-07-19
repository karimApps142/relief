"""
model_manager.py — check whether the relief GPU weights are present, and download
them on demand (the in-UI "Download models" button). Only meaningful on the GPU box.

The depth-based relief needs BiRefNet (subject masking) + a depth model. The default
depth model is Depth-Anything-V2, so those two are the CORE gate that flips the relief
backend from `lite` (crude CPU luminance) to `full`. Marigold (normals) is kept for the
legacy normals path but is NOT required for depth relief, so it does not gate `full`.
Sapiens / DA3 are selected per-run and download themselves on first use.
"""
import threading
from huggingface_hub import snapshot_download

HF_REPOS = {                                    # everything the relief stack can use
    "birefnet":         "ZhengPeng7/BiRefNet",
    "depth_anything":   "depth-anything/Depth-Anything-V2-Large-hf",
    "marigold_normals": "prs-eth/marigold-normals-v1-1",
    # Cutout's default background-removal model (BiRefNet_HR fine-tune, ~885 MB). NOT core:
    # it must never gate lite→full, or existing boxes would drop back to lite after an
    # update. transformers fetches it on first use if it isn't cached.
    "lucida":           "egeorcun/lucida",
}
# CORE = the minimum for full-quality depth relief; this is what gates lite→full.
CORE_REPOS = {k: HF_REPOS[k] for k in ("birefnet", "depth_anything")}

_lock = threading.Lock()
_task = {"running": False, "log": [], "error": None, "done": False}


# --------------------------------------------------------------------------- status
def _repo_present(repo) -> bool:
    try:
        snapshot_download(repo, local_files_only=True)
        return True
    except Exception:
        return False


def models_present() -> bool:
    """True once the CORE weights (BiRefNet + Depth-Anything-V2) are cached."""
    return all(_repo_present(r) for r in CORE_REPOS.values())


def status() -> dict:
    present = {name: _repo_present(repo) for name, repo in CORE_REPOS.items()}
    return {
        "installed": all(present.values()),
        "models": present,
        "busy": _task["running"],
        "log": _task["log"][-40:],
        "error": _task["error"],
        "done": _task["done"],
    }


# ------------------------------------------------------------------------- download
def download_models(progress=print, repos=None):
    """Download the given repos (CORE by default) into the local HF cache."""
    for name, repo in (repos or CORE_REPOS).items():
        progress(f"downloading {name} ({repo}) …")
        snapshot_download(repo)
    progress("done")


def _log(msg):
    with _lock:
        _task["log"].append(str(msg).rstrip())
        del _task["log"][:-200]


def download_async() -> bool:
    """Kick off a background download of the CORE relief weights. Returns False if a
    download is already running."""
    with _lock:
        if _task["running"]:
            return False
        _task.update(running=True, error=None, done=False, log=[])
    threading.Thread(target=_download_thread, daemon=True).start()
    return True


def _download_thread():
    try:
        download_models(progress=_log)
        with _lock:
            _task.update(running=False, done=True)
    except Exception as e:
        _log(f"ERROR: {e}")
        with _lock:
            _task.update(running=False, error=str(e), done=True)
