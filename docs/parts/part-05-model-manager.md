# Part 05 — Model manager (`model_manager.py`) + `/models/*` endpoints + `auto` backend

**Goal:** add the "Download Models" capability. Weights are **never** in the repo; the app ships
able to run in `lite` immediately, and a **Download Models** button (on the Windows box) pulls
the weights into the HF cache, after which the service switches to `full` automatically via the
`auto` backend. On the Mac you simply never press the button → it stays in `lite`.

**Runs on:** 🍎 Mac (build + wire the endpoints; `models_present()` returns `false` here) ·
🪟 Windows (where the download actually does something)

**Prerequisites:** Part 04 (`service.py`).

**Files created:** `model_manager.py`. **Files changed:** `service.py` (add `/models/status`,
`/models/download`, and `auto` resolution in `/relief`).

---

## The big idea

`model_manager.py` only uses `huggingface_hub` (already in the light `requirements.txt`), so it
imports fine on the Mac — it just reports `installed: false`. The UI flow is: on load call
`GET /models/status`; if `installed=false` show a **Download Models** button + a "preview/lite
mode" badge; the button calls `POST /models/download` and then polls `GET /models/status` for the
log until `installed=true`; thereafter relief requests use `full` automatically.

The `auto` backend value (resolves to `full` if weights present, else `lite`) is what ties the
button to the pipeline.

---

## The code

### `model_manager.py`

```python
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
```

### Changes to `service.py`

Add the imports and the download-state holder near the top:

```python
from fastapi import BackgroundTasks, Form
import model_manager

_dl = {"running": False, "log": []}
```

Add the two endpoints:

```python
@app.get("/models/status")
def models_status():
    return {"installed": model_manager.models_present(),
            "downloading": _dl["running"], "log": _dl["log"][-20:]}

def _run_download():
    _dl.update(running=True, log=[])
    try:
        model_manager.download_models(lambda m: _dl["log"].append(m))
    finally:
        _dl["running"] = False

@app.post("/models/download")
def models_download(bg: BackgroundTasks):
    if not _dl["running"]:
        bg.add_task(_run_download)
    return {"started": True}
```

Make `/relief` resolve an `auto` backend. Add a `backend` form field and, before building
`ReliefParams`, resolve it:

```python
# in the /relief handler signature, add:
#   backend: str = Form("auto"),
#
# then, before constructing params:
if backend == "auto":
    backend = "full" if model_manager.models_present() else "lite"
# ... pass backend into generate_relief(..., backend=backend)
```

> So the request says `backend=auto`; on the Mac that becomes `lite`, on a downloaded Windows box
> it becomes `full`. No client change needed between machines.

---

## UI behavior (any frontend — the Gradio app in Part 09, a local web page, etc.)

1. On load, call `GET /models/status`.
2. If `installed=false`, show a **Download Models** button + a "running in preview/lite mode"
   badge.
3. Button → `POST /models/download`, then poll `GET /models/status` for the log/progress until
   `installed=true`.
4. Once installed, relief requests use the `full` backend automatically (via `backend=auto`).

On the Mac you simply never press the button → it stays in `lite` → everything is testable.

---

## Steps

1. Create `model_manager.py`.
2. Edit `service.py`: add the imports + `_dl`, the two `/models/*` endpoints, and the `auto`
   resolution + `backend` form field in `/relief`.
3. Restart the service and check status on the Mac:

```bash
RELIEF_BACKEND=lite uvicorn service:app --reload --port 8000
curl -s http://localhost:8000/models/status
# {"installed": false, "downloading": false, "log": []}   <-- expected on Mac
```

> Do **not** press Download on the Mac — there's no torch/GPU; the StableNormal warm step would
> fail (it's wrapped in try/except, but the big repos would still download pointlessly).

---

## Verify

- `GET /models/status` on the Mac returns `installed: false`.
- `POST /models/download` returns `{"started": true}` and flips `downloading` (on a box where it
  makes sense to run it — i.e. Windows in Part 07).
- `/relief` with `backend=auto` runs in lite on the Mac without error.

## Done when

- [ ] `model_manager.py` exists with `HF_REPOS`, `models_present`, `download_models`.
- [ ] `service.py` has `/models/status` + `/models/download`.
- [ ] `/relief` accepts `backend` and resolves `auto` → full/lite.
- [ ] On the Mac, status reports `installed: false` and lite relief still works.

## Source

Handover §2 (`model_manager.py`, `/models/*` endpoints, `auto` resolution, UI behavior).
