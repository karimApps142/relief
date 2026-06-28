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

Model files stream DIRECTLY into ComfyUI/models over HTTP (HF resolve URLs) — no HF
cache, no symlinks/hardlinks. The cache+hardlink approach broke on Windows (os.link of
an HF symlink leaves a broken reparse point that even crashes `.exists()`), so we avoid
it entirely. The global HF_HOME is never touched (relief keeps its own default cache).

Locations are env-configurable:
  COMFYUI_DIR  (default: <repo-parent>/ComfyUI)   COMFYUI_URL (default 127.0.0.1:8188)
"""
import os
import sys
import time
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
ICLIGHT_GIT = "https://github.com/kijai/ComfyUI-IC-Light"
# Image → 3D (textured): the kijai Hunyuan3D wrapper (shape + paint) + cubiq essentials
# (the wrapper's example workflow uses ImageResize+ / background-removal nodes from it).
HY3DWRAP_GIT = "https://github.com/kijai/ComfyUI-Hunyuan3DWrapper"
ESSENTIALS_GIT = "https://github.com/cubiq/ComfyUI_essentials"
# Clarity-style creative upscale: ssitu's Ultimate SD Upscale node (tiled SD img2img).
# Has a git submodule (Coyote-A/ultimate-upscale) — clone with --recurse-submodules.
USDU_GIT = "https://github.com/ssitu/ComfyUI_UltimateSDUpscale"

# label -> (hf_repo, path_within_repo, dest_subdir_under_ComfyUI/models)
# path_within_repo may contain a subfolder; only the basename lands in dest.
# MODELS = the Krea core that GATES the image engine (text2img/img2img/upscale).
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
# RELIGHT = IC-Light (SD1.5) — downloaded alongside the core but NOT part of the gate,
# so it never blocks the other features. Used only by the Relight feature.
RELIGHT_MODELS = {
    "relight · IC-Light FC (~1.7 GB)":
        ("lllyasviel/ic-light", "iclight_sd15_fc.safetensors", "unet/IC-Light"),
    "relight · SD1.5 base (~2 GB)":
        ("Comfy-Org/stable-diffusion-v1-5-archive", "v1-5-pruned-emaonly-fp16.safetensors", "checkpoints"),
}
# IMAGE→3D = Hunyuan3D-2.0 shape DiT for the kijai Hunyuan3DWrapper's Hy3DModelLoader, which
# lists models/diffusion_models/ (recursively). The wrapper's example workflow references it as
# 'hy3dgen\hunyuan3d-dit-v2-0-fp16.safetensors', so we place it in diffusion_models/hy3dgen/.
# The paint + delight models are diffusers-based and AUTO-DOWNLOAD on first run via the wrapper's
# DownloadAndLoad nodes — only this shape DiT needs explicit provisioning. Not in the engine gate.
HUNYUAN3D_MODELS = {
    "image→3D · Hunyuan3D-2.0 DiT fp16 (~4.9 GB)":
        ("Kijai/Hunyuan3D-2_safetensors", "hunyuan3d-dit-v2-0-fp16.safetensors", "diffusion_models/hy3dgen"),
}
# CLARITY = the creative-upscale bundle (SD1.5 Tile ControlNet + photoreal checkpoint +
# detail LoRA) for the Clarity feature. Downloaded alongside the core but NOT part of the
# engine gate, so it never blocks text2img/img2img. The 4x-UltraSharp upscaler it also uses
# already ships in MODELS, and the SD1.5 base (v1-5-pruned-emaonly) comes from RELIGHT_MODELS.
CLARITY_MODELS = {
    "clarity · Tile ControlNet SD1.5 (~1.4 GB)":
        ("lllyasviel/ControlNet-v1-1", "control_v11f1e_sd15_tile.pth", "controlnet"),
    "clarity · Juggernaut Reborn checkpoint (~2 GB)":
        ("dantea1118/juggernaut_reborn", "juggernaut_reborn.safetensors", "checkpoints"),
    # Detail LoRAs (all SD1.5, from the same repo): more_details (subtle), Detail Tweaker
    # (strong), the LECO detail slider, and a sharpness LoRA. Small; ~58 MB combined.
    "clarity · more_details LoRA (~9 MB)":
        ("philz1337x/loras", "more_details.safetensors", "loras"),
    "clarity · Detail Tweaker LoRA (~36 MB)":
        ("philz1337x/loras", "add_detail.safetensors", "loras"),
    "clarity · Detail slider LoRA (~13 MB)":
        ("philz1337x/loras", "detail_slider_v4.safetensors", "loras"),
    "clarity · Sharpness LoRA (~9 MB)":
        ("philz1337x/loras", "add_sharpness.safetensors", "loras"),
}

LORA_DIR = COMFY_DIR / "models" / "loras"                 # user-supplied custom LoRAs land here

_proc = None                                              # the launched ComfyUI process
_lock = threading.Lock()
_task = {"action": None, "running": False, "log": [], "error": None, "done": False}


# --------------------------------------------------------------------------- state
def _log(msg):
    with _lock:
        _task["log"].append(str(msg).rstrip())
        del _task["log"][:-300]                           # keep the tail bounded


def _dest(subdir, path_in_repo):
    return COMFY_DIR / "models" / subdir / path_in_repo.rsplit("/", 1)[-1]


def _path_ok(path):
    """Robust existence check: a non-empty real file. A broken Windows reparse point
    makes .exists()/.stat() raise WinError 4392 — treat any such error as 'absent'
    (so status() never 500s and the file gets re-downloaded clean)."""
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def is_installed():
    return (COMFY_DIR / "main.py").exists()


def is_running(timeout=1.5):
    try:
        urllib.request.urlopen(f"http://{COMFY_URL}/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def models_status():
    return {label: _path_ok(_dest(sub, p)) for label, (_, p, sub) in MODELS.items()}


def _nodes_status():
    cn = COMFY_DIR / "custom_nodes"
    return {"gguf": (cn / "ComfyUI-GGUF").exists(),
            "iclight": (cn / "ComfyUI-IC-Light").exists(),
            "hy3dwrap": (cn / "ComfyUI-Hunyuan3DWrapper").exists(),
            "essentials": (cn / "ComfyUI_essentials").exists(),
            "usdu": (cn / "ComfyUI_UltimateSDUpscale").exists()}


def status():
    installed = is_installed()
    return {
        "installed": installed,
        "running": is_running() if installed else False,
        "dir": str(COMFY_DIR),
        "url": COMFY_URL,
        "models": models_status(),
        "relight_models": {label: _path_ok(_dest(sub, p)) for label, (_, p, sub) in RELIGHT_MODELS.items()},
        "hunyuan3d_models": {label: _path_ok(_dest(sub, p)) for label, (_, p, sub) in HUNYUAN3D_MODELS.items()},
        "clarity_models": {label: _path_ok(_dest(sub, p)) for label, (_, p, sub) in CLARITY_MODELS.items()},
        "nodes": _nodes_status(),
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
        iclight = COMFY_DIR / "custom_nodes" / "ComfyUI-IC-Light"
        if not iclight.exists():
            _log("cloning ComfyUI-IC-Light custom node (relight)")
            _run(["git", "clone", "--depth", "1", ICLIGHT_GIT, str(iclight)])
            if (iclight / "requirements.txt").exists():
                _run([py, "-m", "pip", "install", "-r", str(iclight / "requirements.txt")])
        # Image → 3D (textured): kijai Hunyuan3D wrapper + cubiq essentials (image-prep nodes
        # its example workflow uses). The wrapper's requirements add trimesh/xatlas/pymeshlab/etc.
        hy3d = COMFY_DIR / "custom_nodes" / "ComfyUI-Hunyuan3DWrapper"
        if not hy3d.exists():
            _log("cloning ComfyUI-Hunyuan3DWrapper (image→3D, textured)")
            _run(["git", "clone", "--depth", "1", HY3DWRAP_GIT, str(hy3d)])
            if (hy3d / "requirements.txt").exists():
                _run([py, "-m", "pip", "install", "-r", str(hy3d / "requirements.txt")])
            cr = hy3d / "hy3dgen" / "texgen" / "custom_rasterizer"
            _log("NOTE: TEXTURE generation needs the custom_rasterizer CUDA extension. No prebuilt "
                 "wheel matches torch2.5.1+cu121, so build it once on the box:")
            _log(f"  {py} -m pip install -e \"{cr}\"   (or: cd \"{cr}\" && {py} setup.py install)")
            _log("  — needs VS Build Tools + the matching CUDA toolkit on PATH. Shape works without it.")
        essentials = COMFY_DIR / "custom_nodes" / "ComfyUI_essentials"
        if not essentials.exists():
            _log("cloning ComfyUI_essentials (image-prep nodes for the Hy3D workflow)")
            _run(["git", "clone", "--depth", "1", ESSENTIALS_GIT, str(essentials)])
            if (essentials / "requirements.txt").exists():
                _run([py, "-m", "pip", "install", "-r", str(essentials / "requirements.txt")])
        # Clarity creative-upscale: Ultimate SD Upscale. --recurse-submodules pulls the
        # Coyote-A upscale script it depends on (else it self-downloads a zip at import).
        usdu = COMFY_DIR / "custom_nodes" / "ComfyUI_UltimateSDUpscale"
        if not usdu.exists():
            _log("cloning ComfyUI_UltimateSDUpscale (clarity creative upscale)")
            _run(["git", "clone", "--depth", "1", "--recurse-submodules", USDU_GIT, str(usdu)])
        _log("installing ComfyUI requirements (this can take a few minutes)…")
        _run([py, "-m", "pip", "install", "-r", str(COMFY_DIR / "requirements.txt")])
        _run([py, "-m", "pip", "install", "-r", str(gguf / "requirements.txt")])
        _align_torchaudio(py)
        if is_running():                              # reload so newly-cloned nodes take effect
            _log("restarting ComfyUI to load new nodes…")
            restart()
        _log("✓ ComfyUI installed")
        _end()
    except Exception as e:
        _log(f"ERROR: {e}")
        _end(str(e))


def _align_torchaudio(py):
    """ComfyUI's requirements pull an unpinned torchaudio that often mismatches our pinned
    torch — its C++ ext then fails to load (WinError 127) and ComfyUI won't boot. Reinstall
    torchaudio matching the installed torch version, from the cu121 index."""
    try:
        ver = subprocess.run([py, "-c", "import torch;print(torch.__version__.split('+')[0])"],
                             capture_output=True, text=True).stdout.strip()
        if ver:
            _log(f"aligning torchaudio with torch {ver} (avoids the WinError 127 ABI clash)…")
            _run([py, "-m", "pip", "install", "--index-url",
                  "https://download.pytorch.org/whl/cu121", f"torchaudio=={ver}"])
    except Exception as e:
        _log(f"torchaudio align skipped ({e}) — run it manually if ComfyUI won't start")


# -------------------------------------------------------------------------- downloads
def download_async(labels=None):
    if not _begin("download"):
        return False
    threading.Thread(target=_download, args=(labels,), daemon=True).start()
    return True


def _download(labels):
    all_models = {**MODELS, **RELIGHT_MODELS, **HUNYUAN3D_MODELS, **CLARITY_MODELS}  # gate uses MODELS; download grabs all
    items = all_models if not labels else {k: all_models[k] for k in labels if k in all_models}
    failures = []
    for label, (repo, path_in_repo, sub) in items.items():
        dest_dir = COMFY_DIR / "models" / sub
        dest_dir.mkdir(parents=True, exist_ok=True)
        # HF repo paths ALWAYS use '/', never os.sep — split with str ops (Path.parent on
        # Windows would yield a backslash → HF 404 on split_files%5Cvae).
        target = dest_dir / path_in_repo.rsplit("/", 1)[-1]
        if _path_ok(target):
            _log(f"✓ {label} — already present")
            continue
        try:
            _log(f"downloading {label} from {repo} …")
            _http_download(f"https://huggingface.co/{repo}/resolve/main/{path_in_repo}",
                           target, label)
            _log(f"✓ {label} -> {target}")
        except Exception as e:                            # one bad file shouldn't block the rest
            failures.append(label)
            _log(f"✗ {label}: {e}")
    if failures:
        _end("failed: " + ", ".join(failures))
    else:
        _log("✓ downloads complete")
        _end()


def _http_download(url, target, label):
    """Stream an HF resolve URL straight to `target` (atomic via a .part temp). Logs
    throttled % progress so the big GGUF doesn't look frozen."""
    req = urllib.request.Request(url, headers={"User-Agent": "relief-comfy-manager"})
    tmp = target.with_name(target.name + ".part")
    try:                                                  # clear any stale/broken target
        target.unlink()
    except OSError:
        pass
    with urllib.request.urlopen(req, timeout=60) as r:    # follows HF's 302 to the CDN
        total = int(r.headers.get("Content-Length") or 0)
        done = last = 0
        step = max(total // 20, 32 << 20) if total else 0   # log ~every 5% (min 32 MB)
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)                   # 1 MB
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if step and done - last >= step:
                    last = done
                    _log(f"   {label}: {done / 1e9:.2f}/{total / 1e9:.2f} GB ({100 * done // total}%)")
    os.replace(tmp, target)                               # atomic; no partial/broken target


