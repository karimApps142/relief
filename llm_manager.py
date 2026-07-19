"""
llm_manager.py — make a local chat LLM an *invisible managed dependency*, the same way
comfy_manager.py manages ComfyUI: install it, fetch the weights, launch it, report status.

The model family is Prism ML's **Bonsai** (ternary / 1-bit quantizations of Qwen3.6-27B).
These are NOT loadable by stock llama.cpp: the GGUFs declare architecture `dspark` and a
custom `Q2_0_g128` weight layout, so they need PrismML's llama.cpp FORK, which ships the
matching low-bit hybrid-attention kernels. That is why this module builds from source
rather than pip-installing llama-cpp-python — no published wheel understands `dspark`.

  status()          -> dict: built / running / per-model presence / task log
  install_async()   -> git clone the PrismML fork + cmake build (background)
  download_async()  -> stream the .gguf weights into LLAMA_DIR/models (background)
  start(model_key)  -> launch llama-server on LLM_URL with the chosen weights
  stop()            -> terminate it and wait for the port to release
  chat_stream(...)  -> generator of SSE lines proxied from llama-server

The GPU is treated as exclusive (matching server.run_feature's existing behaviour): we
unload the relief/depth models and stop ComfyUI before a 7 GB LLM claims the card.

Locations are env-configurable:
  LLAMA_CPP_DIR (default: <repo-parent>/llama.cpp-prism)   LLM_URL (default 127.0.0.1:8899)
  LLM_MODELS_DIR (default: <LLAMA_CPP_DIR>/models)         LLM_CTX (default 8192)
"""
import os
import sys
import glob
import time
import json
import shutil
import threading
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_WIN = os.name == "nt"
LLAMA_DIR = Path(os.environ.get("LLAMA_CPP_DIR", _ROOT.parent / "llama.cpp-prism")).resolve()
# Weights live BESIDE the llama.cpp checkout, never inside it. `git clone` refuses to write
# into a non-empty directory, so weights sitting in LLAMA_DIR/models made the build fail with
# "destination path already exists" — and the obvious user fix (delete the folder) would throw
# away a ~11 GB download. _migrate_legacy_models() relocates anything left in the old spot.
MODELS_DIR = Path(os.environ.get("LLM_MODELS_DIR", _ROOT.parent / "llm-models")).resolve()
_LEGACY_MODELS_DIR = LLAMA_DIR / "models"
# NOT llama.cpp's default 8080 — that port is heavily contested (Docker Desktop binds it,
# among many others) and a foreign service answering there used to read as "model loaded".
LLM_URL = os.environ.get("LLM_URL", "127.0.0.1:8899")
_HOST, _PORT = (LLM_URL.split(":") + ["8899"])[:2]

# PrismML's fork — carries the Q2_0_g128 / ternary CUDA + Metal kernels. Mainline
# llama.cpp cannot load these weights at all (unknown architecture 'dspark').
LLAMA_GIT = "https://github.com/PrismML-Eng/llama.cpp"

# Context window. The model card advertises 262K, but the GGUF header reports 4096 and
# each extra token costs KV cache on a 12 GB card, so we default to a comfortable 8K and
# let LLM_CTX raise it. Peak measured by Prism: ~8.4 GB at 4K, ~14.7 GB at 100K.
DEFAULT_CTX = int(os.environ.get("LLM_CTX", "8192"))

# key -> spec. `size_gb` is the real on-disk size (verified against the HF API), shown in
# the picker so a download is never a surprise. Both entries are full 27B chat models;
# they differ only in how aggressively the weights are quantized.
MODELS = {
    "ternary-q2": {
        "label": "Ternary Bonsai 27B · Q2_0",
        "repo": "prism-ml/Ternary-Bonsai-27B-gguf",
        "file": "Ternary-Bonsai-27B-Q2_0.gguf",
        "size_gb": 7.17,
        "tag": "Quality",
        "blurb": "Ternary {-1,0,+1} weights at ~1.71 bits. Retains ~95% of the FP16 "
                 "model's benchmark score — the best answers this family gives.",
    },
    "binary-q1": {
        "label": "Bonsai 27B · Q1_0",
        "repo": "prism-ml/Bonsai-27B-gguf",
        "file": "Bonsai-27B-Q1_0.gguf",
        "size_gb": 3.80,
        "tag": "Light",
        "blurb": "The 1-bit companion — about half the footprint and noticeably faster "
                 "to load, at some cost in reasoning quality. Good on a busy GPU.",
    },
}
DEFAULT_MODEL = "ternary-q2"

