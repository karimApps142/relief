"""
app_gradio.py — all-Python local UI for the relief pipeline.
Run: python app_gradio.py   (opens http://localhost:7860)
Backend = "auto": lite on the Mac, full on Windows once weights are downloaded.
"""
import gradio as gr
from pipeline import generate_relief, ReliefParams
import model_manager


def make_relief(image_path, depth_mm, pixel_mm, form_strength,
                image_detail, fine_detail, micro_detail, clahe_clip, micro_gain,
                normals, make_solid, flip_y, invert):
    if not image_path:
        raise gr.Error("Upload an image first.")
    params = ReliefParams(
        relief_depth_mm=depth_mm, pixel_mm=pixel_mm,
        form_strength=form_strength, image_detail=image_detail,
        fine_detail=fine_detail, micro_detail=micro_detail,
        clahe_clip=clahe_clip, micro_gain=micro_gain,
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


TUNING_GUIDE = """\
**Engraved bas-relief engine** — a shallow global form with dominant multi-scale photographic
detail on a flat mid-gray base (the sculpt.ok approach). The defaults already target that look.

| Control | Default | Effect |
|---|---|---|
| **3D form** | 0.18 | global dome share — **lower = flatter / more engraved**, higher = bust-like |
| **Photo detail (medium)** | 1.0 | planes, fabric folds, broad texture |
| **Fine detail** | 0.7 | hair strands, lip lines |
| **Micro detail** | 0.5 | eyelashes, pores, skin micro-texture |
| **Local contrast** | 2.5 | CLAHE — pushes detail into smooth areas (cheeks) too |
| **Sharpen** | 0.6 | final crispness |

Keep **Normals = marigold**. Adjust from the result:
- **Still puffy / bust-like?** → lower *3D form* toward 0.10
- **Want more carving / texture?** → raise *Fine* + *Micro detail*, and *Local contrast* toward 3.5
- **Too noisy / grainy?** → lower *Micro detail* and *Sharpen*
- **Detail weak/flat in smooth areas?** → raise *Local contrast*

*This engine inverts the old balance: ~15% global form, ~85% multi-scale detail. The photo's own
luminance becomes the carved surface; depth only gives gentle overall shaping.*
"""


with gr.Blocks(title="CNC Bas-Relief") as demo:
    gr.Markdown("# CNC Bas-Relief Generator\nImage → 16-bit heightmap + STL")
    with gr.Accordion("📐 Tuning guide — chase the engraved / sculpt-style look", open=False):
        gr.Markdown(TUNING_GUIDE)
    with gr.Row():
        with gr.Column():
            img = gr.Image(type="filepath", label="Input image")
            depth_mm = gr.Slider(2, 20, value=8, step=0.5, label="Relief depth (mm)")
            pixel_mm = gr.Slider(0.02, 0.5, value=0.1, step=0.01, label="Pixel size (mm)")
            form_strength = gr.Slider(0.05, 0.40, value=0.18, step=0.01,
                                      label="3D form (lower = flatter / more engraved)")
            image_detail = gr.Slider(0.0, 2.0, value=1.0, step=0.05,
                                     label="Photo detail — medium (planes / fabric)")
            fine_detail = gr.Slider(0.0, 1.5, value=0.7, step=0.05,
                                    label="Fine detail — strands / lip lines")
            micro_detail = gr.Slider(0.0, 1.2, value=0.5, step=0.05,
                                     label="Micro detail — pores / lashes")
            clahe_clip = gr.Slider(1.0, 4.0, value=2.5, step=0.1,
                                   label="Local contrast (detail everywhere)")
            micro_gain = gr.Slider(0.0, 1.5, value=0.6, step=0.05,
                                   label="Sharpen")
            normals = gr.Radio(["marigold", "stable"], value="marigold",
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
             [img, depth_mm, pixel_mm, form_strength,
              image_detail, fine_detail, micro_detail, clahe_clip, micro_gain,
              normals, make_solid, flip_y, invert],
             [preview, png_file, stl_file])


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