# ------------------------------------------------------------------------------ loras
# Custom LoRAs are *drop-in*: the user adds a .safetensors via the UI (POST /api/loras)
# or by copying it into ComfyUI/models/loras/. ComfyUI re-scans that folder when a graph
# is submitted, so a freshly-added file is usable on the next Generate — no restart.
def list_loras():
    """Sorted names of usable LoRA files in models/loras/ (empty if the dir is absent)."""
    try:
        return sorted(p.name for p in LORA_DIR.glob("*.safetensors") if _path_ok(p))
    except OSError:
        return []


def _safe_lora_name(filename):
    """Basename only (no path traversal), must be a .safetensors. Raises ValueError."""
    name = os.path.basename(filename or "").replace("\\", "").replace("\r", "").replace("\n", "").strip()
    name = name.replace("/", "_")
    if not name.lower().endswith(".safetensors"):
        raise ValueError("LoRA must be a .safetensors file")
    return name


def save_lora(filename, data):
    """Write an uploaded LoRA into models/loras/ (atomic via .part). Returns the saved name."""
    name = _safe_lora_name(filename)
    LORA_DIR.mkdir(parents=True, exist_ok=True)
    target = LORA_DIR / name
    tmp = target.with_name(target.name + ".part")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    _log(f"✓ LoRA added -> {target}")
    return name