# Sampling defaults are the model card's published settings (the ones Prism used for all
# reported benchmarks). Exposed in the UI; these are the values the presets reset to.
SAMPLING_DEFAULTS = {"temperature": 0.7, "top_p": 0.95, "top_k": 20, "max_tokens": 2048}
DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant"

_proc = None                                              # the launched llama-server
_logfh = None                                             # its log file handle (kept alive)
_loaded = [None]                                          # model key currently served
_lock = threading.Lock()
_task = {"action": None, "running": False, "log": [], "error": None, "done": False}
# Live byte counter for the in-flight download. Structured (not scraped from the log) so
# the UI can draw a real progress bar — a 7.17 GB fetch is far too long for a spinner.
_progress = {"key": None, "label": None, "done": 0, "total": 0, "percent": 0}


# --------------------------------------------------------------------------- state
def _log(msg):
    with _lock:
        _task["log"].append(str(msg).rstrip())
        del _task["log"][:-300]                           # keep the tail bounded


def model_path(key):
    spec = MODELS.get(key) or MODELS[DEFAULT_MODEL]
    return MODELS_DIR / spec["file"]


def _path_ok(path):
    """A non-empty real file. Mirrors comfy_manager._path_ok: a broken Windows reparse
    point makes .exists() raise WinError 4392, which must read as 'absent', not 500."""
    try:
        return path.exists() and path.stat().st_size > 0
    except OSError:
        return False


def server_bin():
    """Locate llama-server: the extracted prebuilt release first, then the layouts cmake
    produces (MSVC nests a per-config dir; Ninja/Make don't). None until one exists."""
    exe = ".exe" if _WIN else ""
    for rel in (f"bin/llama-server{exe}",                       # prebuilt release
                f"build/bin/Release/llama-server{exe}", f"build/bin/llama-server{exe}",
                f"build/Release/llama-server{exe}", f"build/llama-server{exe}"):
        p = LLAMA_DIR / rel
        if p.exists():
            return p
    return None


def is_built():
    return server_bin() is not None


def is_running(timeout=1.5):
    """Is *our* llama-server answering on LLM_URL?

    Deliberately checks the response body, not just reachability: any unrelated service
    bound to this port (Docker, a dev server) would otherwise register as a loaded model
    and send the UI into a chat view that can never answer. llama-server's /health replies
    with a JSON `status` field — 200 {"status":"ok"} when ready, 503 while still loading.
    """
    try:
        with urllib.request.urlopen(f"http://{LLM_URL}/health", timeout=timeout) as r:
            return b'"status"' in r.read(400)
    except urllib.error.HTTPError as e:
        if e.code != 503:                                 # not our server — something else
            return False
        try:
            return b'"status"' in e.read(400)             # still loading the model → up
        except Exception:
            return True
    except Exception:
        return False


def models_status():
    return {k: _path_ok(model_path(k)) for k in MODELS}


