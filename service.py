"""
service.py — minimal inference API. The UI / a client calls POST /relief.
Run: uvicorn service:app --host 0.0.0.0 --port 8000

OUT_ROOT is a local ./data path so it works on macOS without root. Override
with the RELIEF_OUT_ROOT env var (e.g. /data/relief_jobs in production).
"""
import os
import uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

from pipeline import generate_relief, ReliefParams

app = FastAPI(title="Relief Service")
OUT_ROOT = Path(os.environ.get("RELIEF_OUT_ROOT", "data/relief_jobs"))


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/relief")
async def relief(
    file: UploadFile = File(...),
    relief_depth_mm: float = Form(8.0),
    pixel_mm: float = Form(0.1),
    normals: str = Form("stable"),
    make_solid: bool = Form(False),
):
    job = str(uuid.uuid4())
    out_dir = OUT_ROOT / job
    out_dir.mkdir(parents=True, exist_ok=True)

    src = out_dir / f"src_{file.filename}"
    src.write_bytes(await file.read())

    params = ReliefParams(relief_depth_mm=relief_depth_mm, pixel_mm=pixel_mm,
                          normals=normals, make_solid=make_solid)
    try:
        result = generate_relief(str(src), str(out_dir), params)
    except Exception as e:
        return JSONResponse(status_code=500, content={"job": job, "error": str(e)})

    return {"job": job, **result}