def delete_lora(name):
    """Remove a LoRA file by name (basename-guarded). Best-effort."""
    try:
        (LORA_DIR / os.path.basename(name)).unlink()
    except OSError:
        pass


# ----------------------------------------------------------------------------- launch
def _pump(proc):
    """Stream ComfyUI's stdout/stderr into our task log (and comfy.log) so boot errors
    are visible in the UI instead of vanishing into DEVNULL."""
    logfile = COMFY_DIR / "comfy.log"
    try:
        with open(logfile, "w", encoding="utf-8", errors="replace") as fh:
            for line in proc.stdout:
                line = line.rstrip()
                fh.write(line + "\n"); fh.flush()
                _log("[comfy] " + line)
    except Exception:
        pass


def start():
    """Launch ComfyUI headless if installed and not already up. Streams its boot log
    into the UI and detects an early crash instead of silently 'starting' forever."""
    global _proc
    if not is_installed():
        return {"ok": False, "error": "ComfyUI is not installed yet"}
    if is_running():
        return {"ok": True, "already_running": True}
    _log(f"starting ComfyUI ({sys.executable} main.py --listen {_HOST} --port {_PORT}) …")
    _proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", "--listen", _HOST, "--port", _PORT],
        cwd=str(COMFY_DIR), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    threading.Thread(target=_pump, args=(_proc,), daemon=True).start()
    for _ in range(120):                                  # up to 60s: torch + custom nodes load
        if is_running():
            _log("✓ ComfyUI is up")
            return {"ok": True, "started": True}
        if _proc.poll() is not None:                      # exited early → it crashed
            _log(f"✗ ComfyUI exited with code {_proc.returncode} — see the [comfy] log above")
            return {"ok": False, "error": f"ComfyUI exited with code {_proc.returncode} "
                                          f"(see log / F:\\ComfyUI\\comfy.log)"}
        time.sleep(0.5)
    return {"ok": True, "starting": True}                 # still warming; client keeps polling


