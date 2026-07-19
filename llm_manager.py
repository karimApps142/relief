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
import time
import json
import shutil
import threading
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
LLAMA_DIR = Path(os.environ.get("LLAMA_CPP_DIR", _ROOT.parent / "llama.cpp-prism")).resolve()
MODELS_DIR = Path(os.environ.get("LLM_MODELS_DIR", LLAMA_DIR / "models")).resolve()
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
    """Locate llama-server across the layouts cmake produces (MSVC nests a per-config
    dir; the Ninja/Make generators don't). Returns None until the build has produced it."""
    exe = ".exe" if os.name == "nt" else ""
    for rel in (f"build/bin/Release/llama-server{exe}", f"build/bin/llama-server{exe}",
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


def toolchain():
    """Which build prerequisites are on PATH. Surfaced in the UI *before* the user starts
    a 20-minute build, because a missing compiler otherwise fails deep in cmake output."""
    return {"git": bool(shutil.which("git")), "cmake": bool(shutil.which("cmake")),
            "nvcc": bool(shutil.which("nvcc")),
            "compiler": bool(shutil.which("cl") or shutil.which("cc") or shutil.which("gcc"))}


def status():
    return {
        "built": is_built(),
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


# --------------------------------------------------------------------------- install
def install_async():
    if not _begin("install"):
        return False
    threading.Thread(target=_install, daemon=True).start()
    return True


def _install():
    """Clone + cmake-build the PrismML llama.cpp fork. CUDA if nvcc is present, CPU
    otherwise (which still runs, just slowly — worth building rather than hard-failing)."""
    try:
        tc = toolchain()
        missing = [n for n in ("git", "cmake") if not tc[n]]
        if missing:
            raise RuntimeError(
                f"{' and '.join(missing)} not found on PATH. Install them first — "
                "Git: https://git-scm.com/download/win · CMake: https://cmake.org/download/ "
                "(tick 'Add to PATH'), then reopen the terminal and retry.")
        if not tc["compiler"]:
            _log("! No C++ compiler on PATH. On Windows install 'Visual Studio Build Tools' "
                 "with the 'Desktop development with C++' workload, then run this from a "
                 "'x64 Native Tools Command Prompt'. Attempting the build anyway…")

        LLAMA_DIR.parent.mkdir(parents=True, exist_ok=True)
        if not (LLAMA_DIR / "CMakeLists.txt").exists():
            _log(f"cloning the PrismML llama.cpp fork -> {LLAMA_DIR}")
            _run(["git", "clone", "--depth", "1", LLAMA_GIT, str(LLAMA_DIR)])
        else:
            _log("✓ fork already cloned — pulling latest")
            try:
                _run(["git", "pull", "--ff-only"], cwd=str(LLAMA_DIR))
            except Exception as e:
                _log(f"  (pull skipped: {e})")

        cuda = tc["nvcc"]
        _log("configuring cmake " + ("WITH CUDA (nvcc found)" if cuda else
                                     "for CPU — nvcc not on PATH, so no GPU offload"))
        # LLAMA_CURL=OFF: recent llama.cpp hard-requires libcurl at configure time, which
        # is not present on a stock Windows box. We download weights ourselves anyway.
        cfg = ["cmake", "-B", "build", "-DLLAMA_CURL=OFF", "-DLLAMA_BUILD_TESTS=OFF",
               "-DLLAMA_BUILD_EXAMPLES=OFF", "-DLLAMA_BUILD_SERVER=ON"]
        if cuda:
            cfg.append("-DGGML_CUDA=ON")
        _run(cfg, cwd=str(LLAMA_DIR))

        _log("building llama-server (this takes 10–30 minutes the first time)…")
        _run(["cmake", "--build", "build", "--config", "Release", "--target", "llama-server",
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