def _migrate_legacy_models():
    """Move weights out of the old LLAMA_DIR/models into MODELS_DIR.

    Called from status()/download/start so it runs the moment the UI is opened. Same-volume
    moves are instant renames, so a 7 GB file is never re-downloaded and never copied. Purely
    additive: a file already present at the destination is left alone, never overwritten.
    """
    try:
        if _LEGACY_MODELS_DIR.resolve() == MODELS_DIR.resolve() or not _LEGACY_MODELS_DIR.is_dir():
            return
    except OSError:
        return
    for spec in MODELS.values():
        old, new = _LEGACY_MODELS_DIR / spec["file"], MODELS_DIR / spec["file"]
        if not _path_ok(old) or _path_ok(new):
            continue
        try:
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            try:
                os.replace(old, new)                      # same volume: instant rename
            except OSError:
                shutil.move(str(old), str(new))           # crosses volumes: real copy
            _log(f"moved {spec['file']} out of the llama.cpp checkout -> {new}")
        except Exception as e:
            _log(f"! could not relocate {spec['file']}: {e} (it is still at {old})")


def _find(exe, *candidates):
    """Locate a build tool. PATH first, then well-known install locations — a server started
    before the tool was installed (or launched outside a developer shell) has a stale PATH,
    and we would otherwise report a tool as missing when it is sitting right there."""
    found = shutil.which(exe)
    if found:
        return found
    for pattern in candidates:
        for hit in sorted(glob.glob(pattern), reverse=True):   # newest versioned dir wins
            if Path(hit).exists():
                return hit
    return None


def cmake_bin():
    return _find("cmake", r"C:\Program Files\CMake\bin\cmake.exe",
                 r"C:\Program Files (x86)\CMake\bin\cmake.exe",
                 "/opt/homebrew/bin/cmake", "/usr/local/bin/cmake")


def git_bin():
    return _find("git", r"C:\Program Files\Git\cmd\git.exe",
                 "/opt/homebrew/bin/git", "/usr/bin/git")


def nvcc_bin():
    return _find("nvcc", r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v*\bin\nvcc.exe",
                 "/usr/local/cuda*/bin/nvcc")


