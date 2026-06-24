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


@app.get("/api/comfy/progress")
def comfy_progress():
    """Live generation progress (sampler steps) for the in-flight ComfyUI job."""
    from features._comfy import get_progress
    return get_progress()


def _free_relief_vram():
    """Unload our in-process depth/matting models so ComfyUI (separate process)
    can claim the 12 GB. Best-effort; harmless if nothing is loaded."""
    try:
        import models
        models.unload_all()
    except Exception:
        pass


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
        # serve /api/comfy/progress + /api/comfy/status polls during a long generation.
        if getattr(feat, "needs_comfy", False):           # ComfyUI-backed feature
            _free_relief_vram()                           # free the 12 GB for ComfyUI
            comfy_manager.ensure_running()                # auto-start if installed & down
        return feat.run(inputs, coerced, out_dir)

    try:
        artifacts = await run_in_threadpool(_execute)
    except Exception as e:  # surface the error to the client instead of a 500 page
        return JSONResponse(status_code=500, content={"job": job, "error": str(e)})

    urls = {k: f"/api/jobs/{job}/{Path(v).name}" for k, v in artifacts.items()}
    return {"job": job, "feature": fid, "artifacts": urls}


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
