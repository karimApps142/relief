"""
server.py — modular feature API (Phase 2 backend).

One generic router serves EVERY registered feature, so the frontend is built once
and new features appear automatically:
  GET  /api/features                 -> [feature schema, ...] (UI renders from this)
  POST /api/features/{id}/run        -> {job, artifacts:{name:url}}  (multipart: file + params JSON)
  GET  /api/jobs/{job}/{name}        -> the artifact file (PNG/STL/GLB/…)

Run: uvicorn server:app --host 0.0.0.0 --port 8000
(The legacy service.py and app_gradio.py still work during the migration.)
"""
import os
import json
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.concurrency import run_in_threadpool

from features import REGISTRY
import model_manager
import comfy_manager
import system_info
import relief_progress

_DEPTH_LABEL = {"depth-anything": "Depth-Anything-V2", "depth-anything-3": "Depth-Anything-3",
                "sapiens": "Sapiens depth"}

app = FastAPI(title="Relief Studio API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
OUT_ROOT = Path(os.environ.get("RELIEF_OUT_ROOT", "data/jobs"))
OUT_ROOT.mkdir(parents=True, exist_ok=True)


@app.get("/api/health")
def health():
    return {"ok": True, "features": list(REGISTRY)}


@app.get("/api/features")
def list_features():
    return [f.schema() for f in REGISTRY.values()]


@app.get("/api/models/status")
def models_status():
    return model_manager.status()


@app.post("/api/models/download")
def models_download():
    """Download the CORE relief weights (BiRefNet + Depth-Anything-V2) in the
    background; the next relief run then uses the full GPU backend (no restart)."""
    return {"started": model_manager.download_async(), **model_manager.status()}


# ---- ComfyUI engine: install / download / launch, all driven from the UI ----
@app.get("/api/comfy/status")
def comfy_status():
    return comfy_manager.status()


@app.post("/api/comfy/install")
def comfy_install():
    return {"started": comfy_manager.install_async(), **comfy_manager.status()}


@app.post("/api/comfy/download")
def comfy_download():
    return {"started": comfy_manager.download_async(), **comfy_manager.status()}


@app.post("/api/comfy/start")
def comfy_start():
    return comfy_manager.start()


@app.post("/api/comfy/restart")
def comfy_restart():
    return {"started": comfy_manager.restart_async(), **comfy_manager.status()}


@app.post("/api/comfy/interrupt")
def comfy_interrupt():
    """Cancel the in-flight ComfyUI generation (stops the GPU work)."""
    return comfy_manager.interrupt()


@app.get("/api/comfy/progress")
def comfy_progress():
    """Live generation progress (sampler steps) for the in-flight ComfyUI job."""
    from features._comfy import get_progress
    return get_progress()


# ---- Custom LoRAs: list / drag-drop upload / remove (drop-in, no restart) ----
@app.get("/api/loras")
def loras_list():
    """Custom LoRA files available to text2img/img2img (ComfyUI/models/loras/*.safetensors)."""
    return {"loras": comfy_manager.list_loras()}


@app.post("/api/loras")
async def loras_upload(file: UploadFile = File(...)):
    """Save an uploaded .safetensors LoRA so the next Generate can use it (no restart)."""
    try:
        saved = comfy_manager.save_lora(file.filename, await file.read())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"saved": saved, "loras": comfy_manager.list_loras()}


@app.delete("/api/loras/{name}")
def loras_delete(name: str):
    comfy_manager.delete_lora(name)
    return {"loras": comfy_manager.list_loras()}


@app.get("/api/progress")
def progress():
    """Unified live progress: ComfyUI sampler steps OR relief phase stepper, whichever
    is active (one workflow runs at a time)."""
    from features._comfy import get_progress
    cp = get_progress()
    if cp.get("active"):
        return {"active": True, "engine": "comfy", **cp}
    rp = relief_progress.get()
    if rp.get("active"):
        return {"active": True, "engine": "local", **rp}
    return {"active": False, "engine": None}


@app.get("/api/system")
def system():
    """Real GPU/host telemetry for the System & health panel (nvidia-smi + disk)."""
    return system_info.system()


@app.get("/api/jobs")
def list_jobs(limit: int = 24):
    """Recent generations (most recent first) for the history panel — read from the
    persisted job.json under each data/jobs/<id>/."""
    items = []
    for d in OUT_ROOT.iterdir() if OUT_ROOT.exists() else []:
        jf = d / "job.json"
        if jf.exists():
            try:
                items.append((jf.stat().st_mtime, json.loads(jf.read_text())))
            except Exception:
                pass
    items.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in items[:limit]]


