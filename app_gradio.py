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