def _has_compiler():
    """On Windows, cl.exe is only on PATH inside a Developer Command Prompt — but CMake finds
    MSVC through the registry/vswhere regardless, so the presence of a Visual Studio install
    is the honest signal. Reporting 'no compiler' for a working box would be a false alarm."""
    if _WIN:
        return bool(shutil.which("cl") or
                    _find("vswhere", r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"))
    return bool(shutil.which("cc") or shutil.which("clang") or shutil.which("gcc"))


def toolchain():
    """Which build prerequisites are available. Surfaced in the UI *before* the user starts
    a long build, because a missing tool otherwise fails deep in cmake output.

    `gpu` describes the acceleration the build would get: CUDA where nvcc is present, Metal on
    macOS (always available, no toolkit needed), otherwise CPU-only.
    """
    cuda = bool(nvcc_bin())
    nvidia = _has_nvidia()
    # What the PREBUILT engine would give us — that path needs only a driver, not a toolkit,
    # so an RTX box with no CUDA Toolkit still reports full GPU acceleration here.
    prebuilt_gpu = "cuda" if nvidia else "metal" if sys.platform == "darwin" else "cpu"
    return {"git": bool(git_bin()), "cmake": bool(cmake_bin()),
            "nvcc": cuda, "compiler": _has_compiler(), "nvidia": nvidia,
            "gpu": "cuda" if cuda else "metal" if sys.platform == "darwin" else "cpu",
            "prebuilt_gpu": prebuilt_gpu}


def status():
    _migrate_legacy_models()      # polled by the UI, so a stale layout self-heals on open
    return {
        "built": is_built(),
        "models_dir": str(MODELS_DIR),
        "running": is_running() if is_built() else False,
        "dir": str(LLAMA_DIR),
        "url": LLM_URL,
        "loaded": _loaded[0],
        "ctx": DEFAULT_CTX,
        "catalog": [{"key": k, **{x: v[x] for x in ("label", "repo", "file", "size_gb", "tag", "blurb")}}
                    for k, v in MODELS.items()],
        "models": models_status(),
        "progress": dict(_progress),
        "toolchain": toolchain(),
        "defaults": {**SAMPLING_DEFAULTS, "system_prompt": DEFAULT_SYSTEM_PROMPT},
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
                         stderr=subprocess.STDOUT, text=True, bufsize=1,
                         encoding="utf-8", errors="replace")
    for line in p.stdout:
        _log(line)
    p.wait()
    if p.returncode != 0:
        raise RuntimeError(f"`{cmd[0]} …` exited {p.returncode}")


# ----------------------------------------------------------------- prebuilt install
# The preferred path. Prism publishes per-platform binaries of their fork, including a
# Windows CUDA build plus a `cudart-` pack carrying the CUDA runtime DLLs — so a GPU-ready
# engine needs NO CMake, NO Visual Studio and NO CUDA Toolkit, just ~650 MB of downloads.
RELEASES_API = "https://api.github.com/repos/PrismML-Eng/llama.cpp/releases/latest"
BIN_DIR = LLAMA_DIR / "bin"


_nvidia = []                                   # cached: hardware does not change at runtime


def _has_nvidia():
    """An NVIDIA GPU usable for inference. nvidia-smi ships with the DRIVER, so this is true
    on a normal gaming box — unlike nvcc, which only exists with the (huge) CUDA Toolkit.
    Cached because status() is polled every 1.5 s and this shells out."""
    if _nvidia:
        return _nvidia[0]
    ok = False
    if shutil.which("nvidia-smi"):
        try:
            ok = subprocess.run(["nvidia-smi"], capture_output=True, timeout=6).returncode == 0
        except Exception:
            ok = False
    _nvidia.append(ok)
    return ok


def _pick_assets(names):
    """Release asset names to install for this platform, in download order."""
    def find(*subs, exclude=()):
        # prefer Prism's own build over any vanilla passthrough asset of the same shape
        for n in sorted(names, key=lambda x: ("prism" not in x, x)):
            if all(s in n for s in subs) and not any(e in n for e in exclude):
                return n
        return None

    if _WIN:
        if _has_nvidia():
            main = find("bin-win-cuda", "x64.zip", exclude=("cudart",))
            if main:
                # the runtime pack is what removes the CUDA Toolkit requirement
                return [a for a in (main, find("cudart-", "win-cuda", "x64.zip")) if a]
        return [a for a in [find("bin-win-cpu-x64.zip")] if a]
    if sys.platform == "darwin":
        import platform
        arch = "arm64" if platform.machine() in ("arm64", "aarch64") else "x64"
        return [a for a in [find(f"bin-macos-{arch}.tar.gz", exclude=("kleidiai",))] if a]
    if _has_nvidia():
        cuda = find("bin-linux-cuda-12.4", "x64.tar.gz")
        if cuda:
            return [cuda]
    return [a for a in [find("bin-ubuntu-x64.tar.gz")] if a]


def _safe_extract(archive, dest):
    """Extract a release archive, rejecting entries that escape `dest` (zip-slip)."""
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()

    def ok(name):
        return not os.path.isabs(name) and (root / name).resolve().is_relative_to(root)

    if archive.suffix == ".zip":
        import zipfile
        with zipfile.ZipFile(archive) as z:
            members = [n for n in z.namelist() if ok(n)]
            z.extractall(dest, members=members)
    else:
        import tarfile
        with tarfile.open(archive) as t:
            members = [m for m in t.getmembers() if ok(m.name)]
            try:
                t.extractall(dest, members=members, filter="data")   # py>=3.12
            except TypeError:
                t.extractall(dest, members=members)


def _flatten_to_bin(staged):
    """Move the directory that actually contains llama-server into BIN_DIR.

    Windows zips put the binaries at the archive root; the tarballs nest them under
    build/bin/. Locating the executable and taking its whole folder handles both, and keeps
    the DLLs/shared libs next to it — llama-server will not start without them.
    """
    exe = ".exe" if _WIN else ""
    hits = list(staged.rglob(f"llama-server{exe}"))
    if not hits:
        raise RuntimeError("the release archive did not contain llama-server — asset layout changed?")
    src = hits[0].parent
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = BIN_DIR / item.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink()
        shutil.move(str(item), str(target))
    if not _WIN:                                       # tar keeps the bit; zip does not
        for f in BIN_DIR.iterdir():
            if f.is_file():
                try:
                    f.chmod(f.stat().st_mode | 0o111)
                except OSError:
                    pass


def install_prebuilt_async():
    if not _begin("install"):
        return False
    threading.Thread(target=_install_prebuilt, daemon=True).start()
    return True


def _install_prebuilt():
    """Download + extract Prism's prebuilt llama.cpp for this platform. No toolchain."""
    try:
        _migrate_legacy_models()
        _log("looking up the latest PrismML llama.cpp release …")
        req = urllib.request.Request(RELEASES_API, headers={
            "User-Agent": "relief-llm-manager", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            rel = json.loads(r.read().decode())
        assets = {a["name"]: a["browser_download_url"] for a in rel.get("assets", [])}
        wanted = _pick_assets(list(assets))
        if not wanted:
            raise RuntimeError(
                f"release {rel.get('tag_name')} has no prebuilt binary for this platform — "
                "use 'Build from source' instead.")
        _log(f"release {rel.get('tag_name')} · installing: {', '.join(wanted)}")
        if _WIN and not _has_nvidia():
            _log("! no NVIDIA GPU detected — installing the CPU build (much slower)")

        staged = LLAMA_DIR / "_staged"
        shutil.rmtree(staged, ignore_errors=True)
        staged.mkdir(parents=True, exist_ok=True)
        try:
            for name in wanted:
                archive = staged / name
                _progress.update(key="engine", label=name, done=0, total=0, percent=0)
                _log(f"downloading {name} …")
                _http_download(assets[name], archive, name)
                _log(f"extracting {name} …")
                _safe_extract(archive, staged)
                archive.unlink(missing_ok=True)
            _flatten_to_bin(staged)
        finally:
            _reset_progress()
            shutil.rmtree(staged, ignore_errors=True)

        if not is_built():
            raise RuntimeError("install finished but llama-server is still missing — see the log")
        _log(f"✓ engine ready -> {server_bin()}")
        _end()
    except Exception as e:
        _log(f"ERROR: {e}")
        _end(str(e))


# --------------------------------------------------------- install (build from source)
def install_async():
    if not _begin("install"):
        return False
    threading.Thread(target=_install, daemon=True).start()
    return True


def _ensure_repo(git):
    """Get the fork's source into LLAMA_DIR, whatever state that directory is in.

    A plain `git clone` fails on a non-empty destination, which is exactly what an earlier
    weight download left behind. So a non-empty, non-repo directory is populated in place via
    init + fetch instead — it never deletes anything the user already has on disk.
    """
    LLAMA_DIR.parent.mkdir(parents=True, exist_ok=True)
    if (LLAMA_DIR / "CMakeLists.txt").exists():
        _log("✓ fork already cloned — pulling latest")
        try:
            _run([git, "pull", "--ff-only"], cwd=str(LLAMA_DIR))
        except Exception as e:
            _log(f"  (pull skipped: {e})")
        return
    if not LLAMA_DIR.exists() or not any(LLAMA_DIR.iterdir()):
        _log(f"cloning the PrismML llama.cpp fork -> {LLAMA_DIR}")
        _run([git, "clone", "--depth", "1", LLAMA_GIT, str(LLAMA_DIR)])
        return
    _log(f"{LLAMA_DIR} already has files in it — fetching the source in place "
         "(nothing existing is deleted)")
    if not (LLAMA_DIR / ".git").exists():
        _run([git, "init"], cwd=str(LLAMA_DIR))
        _run([git, "remote", "add", "origin", LLAMA_GIT], cwd=str(LLAMA_DIR))
    _run([git, "fetch", "--depth", "1", "origin", "HEAD"], cwd=str(LLAMA_DIR))
    _run([git, "reset", "--hard", "FETCH_HEAD"], cwd=str(LLAMA_DIR))


def _install():
    """Clone + cmake-build the PrismML llama.cpp fork. CUDA if nvcc is present, Metal on
    macOS, CPU otherwise (which still runs, just slowly — better than hard-failing)."""
    try:
        _migrate_legacy_models()          # get weights out of the clone target first
        tc = toolchain()
        git, cmake = git_bin(), cmake_bin()
        missing = [n for n in ("git", "cmake") if not tc[n]]
        if missing:
            raise RuntimeError(
                f"{' and '.join(missing)} not found. Install "
                + (" and ".join(missing)) +
                " — Git: https://git-scm.com/download/win · CMake: https://cmake.org/download/ "
                "(tick 'Add CMake to the system PATH'), then RESTART this server so it picks "
                "up the new PATH, and retry.")
        if not tc["compiler"]:
            _log("! No C++ compiler found. On Windows install 'Visual Studio Build Tools' with "
                 "the 'Desktop development with C++' workload. Attempting the build anyway…")

        _ensure_repo(git)

        gpu = tc["gpu"]
        _log({"cuda": "configuring cmake WITH CUDA (nvcc found) — full GPU offload",
              "metal": "configuring cmake with Metal (macOS GPU; no CUDA toolkit needed)",
              "cpu": "configuring cmake for CPU — no CUDA toolkit found, so no GPU offload"}[gpu])
        # LLAMA_CURL=OFF: recent llama.cpp hard-requires libcurl at configure time, which
        # is not present on a stock Windows box. We download weights ourselves anyway.
        cfg = [cmake, "-B", "build", "-DLLAMA_CURL=OFF", "-DLLAMA_BUILD_TESTS=OFF",
               "-DLLAMA_BUILD_EXAMPLES=OFF", "-DLLAMA_BUILD_SERVER=ON"]
        if gpu == "cuda":
            cfg.append("-DGGML_CUDA=ON")
        _run(cfg, cwd=str(LLAMA_DIR))

        _log("building llama-server (this takes 10–30 minutes the first time)…")
        _run([cmake, "--build", "build", "--config", "Release", "--target", "llama-server",
              "-j", str(max(2, (os.cpu_count() or 4) - 1))], cwd=str(LLAMA_DIR))

        if not is_built():
            raise RuntimeError("build finished but llama-server was not produced — see the log above")
        _log(f"✓ llama-server built -> {server_bin()}")
        _end()
    except Exception as e:
        _log(f"ERROR: {e}")
        _end(str(e))


# -------------------------------------------------------------------------- downloads
def download_async(keys=None):
    if not _begin("download"):
        return False
    threading.Thread(target=_download, args=(keys,), daemon=True).start()
    return True


def _reset_progress():
    _progress.update(key=None, label=None, done=0, total=0, percent=0)


def _download(keys):
    _migrate_legacy_models()          # never re-download something we already have
    wanted = [k for k in (keys or list(MODELS)) if k in MODELS]
    failures = []
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    for key in wanted:
        spec = MODELS[key]
        target = model_path(key)
        if _path_ok(target):
            _log(f"✓ {spec['label']} — already present")
            continue
        try:
            _log(f"downloading {spec['label']} ({spec['size_gb']:.2f} GB) from {spec['repo']} …")
            _progress.update(key=key, label=spec["label"], done=0,
                             total=int(spec["size_gb"] * 1e9), percent=0)
            _http_download(f"https://huggingface.co/{spec['repo']}/resolve/main/{spec['file']}",
                           target, spec["label"])
            _log(f"✓ {spec['label']} -> {target}")
        except Exception as e:                             # one bad file shouldn't block the rest
            failures.append(spec["label"])
            _log(f"✗ {spec['label']}: {e}")
    _reset_progress()
    if failures:
        _end("failed: " + ", ".join(failures))
    else:
        _log("✓ downloads complete")
        _end()


def _http_download(url, target, label):
    """Stream an HF resolve URL straight to `target` (atomic via a .part temp), logging
    throttled progress so a multi-GB fetch never looks frozen. Deliberately NOT
    huggingface_hub: comfy_manager learned the hard way that the HF cache's symlink /
    hardlink dance corrupts on Windows."""
    req = urllib.request.Request(url, headers={"User-Agent": "relief-llm-manager"})
    tmp = target.with_name(target.name + ".part")
    try:                                                  # clear any stale/broken target
        target.unlink()
    except OSError:
        pass
    with urllib.request.urlopen(req, timeout=60) as r:    # follows HF's 302 to the CDN
        total = int(r.headers.get("Content-Length") or 0)
        if total:
            _progress["total"] = total                    # exact, replaces the catalog estimate
        done = last = 0
        step = max(total // 20, 64 << 20) if total else 0   # log ~every 5% (min 64 MB)
        with open(tmp, "wb") as f:
            while True:
                chunk = r.read(1 << 20)                   # 1 MB
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                _progress["done"] = done
                _progress["percent"] = (100 * done // total) if total else 0
                if step and done - last >= step:
                    last = done
                    _log(f"   {label}: {done / 1e9:.2f}/{total / 1e9:.2f} GB ({100 * done // total}%)")
    os.replace(tmp, target)                               # atomic; no partial/broken target
    _progress["percent"] = 100


# ----------------------------------------------------------------------------- launch
def _free_vram():
    """The 12 GB card is exclusive: a 27B LLM cannot share it with the relief models or a
    resident ComfyUI checkpoint. Unload ours and stop ComfyUI before claiming it."""
    try:
        import models
        models.unload_all()
    except Exception:
        pass
    try:
        import comfy_manager
        if comfy_manager.is_running():
            _log("stopping ComfyUI to free VRAM for the LLM …")
            comfy_manager.stop()
    except Exception:
        pass


def _tail_log(logfile, proc):
    """Follow llama-server's log FILE → task log until it exits. A file (not a PIPE) for
    the same reason ComfyUI uses one: piped progress output breaks flushing on Windows."""
    try:
        with open(logfile, "r", encoding="utf-8", errors="replace") as f:
            while True:
                line = f.readline()
                if line:
                    _log("[llm] " + line.rstrip())
                elif proc.poll() is not None:
                    for rest in f.read().splitlines():     # drain the tail
                        _log("[llm] " + rest.rstrip())
                    break
                else:
                    time.sleep(0.3)
    except Exception:
        pass


def start(model_key=None, ctx=None):
    """Launch llama-server with the chosen weights. Idempotent: if the requested model is
    already the one being served we no-op; switching models restarts the process, since
    only one 27B model fits in VRAM at a time."""
    global _proc, _logfh
    _migrate_legacy_models()
    key = model_key or _loaded[0] or DEFAULT_MODEL
    if key not in MODELS:
        return {"ok": False, "error": f"unknown model: {key}"}
    if not is_built():
        return {"ok": False, "error": "llama.cpp (PrismML fork) is not built yet"}
    gguf = model_path(key)
    if not _path_ok(gguf):
        return {"ok": False, "error": f"{MODELS[key]['label']} is not downloaded yet"}
    if is_running():
        if _loaded[0] == key:
            return {"ok": True, "already_running": True, "loaded": key}
        _log(f"switching model → {MODELS[key]['label']} (restarting llama-server)")
        stop()

    _free_vram()
    try:
        if _logfh:
            _logfh.close()
    except Exception:
        pass
    logfile = LLAMA_DIR / "llama-server.log"
    try:                                                  # keep the previous session's log
        if logfile.exists():
            os.replace(logfile, logfile.with_suffix(".log.prev"))
    except OSError:
        pass

    n_ctx = int(ctx or DEFAULT_CTX)
    # --jinja uses the chat template embedded in the GGUF, which is what makes
    # /v1/chat/completions apply the model's real role formatting (and emit its <think>
    # blocks correctly). -ngl 99 offloads every layer it can; harmless on a CPU build.
    args = [str(server_bin()), "-m", str(gguf), "--host", _HOST, "--port", _PORT,
            "-c", str(n_ctx), "-ngl", "99", "--jinja"]
    _log(f"starting llama-server · {MODELS[key]['label']} · ctx {n_ctx} …")
    _logfh = open(logfile, "wb")
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    _proc = subprocess.Popen(args, cwd=str(LLAMA_DIR), stdout=_logfh,
                             stderr=subprocess.STDOUT, env=env)
    threading.Thread(target=_tail_log, args=(logfile, _proc), daemon=True).start()

    # A 7 GB model off a cold page cache can take a while to map; poll generously.
    for _ in range(240):                                  # up to 120 s
        if is_running():
            _loaded[0] = key
            try:
                import system_info
                system_info.set_resident("llm", MODELS[key]["label"])
            except Exception:
                pass
            _log(f"✓ {MODELS[key]['label']} is ready")
            return {"ok": True, "started": True, "loaded": key}
        if _proc.poll() is not None:                      # exited early → it crashed
            _log(f"✗ llama-server exited with code {_proc.returncode} — see the [llm] log above")
            return {"ok": False, "error": f"llama-server exited with code {_proc.returncode} "
                                          f"(see the log, or {logfile})"}
        time.sleep(0.5)
    return {"ok": True, "starting": True, "loaded": key}  # still warming; client keeps polling


def start_async(model_key=None, ctx=None):
    """Background start so the UI can show the load progressing (a cold 7 GB map is slow)."""
    if not _begin("start"):
        return False

    def _s():
        try:
            r = start(model_key, ctx)
            _end(None if r.get("ok") else r.get("error"))
        except Exception as e:
            _log(f"ERROR: {e}")
            _end(str(e))
    threading.Thread(target=_s, daemon=True).start()
    return True


def stop(wait=12):
    """Stop the llama-server we launched and wait for the port to release."""
    global _proc, _logfh
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
    if _logfh is not None:
        try:
            _logfh.close()
        except Exception:
            pass
        _logfh = None
    _loaded[0] = None
    try:
        import system_info
        system_info.set_resident("idle")
    except Exception:
        pass
    for _ in range(24):                                   # wait for the port to free
        if not is_running():
            return True
        time.sleep(0.5)
    return not is_running()


# ------------------------------------------------------------------------------ chat
def chat_stream(messages, params=None):
    """Proxy llama-server's OpenAI-compatible streaming completion, yielding raw SSE
    `data: {...}` lines for the browser's EventSource-style reader.

    A generator (not async) on purpose: Starlette iterates it in a threadpool, so the
    blocking urllib read never touches the event loop, and closing it — which is what a
    client disconnect does — drops the upstream socket and llama-server stops generating.
    """
    p = {**SAMPLING_DEFAULTS, **(params or {})}
    body = json.dumps({
        "messages": messages,
        "stream": True,
        "temperature": float(p["temperature"]),
        "top_p": float(p["top_p"]),
        "top_k": int(p["top_k"]),
        "max_tokens": int(p["max_tokens"]),
    }).encode()
    req = urllib.request.Request(
        f"http://{LLM_URL}/v1/chat/completions", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
    try:
        resp = urllib.request.urlopen(req, timeout=600)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        yield _sse_error(f"llama-server rejected the request ({e.code}): {detail}")
        return
    except Exception as e:
        yield _sse_error(f"cannot reach llama-server at {LLM_URL}: {e}")
        return
    try:
        for raw in resp:
            line = raw.decode("utf-8", "replace")
            if line.strip():                              # forward data:/comment lines as-is
                yield line if line.endswith("\n") else line + "\n"
            else:
                yield "\n"                                # event terminator
    except GeneratorExit:                                 # client disconnected → stop upstream
        raise
    except Exception as e:
        yield _sse_error(f"stream interrupted: {e}")
    finally:
        try:
            resp.close()
        except Exception:
            pass


def _sse_error(message):
    """Errors ride the stream itself so the UI can render them in the message thread
    rather than the request failing after headers are already sent."""
    return f"data: {json.dumps({'error': message})}\n\n"