def _free_relief_vram():
    """Unload our in-process depth/matting models so ComfyUI (separate process)
    can claim the 12 GB. Best-effort; harmless if nothing is loaded."""
    try:
        import models
        models.unload_all()
    except Exception:
        pass


def _human_size(nbytes):
    n = float(nbytes)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _model_label(feat, coerced):
    if feat.engine == "comfy":
        if feat.id == "upscale":
            return coerced.get("model_name", "")
        if feat.id == "clarity":
            return "Clarity · " + coerced.get("checkpoint", "").replace(".safetensors", "")
        return "Krea-2-Turbo " + coerced.get("quant", "Q4_K_M")
    return _DEPTH_LABEL.get(coerced.get("depth_model"), coerced.get("depth_model", ""))


def _build_meta(feat, coerced, artifacts, duration):
    """Real per-run metadata read off the produced files (dims, size) + params."""
    img_path = next((artifacts[k] for k in ("heightmap", "image") if k in artifacts), None)
    if img_path is None:
        img_path = next((v for v in artifacts.values()
                         if str(v).lower().endswith((".png", ".jpg", ".jpeg", ".webp"))), None)
    dims = ""
    if img_path:
        try:
            from PIL import Image
            with Image.open(img_path) as im:
                dims = f"{im.width} × {im.height}"
        except Exception:
            pass
    total = sum(os.path.getsize(v) for v in artifacts.values() if os.path.exists(v))
    return {
        "duration_s": round(duration, 1),
        "dimensions": dims,
        "file_size": _human_size(total) if total else "",
        "model": _model_label(feat, coerced),
        "seed": coerced.get("seed"),
        "params": coerced,
    }


@app.post("/api/features/{fid}/run")
async def run_feature(fid: str, file: UploadFile = File(None), params: str = Form("{}")):
    feat = REGISTRY.get(fid)
    if feat is None:
        raise HTTPException(404, f"unknown feature: {fid}")
    try:
        raw = json.loads(params or "{}")
    except json.JSONDecodeError:
        raise HTTPException(400, "params must be a JSON object")

    job = uuid.uuid4().hex[:12]
    out_dir = OUT_ROOT / job
    out_dir.mkdir(parents=True, exist_ok=True)

    inputs = {}
    if file is not None:
        dst = out_dir / f"input_{file.filename}"
        dst.write_bytes(await file.read())
        inputs["image"] = str(dst)

    coerced = feat.coerce(raw)

    def _execute():
        # Runs in a worker thread (run_in_threadpool) so the event loop stays free to
        # serve /api/progress + /api/system polls during a long generation.
        if getattr(feat, "needs_comfy", False):           # ComfyUI-backed feature
            _free_relief_vram()                           # free the 12 GB for ComfyUI
            system_info.set_resident("image", _model_label(feat, coerced))
            comfy_manager.ensure_running()                # auto-start if installed & down
        else:
            system_info.set_resident("relief", _model_label(feat, coerced))
        return feat.run(inputs, coerced, out_dir)

    t0 = time.monotonic()
    try:
        artifacts = await run_in_threadpool(_execute)
    except Exception as e:  # surface the error to the client instead of a 500 page
        return JSONResponse(status_code=500, content={"job": job, "error": str(e)})

    duration = time.monotonic() - t0
    urls = {k: f"/api/jobs/{job}/{Path(v).name}" for k, v in artifacts.items()}
    meta = _build_meta(feat, coerced, artifacts, duration)
    thumb = next((urls[k] for k in ("heightmap", "image") if k in urls),
                 next((u for u in urls.values()
                       if u.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))), None))
    record = {"job": job, "feature": fid, "name": feat.name, "icon": feat.icon,
              "engine": feat.engine, "created_at": time.time(), "duration_s": meta["duration_s"],
              "artifacts": urls, "thumb": thumb, "meta": meta}
    try:
        (out_dir / "job.json").write_text(json.dumps(record))
    except Exception:
        pass
    return record


@app.get("/api/jobs/{job}/{name}")
def get_artifact(job: str, name: str):
    path = OUT_ROOT / job / name
    if not path.exists():
        raise HTTPException(404, "artifact not found")
    return FileResponse(str(path))


# Serve the built React UI (web/dist) at "/" when present — single-process prod
# deploy (uvicorn server:app serves both the API and the UI). Mounted last so the
# /api/* routes above take precedence. In dev, run Vite separately (it proxies /api).
_DIST = Path(__file__).parent / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
