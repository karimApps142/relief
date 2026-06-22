"""
service.py — minimal inference API. The UI / a client calls POST /relief.
Run: uvicorn service:app --host 0.0.0.0 --port 8000

OUT_ROOT is a local ./data path so it works on macOS without root. Override
with the RELIEF_OUT_ROOT env var (e.g. /data/relief_jobs in production).
"""
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse

from pipeline import generate_relief, ReliefParams
import model_manager

app = FastAPI(title="Relief Service")
OUT_ROOT = Path(os.environ.get("RELIEF_OUT_ROOT", "data/relief_jobs"))

_dl = {"running": False, "log": []}


@app.get("/health")
def health():
    return {"ok": True}


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


@app.post("/relief")
async def relief(
    file: UploadFile = File(...),
    relief_depth_mm: float = Form(8.0),
    pixel_mm: float = Form(0.1),
    normals: str = Form("stable"),
    make_solid: bool = Form(False),
    backend: str = Form("auto"),
):
    if backend == "auto":                      # full if weights present, else lite
        backend = "full" if model_manager.models_present() else "lite"

    job = str(uuid.uuid4())
    out_dir = OUT_ROOT / job
    out_dir.mkdir(parents=True, exist_ok=True)

    src = out_dir / f"src_{file.filename}"
    src.write_bytes(await file.read())

    params = ReliefParams(relief_depth_mm=relief_depth_mm, pixel_mm=pixel_mm,
                          normals=normals, make_solid=make_solid)
    try:
        result = generate_relief(str(src), str(out_dir), params, backend=backend)
    except Exception as e:
        return JSONResponse(status_code=500, content={"job": job, "error": str(e)})

    return {"job": job, "backend": backend, **result}
