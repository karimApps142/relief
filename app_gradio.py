"""
app_gradio.py — local UI for the depth-based relief pipeline.
Run: python app_gradio.py   (opens http://localhost:7860)
Image -> smooth monocular-depth heightmap (16-bit PNG) + STL, with a 3D preview.
"""
import numpy as np
from PIL import Image
import gradio as gr
from pipeline import generate_relief, ReliefParams
import relief_core as rc
import model_manager


def make_relief(image_path, depth_model, depth_mm, pixel_mm, refine, depth_smooth,
                depth_compress, invert, flatten_bg, tiling, make_solid):
    if not image_path:
        raise gr.Error("Upload an image first.")
    params = ReliefParams(
        depth_model=depth_model, relief_depth_mm=depth_mm, pixel_mm=pixel_mm,
        refine=refine, depth_smooth=depth_smooth, depth_compress=depth_compress,
        invert=invert, flatten_bg=flatten_bg, tiling=tiling, make_solid=make_solid,
    )
    out = generate_relief(image_path, "out/", params, backend="auto")
    return out["heightmap"], out["heightmap"], out["stl"], out["preview3d"]


# ---- optional models panel (only meaningful on the Windows GPU box) ----
def models_status_md():
    if model_manager.models_present():
        return "✅ **full** mode — models installed."
    return "⚠️ **lite/preview** mode — click *Download Models* (GPU box only)."


def do_download():
    logs = []
    model_manager.download_models(lambda m: logs.append(m))
    return "\n".join(logs), models_status_md()


GUIDE = """\
**Depth-based relief** — the heightmap is a smooth monocular **depth map** (near = high),
seated on a flat base. This is the correct data for bas-relief / CNC / lithophane: a
continuous height field, not an engraving.

- **Depth model** — *sapiens* = best for people/portraits (downloads ~4 GB on first use);
  *depth-anything* = general fallback.
- **Edge refine** — guided filter that snaps the smooth depth onto the *photo's* edges
  (jaw / hairline / collar) for crisp-but-smooth definition. The main "detail" lever.
- **Depth smoothing** — removes model noise; raise if the surface is lumpy.
- **Depth range** — lower (<1) flattens the nearest parts → shallower, more even relief.
- **Invert** — flip if the face comes out *sunken* instead of raised.
- **Flatten background** — seats the subject on a clean flat plate.
- **Hi-res tiling** — *depth-anything only* (skipped for sapiens). Runs the model on
  overlapping tiles for higher resolution; **slow** (many passes), so it's opt-in.

Geometry/refine sliders re-run instantly (the raw depth is cached per image)."""


with gr.Blocks(title="CNC Bas-Relief") as demo:
    gr.Markdown("# CNC Bas-Relief Generator\nImage → smooth depth heightmap + STL")
    with gr.Accordion("ℹ️ How it works / tuning", open=False):
        gr.Markdown(GUIDE)
    with gr.Row():
        with gr.Column():
            img = gr.Image(type="filepath", label="Input image")
            depth_model = gr.Radio(["sapiens", "depth-anything-3", "depth-anything"],
                                   value="sapiens", label="Depth model")
            depth_mm = gr.Slider(2, 20, value=8, step=0.5, label="Relief depth (mm)")
            pixel_mm = gr.Slider(0.02, 0.5, value=0.1, step=0.01, label="Pixel size (mm)")
            refine = gr.Slider(0.0, 1.0, value=0.6, step=0.05,
                               label="Edge refine (snap depth to photo edges)")
            depth_smooth = gr.Slider(0.0, 1.0, value=0.5, step=0.05,
                                     label="Depth smoothing (de-noise)")
            depth_compress = gr.Slider(0.4, 1.5, value=1.0, step=0.05,
                                       label="Depth range (lower = shallower / flatter)")
            with gr.Row():
                invert = gr.Checkbox(value=False, label="Invert (flip near/far)")
                flatten_bg = gr.Checkbox(value=True, label="Flatten background")
                tiling = gr.Checkbox(value=False, label="Hi-res tiling (depth-anything; slow)")
                make_solid = gr.Checkbox(value=False, label="Watertight solid (3D print)")
            go = gr.Button("Generate relief", variant="primary")
        with gr.Column():
            preview = gr.Image(label="Heightmap preview")
            model3d = gr.Model3D(label="3D preview (rotate / zoom — the real surface)")
            png_file = gr.File(label="16-bit heightmap (PNG)")
            stl_file = gr.File(label="STL")

    with gr.Accordion("Models (Windows GPU box)", open=False):
        status = gr.Markdown(models_status_md())
        dl = gr.Button("Download Models")
        dl_log = gr.Textbox(label="download log", lines=6)
        dl.click(do_download, outputs=[dl_log, status])

    go.click(make_relief,
             [img, depth_model, depth_mm, pixel_mm, refine, depth_smooth,
              depth_compress, invert, flatten_bg, tiling, make_solid],
             [preview, png_file, stl_file, model3d])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
