# Part 04 — FastAPI service (`service.py`)

**Goal:** create `service.py`, the minimal HTTP API around `generate_relief`. After this part you
can upload an image over HTTP and get back a heightmap + STL — tested entirely in **lite mode on
the Mac**, no models. (The `/models/*` endpoints and `auto` backend come in Part 05.)

**Runs on:** 🍎 Mac (lite) — and unchanged on 🪟 Windows (full)

**Prerequisites:** Part 03 (`pipeline.py`).

**Files created:** `service.py`

---

## The big idea

A stateless FastAPI app with two endpoints: `/health` (liveness) and `/relief` (multipart image
upload → runs the pipeline → returns JSON with the output paths). Each request gets a UUID job
folder under `OUT_ROOT`. This is the only thing the UI (the Gradio app in Part 09, or any client) needs to call.

---

## The code

### `service.py`

```python
"""
service.py — minimal inference API. The UI / a client calls POST /relief.
Run: uvicorn service:app --host 0.0.0.0 --port 8000
"""
import tempfile, uuid
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse

from pipeline import generate_relief, ReliefParams

app = FastAPI(title="Relief Service")
OUT_ROOT = Path("/data/relief_jobs")


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
```

> **Heads-up on `OUT_ROOT`:** the plan uses `/data/relief_jobs`, which needs root on macOS. For
> local Mac testing, either `sudo mkdir -p /data/relief_jobs && sudo chown $(whoami) /data` once,
> or change `OUT_ROOT` to a local path like `Path("./data/relief_jobs")`. Keep it consistent with
> your `.gitignore` (`/data/` is already ignored).

---

## Steps

1. Create `service.py` with the code above.
2. (Mac) ensure `OUT_ROOT` is writable — easiest is to set `OUT_ROOT = Path("./data/relief_jobs")`
   for local dev.
3. Start the service in lite mode and hit it:

```bash
RELIEF_BACKEND=lite uvicorn service:app --reload --port 8000
```

```bash
# in another terminal
curl -s http://localhost:8000/health
# {"ok":true}

curl -s -F "file=@input.jpg" -F "make_solid=true" http://localhost:8000/relief
# {"job":"<uuid>","heightmap":".../relief_heightmap.png","stl":".../relief.stl"}
```

---

## Verify

- `GET /health` returns `{"ok": true}`.
- `POST /relief` with an image returns `200` and a JSON body with `job`, `heightmap`, `stl`.
- The referenced PNG (16-bit) and STL exist on disk under the job folder.
- Interactive docs at `http://localhost:8000/docs` let you upload from the browser.

## Done when

- [ ] `service.py` exists with `/health` and `/relief`.
- [ ] Service starts under `uvicorn` in lite mode.
- [ ] An uploaded image round-trips to a heightmap + STL via HTTP.
- [ ] Errors return a `500` JSON `{job, error}` rather than crashing the worker.

## Source

Plan §5.4 (`service.py`). The `/models/*` endpoints + `auto` backend resolution are added next
in Part 05.