def stop(wait=12):
    """Stop the ComfyUI we launched and wait for the port to release."""
    global _proc
    if _proc is not None:
        try:
            _proc.terminate()
            for _ in range(wait * 2):
                if _proc.poll() is not None:
                    break
                time.sleep(0.5)
            if _proc.poll() is None:
                _proc.kill()
        except Exception:
            pass
        _proc = None
    for _ in range(24):                                   # wait for :8188 to free
        if not is_running():
            return True
        time.sleep(0.5)
    return not is_running()


def restart():
    """Stop + start ComfyUI (e.g. to load a newly-installed custom node). Synchronous;
    used internally by _install (which already holds the task lock)."""
    if not is_installed():
        return {"ok": False, "error": "ComfyUI is not installed yet"}
    _log("restarting ComfyUI …")
    stop()
    return start()


def restart_async():
    """Background restart for the /api/comfy/restart endpoint (so the UI shows it busy)."""
    if not _begin("restart"):
        return False

    def _r():
        try:
            restart(); _end()
        except Exception as e:
            _log(f"ERROR: {e}"); _end(str(e))
    threading.Thread(target=_r, daemon=True).start()
    return True


def interrupt():
    """Interrupt the in-flight ComfyUI execution (POST /interrupt) so Cancel actually
    stops the GPU work. Best-effort; harmless if nothing is running."""
    try:
        req = urllib.request.Request(f"http://{COMFY_URL}/interrupt", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=3)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ensure_running():
    """Best-effort start before a ComfyUI-backed feature runs (never raises)."""
    try:
        if is_installed() and not is_running():
            start()
    except Exception:
        pass
