# Part 09 — Gradio UI (all-Python, OPTIONAL)

**Goal:** a tiny **all-Python** browser UI that sits right next to the pipeline — drag an image,
tune the knobs with sliders, preview the heightmap, download the PNG + STL. No Laravel, no queue,
no database, no S3. One file, one `python app_gradio.py`. **Skip if the CLI / API from Parts
03–05 is enough.**

**Runs on:** 🍎 Mac (lite — great for building/testing the UI) · 🪟 Windows 11 (full — real
output). Gradio runs anywhere Python runs.

**Prerequisites:** Part 03 (`pipeline.py`) is the minimum — Gradio calls `generate_relief`
**in-process**, no HTTP hop. Part 05 (`model_manager.py`) is needed only for the optional
"Download Models" panel. Real quality needs Parts 06–07 on Windows.

**Files created:** `app_gradio.py`. **Files changed:** add one line (`gradio`) to
`requirements.txt`.

---

## The big idea (why this replaces Laravel)

The FastAPI service already does all the real work. The "frontend backend" job is just: take an
upload, call `generate_relief`, show/download the result. Gradio collapses that whole layer into
a few dozen lines **in the same language as the pipeline** — it imports `generate_relief`
directly, so there's no separate web backend, no queue, no DB. `backend="auto"` means the same UI
is crude-but-working on the Mac (lite) and full-quality on Windows once weights are downloaded.

> `gradio` is pure-Python and pulls **no torch**, so it's safe to add to the light
> `requirements.txt` — the invariant (no GPU deps in the light file) still holds, and the UI is
> testable on the Mac.

---

## The code

### `app_gradio.py`

```python
"""
app_gradio.py — all-Python local UI for the relief pipeline.
Run: python app_gradio.py   (opens http://localhost:7860)
Backend = "auto": lite on the Mac, full on Windows once weights are downloaded.
"""
import gradio as gr
from pipeline import generate_relief, ReliefParams
import model_manager


def make_relief(image_path, depth_mm, pixel_mm, beta, detail_gain,
                normals, make_solid, flip_y, invert):
    if not image_path:
        raise gr.Error("Upload an image first.")
    params = ReliefParams(
        relief_depth_mm=depth_mm, pixel_mm=pixel_mm,
        compress_beta=beta, detail_gain=detail_gain,
        normals=normals, make_solid=make_solid,
        flip_y=flip_y, invert=invert,
    )
    out = generate_relief(image_path, "out/", params, backend="auto")
    # heightmap path feeds both the preview and the PNG download
    return out["heightmap"], out["heightmap"], out["stl"]


# ---- optional models panel (only meaningful on the Windows GPU box) ----
def models_status_md():
    if model_manager.models_present():
        return "✅ **full** mode — models installed."
    return "⚠️ **lite/preview** mode — click *Download Models* (GPU box only)."

def do_download():
    logs = []
    model_manager.download_models(lambda m: logs.append(m))
    return "\n".join(logs), models_status_md()


with gr.Blocks(title="CNC Bas-Relief") as demo:
    gr.Markdown("# CNC Bas-Relief Generator\nImage → 16-bit heightmap + STL")
    with gr.Row():
        with gr.Column():
            img = gr.Image(type="filepath", label="Input image")
            depth_mm = gr.Slider(2, 20, value=8, step=0.5, label="Relief depth (mm)")
            pixel_mm = gr.Slider(0.02, 0.5, value=0.1, step=0.01, label="Pixel size (mm)")
            beta = gr.Slider(0.1, 1.0, value=0.55, step=0.05,
                             label="compress_beta (lower = flatter)")
            detail = gr.Slider(0.5, 3.0, value=1.4, step=0.1, label="detail_gain")
            normals = gr.Radio(["stable", "marigold"], value="stable",
                               label="Normals model (full mode only)")
            with gr.Row():
                make_solid = gr.Checkbox(label="Watertight solid (3D print)")
                flip_y = gr.Checkbox(label="flip_y")
                invert = gr.Checkbox(label="invert")
            go = gr.Button("Generate relief", variant="primary")
        with gr.Column():
            preview = gr.Image(label="Heightmap preview")
            png_file = gr.File(label="16-bit heightmap (PNG)")
            stl_file = gr.File(label="STL")

    with gr.Accordion("Models (Windows GPU box)", open=False):
        status = gr.Markdown(models_status_md())
        dl = gr.Button("Download Models")
        dl_log = gr.Textbox(label="download log", lines=6)
        dl.click(do_download, outputs=[dl_log, status])

    go.click(make_relief,
             [img, depth_mm, pixel_mm, beta, detail, normals,
              make_solid, flip_y, invert],
             [preview, png_file, stl_file])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
```

### Add to `requirements.txt` (light — pulls no torch)

```txt
gradio
```

---

## Optional: serve the UI *on* the existing FastAPI service

If you'd rather run **one** server that exposes both the JSON API (`/relief`, `/models/*`) **and**
the UI, mount Gradio onto the FastAPI app instead of launching it standalone — add to
`service.py`:

```python
import gradio as gr
from app_gradio import demo

app = gr.mount_gradio_app(app, demo, path="/ui")
# now: uvicorn service:app  -> API at /relief, UI at http://localhost:8000/ui
```

Pick one: standalone `python app_gradio.py` (simplest), or mounted (one process for API + UI).

---

## Steps

1. `pip install gradio` and add the `gradio` line to `requirements.txt`.
2. Create `app_gradio.py` with the code above.
3. Launch it (lite on Mac, auto on Windows):

```bash
# Mac (crude preview, proves the UI + flow)
RELIEF_BACKEND=lite python app_gradio.py
# Windows (real output once weights downloaded)
python app_gradio.py
```

4. Open `http://localhost:7860`, upload an image, hit **Generate relief**, download the STL/PNG.
5. On Windows, expand **Models** → **Download Models** once; status flips to ✅ full.

---

## Verify

- `python app_gradio.py` opens a browser UI at `:7860`.
- Uploading an image and clicking Generate produces a heightmap **preview** + downloadable
  **16-bit PNG** + **STL**.
- On the Mac (lite) it's crude but works end-to-end; on Windows (full) it's sharp.
- The Models panel reports lite on the Mac and, after Download Models on Windows, full.

> If the 16-bit PNG preview looks washed out in the `gr.Image` widget (some viewers display
> `I;16` oddly), it's only the on-screen preview — the downloaded PNG is correct 16-bit. If it
> bothers you, return a normalized 8-bit copy *for the preview slot only*.

## Done when

- [ ] `gradio` added to `requirements.txt` (no torch pulled).
- [ ] `app_gradio.py` exists and launches.
- [ ] Upload → tune knobs → preview + download PNG + STL works in lite on the Mac.
- [ ] On Windows, `backend="auto"` gives full-quality output; the Download Models panel works.
- [ ] (Optional) UI mounted on the FastAPI service at `/ui` if you want a single server.

## Source

Replaces the original Laravel + frontend design (plan §6) with an all-Python Gradio UI, per your
choice. The queue (Horizon), database, and S3/Spaces from §6 are intentionally dropped — for a
local tool, in-process generation + on-disk job folders are enough. Credits/membership/payments
remain out of scope (plan §1).
