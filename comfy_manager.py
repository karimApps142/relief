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
    items = MODELS if not labels else {k: MODELS[k] for k in labels if k in MODELS}
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


def ensure_running():
    """Best-effort start before a ComfyUI-backed feature runs (never raises)."""
    try:
        if is_installed() and not is_running():
            start()
    except Exception:
        pass
