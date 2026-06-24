"""
comfy_manager.py — make ComfyUI an *invisible managed dependency* of our app.

Install it, download the model files, launch it headless, and report status — all
driven from our own UI/API so the user never touches ComfyUI directly. Box-side
work (the heavy bits no-op cleanly off the box).

  status()          -> dict: installed / running / per-model presence / task log
  install_async()   -> git clone ComfyUI + ComfyUI-GGUF, pip install (background)
  download_async()  -> fetch the 4 model files into ComfyUI/models/* (background)
  start()           -> launch ComfyUI headless on COMFYUI_URL if down
  ensure_running()  -> best-effort start before a ComfyUI-backed feature runs

Locations are env-configurable:
  COMFYUI_DIR  (default: <repo-parent>/ComfyUI)   COMFYUI_URL (default 127.0.0.1:8188)
"""
import os
import sys
import time
import shutil
import threading
import subprocess
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
COMFY_DIR = Path(os.environ.get("COMFYUI_DIR", _ROOT.parent / "ComfyUI")).resolve()
COMFY_URL = os.environ.get("COMFYUI_URL", "127.0.0.1:8188")
_HOST, _PORT = (COMFY_URL.split(":") + ["8188"])[:2]

COMFY_GIT = "https://github.com/comfyanonymous/ComfyUI"
GGUF_GIT = "https://github.com/city96/ComfyUI-GGUF"

# label -> (hf_repo, path_within_repo, dest_subdir_under_ComfyUI/models)
# path_within_repo may contain a subfolder; only the basename lands in dest.
MODELS = {
    "transformer · Krea-2-Turbo Q4_K_M (~7.5 GB)":
        ("vantagewithai/Krea-2-Turbo-GGUF", "krea2_turbo-Q4_K_M.gguf", "unet"),
    "text encoder · Qwen3-VL 4B (~4 GB)":
        ("Comfy-Org/Qwen3-VL", "text_encoders/qwen3vl_4b_fp8_scaled.safetensors", "text_encoders"),
    "VAE · qwen_image (~0.25 GB)":
        ("Comfy-Org/Qwen-Image_ComfyUI", "split_files/vae/qwen_image_vae.safetensors", "vae"),
    "upscaler · 4x-UltraSharp (~67 MB)":
        ("lokCX/4x-Ultrasharp", "4x-UltraSharp.pth", "upscale_models"),
}

_proc = None                                              # the launched ComfyUI process
_lock = threading.Lock()
_task = {"action": None, "running": False, "log": [], "error": None, "done": False}


# --------------------------------------------------------------------------- state
def _log(msg):
    with _lock:
        _task["log"].append(str(msg).rstrip())
        del _task["log"][:-300]                           # keep the tail bounded


def _dest(subdir, path_in_repo):
    return COMFY_DIR / "models" / subdir / Path(path_in_repo).name


def is_installed():
    return (COMFY_DIR / "main.py").exists()


def is_running(timeout=1.5):
    try:
        urllib.request.urlopen(f"http://{COMFY_URL}/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def models_status():
    return {label: _dest(sub, p).exists() for label, (_, p, sub) in MODELS.items()}


def status():
    installed = is_installed()
    return {
        "installed": installed,
        "running": is_running() if installed else False,
        "dir": str(COMFY_DIR),
        "url": COMFY_URL,
        "models": models_status(),
        "busy": _task["running"],
        "action": _task["action"],
        "log": _task["log"][-60:],
        "error": _task["error"],
        "done": _task["done"],
    }


# ----------------------------------------------------------------------- task plumbing
def _begin(action):
    with _lock:
        if _task["running"]:
            return False
        _task.update(action=action, running=True, error=None, done=False, log=[])
        return True


def _end(error=None):
    with _lock:
        _task.update(running=False, error=error, done=True)


def _run(cmd, cwd=None):
    """Run a subprocess, streaming its output into the task log."""
    _log("$ " + " ".join(str(c) for c in cmd))
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in p.stdout:
        _log(line)
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"`{cmd[0]} …` exited {p.returncode}")


# --------------------------------------------------------------------------- install
def install_async():
    if not _begin("install"):
        return False
    threading.Thread(target=_install, daemon=True).start()
    return True


def _install():
    try:
        py = sys.executable
        COMFY_DIR.parent.mkdir(parents=True, exist_ok=True)
        if not is_installed():
            _log(f"cloning ComfyUI -> {COMFY_DIR}")
            _run(["git", "clone", "--depth", "1", COMFY_GIT, str(COMFY_DIR)])
        gguf = COMFY_DIR / "custom_nodes" / "ComfyUI-GGUF"
        if not gguf.exists():
            _log("cloning ComfyUI-GGUF custom node")
            _run(["git", "clone", "--depth", "1", GGUF_GIT, str(gguf)])
        _log("installing ComfyUI requirements (this can take a few minutes)…")
        _run([py, "-m", "pip", "install", "-r", str(COMFY_DIR / "requirements.txt")])
        _run([py, "-m", "pip", "install", "-r", str(gguf / "requirements.txt")])
        _log("✓ ComfyUI installed")
        _end()
    except Exception as e:
        _log(f"ERROR: {e}")
        _end(str(e))


# -------------------------------------------------------------------------- downloads
def download_async(labels=None):
    if not _begin("download"):
        return False
    threading.Thread(target=_download, args=(labels,), daemon=True).start()
    return True


def _download(labels):
    try:
        from huggingface_hub import hf_hub_download
        items = MODELS if not labels else {k: MODELS[k] for k in labels if k in MODELS}
        for label, (repo, path_in_repo, sub) in items.items():
            dest_dir = COMFY_DIR / "models" / sub
            dest_dir.mkdir(parents=True, exist_ok=True)
            target = dest_dir / Path(path_in_repo).name
            if target.exists():
                _log(f"✓ {label} — already present")
                continue
            sf = str(Path(path_in_repo).parent)
            _log(f"downloading {label} from {repo} …")
            cached = hf_hub_download(repo_id=repo, filename=Path(path_in_repo).name,
                                     subfolder=None if sf in ("", ".") else sf)
            try:                                          # hardlink (instant, same volume)
                os.link(cached, target)
            except OSError:                               # cross-volume → copy
                shutil.copy(cached, target)
            _log(f"✓ {label} -> {target}")
        _log("✓ downloads complete")
        _end()
    except Exception as e:
        _log(f"ERROR: {e}")
        _end(str(e))


# ----------------------------------------------------------------------------- launch
def start():
    """Launch ComfyUI headless if installed and not already up."""
    global _proc
    if not is_installed():
        return {"ok": False, "error": "ComfyUI is not installed yet"}
    if is_running():
        return {"ok": True, "already_running": True}
    _proc = subprocess.Popen(
        [sys.executable, "main.py", "--listen", _HOST, "--port", _PORT],
        cwd=str(COMFY_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(30):                                   # ComfyUI takes a few s to bind
        if is_running():
            return {"ok": True, "started": True}
        time.sleep(0.5)
    return {"ok": True, "starting": True}                 # still warming; client retries


def ensure_running():
    """Best-effort start before a ComfyUI-backed feature runs (never raises)."""
    try:
        if is_installed() and not is_running():
            start()
    except Exception:
        pass
