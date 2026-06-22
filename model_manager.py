"""
model_manager.py — check whether heavy weights are present, and download
them on demand (the "Download Models" button). Only meaningful on the GPU box.
"""
from huggingface_hub import snapshot_download

HF_REPOS = {
    "birefnet":         "ZhengPeng7/BiRefNet",
    "marigold_normals": "prs-eth/marigold-normals-v1-1",
    "depth_anything":   "depth-anything/Depth-Anything-V2-Large-hf",
}
# StableNormal loads via torch.hub and downloads on first inference call.


def models_present() -> bool:
    """True only if every repo is fully in the local HF cache."""
    for repo in HF_REPOS.values():
        try:
            snapshot_download(repo, local_files_only=True)
        except Exception:
            return False
    return True


def download_models(progress=print):
    for name, repo in HF_REPOS.items():
        progress(f"downloading {name} ({repo}) ...")
        snapshot_download(repo)
    try:                                            # warm StableNormal weights
        import torch
        torch.hub.load("Stable-X/StableNormal", "StableNormal", trust_repo=True)
    except Exception as e:
        progress(f"stablenormal warm skipped ({e}) — fine if using marigold")
    progress("done")
