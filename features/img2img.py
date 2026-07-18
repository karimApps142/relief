"""features/img2img.py — Image -> Image with Krea-2-Turbo (GGUF) via ComfyUI.

Two paths, picked by the `style_ref` switch:

• DEFAULT (denoise) — encodes the uploaded image to a latent and re-diffuses it under a
  prompt at partial denoise (lower = closer to the original). Same loaders/sampler as
  text2img; the only difference is VAEEncode(LoadImage) feeding the KSampler's latent.

• STYLE REFERENCE — ostris's krea2_turbo_style_reference LoRA + his ComfyUI-Krea2-Ostris-Edit
  nodes. The upload is a *reference* rather than a starting point: it is encoded through the
  Krea-2 Qwen3-VL text encoder AND attached as reference latents, then the image is generated
  from empty at full denoise. That makes it an edit/restyle ("make this person a cyclops")
  instead of a blend, so it keeps identity without inheriting the original's pixels.
  No trigger word — just the image + a prompt.

Both paths reuse the same Krea core (unet + qwen3vl encoder + qwen VAE); style reference adds
only a 457 MB LoRA. See comfy_manager.KREA2_EDIT_MODELS / KREA2EDIT_GIT.
"""
from pathlib import Path
from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient
from . import _lora

_STYLE_LORA = "krea2_style_reference.safetensors"
_STYLE_NODE = "ComfyUI-Krea2-Ostris-Edit"


def _build_graph(image_name, prompt, denoise, steps, seed, gguf, loras=None):
    graph = {
        "16": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": gguf}},
        "18": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "4":  {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "6":  {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["18", 0]}},
        "8":  {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["6", 0]}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "12": {"class_type": "VAEEncode", "inputs": {"pixels": ["11", 0], "vae": ["4", 0]}},
        "2":  {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": 1.0,
            "sampler_name": "er_sde", "scheduler": "simple", "denoise": float(denoise),
            "model": ["16", 0], "positive": ["6", 0], "negative": ["8", 0],
            "latent_image": ["12", 0]}},
        "3":  {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["4", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"filename_prefix": "krea2/i2i", "images": ["3", 0]}},
    }
    graph["2"]["inputs"]["model"] = _lora.model_ref_with_loras(graph, ["16", 0], loras)
    return graph


def _build_style_graph(image_name, prompt, width, height, steps, seed, gguf,
                       loras=None, ref_strength=1.0):
    """Ostris Krea-2 reference path. Topology from his template workflow:
        UnetLoaderGGUF -> [user LoRAs] -> style LoRA -> Krea2OstrisEditModelPatch -> KSampler
        CLIPLoader(krea2) -> TextEncodeKrea2OstrisEdit(prompt + image + VAE) -> positive
        CLIPLoader(krea2) -> TextEncodeKrea2OstrisEdit(empty prompt)         -> negative

    Wiring the VAE into the encoder is what turns each reference image into a reference
    LATENT (without it the image is only seen by the VL tower at 384x384 — style but no
    detail). The patch node is not optional: stock Krea-2 drops reference latents on the
    floor, so omitting it silently ignores the reference and looks like the LoRA "did
    nothing". kv_cache stays off — that path is only for LoRAs trained with ai-toolkit's
    kv_cache kwarg, which this one was not. Sampler/cfg/denoise follow the template
    (euler/simple, cfg 1, full denoise — we generate, we don't blend).
    """
    graph = {
        "16": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": gguf}},
        "18": {"class_type": "CLIPLoader", "inputs": {
            "clip_name": "qwen3vl_4b_fp8_scaled.safetensors", "type": "krea2", "device": "default"}},
        "4":  {"class_type": "VAELoader", "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "11": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "6":  {"class_type": "TextEncodeKrea2OstrisEdit", "inputs": {
            "clip": ["18", 0], "prompt": prompt, "vae": ["4", 0], "image1": ["11", 0]}},
        "8":  {"class_type": "TextEncodeKrea2OstrisEdit", "inputs": {
            "clip": ["18", 0], "prompt": ""}},
        "10": {"class_type": "EmptyLatentImage", "inputs": {
            "width": int(width), "height": int(height), "batch_size": 1}},
        "20": {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ["16", 0], "lora_name": _STYLE_LORA, "strength_model": float(ref_strength)}},
        "21": {"class_type": "Krea2OstrisEditModelPatch", "inputs": {
            "model": ["20", 0], "kv_cache": False}},
        "2":  {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": 1.0,
            "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0,
            "model": ["21", 0], "positive": ["6", 0], "negative": ["8", 0],
            "latent_image": ["10", 0]}},
        "3":  {"class_type": "VAEDecode", "inputs": {"samples": ["2", 0], "vae": ["4", 0]}},
        "22": {"class_type": "SaveImage", "inputs": {"filename_prefix": "krea2/style", "images": ["3", 0]}},
    }
    # the user's own LoRAs stack UNDER the style LoRA (model-only deltas commute, so the
    # order is cosmetic) — the patch must stay LAST, closest to the sampler.
    graph["20"]["inputs"]["model"] = _lora.model_ref_with_loras(graph, ["16", 0], loras)
    return graph


def _style_preflight():
    """Fail fast with a fixable message. Without this the run dies deep inside ComfyUI as an
    opaque validation error ('node type not found' / 'value_not_in_list')."""
    from comfy_manager import COMFY_DIR
    missing = []
    if not (COMFY_DIR / "custom_nodes" / _STYLE_NODE).exists():
        missing.append("the Krea-2 Ostris Edit node")
    if not (COMFY_DIR / "models" / "loras" / _STYLE_LORA).exists():
        missing.append(f"{_STYLE_LORA} (~457 MB)")
    if missing:
        raise RuntimeError(
            "Style reference is missing " + " and ".join(missing) +
            ". Click 'Install style reference' next to the Style reference switch — it installs "
            "both and reloads the engine. (The ComfyUI setup panel does not cover this add-on.)")


class Img2ImgFeature(Feature):
    id = "img2img"
    name = "Image → Image"
    description = "Transform an image with a prompt (Krea-2-Turbo img2img, via ComfyUI)."
    needs_comfy = True
    engine = "comfy"
    icon = "image"
    est_runtime = "~5–20 s"
    vram = "~9–10 GB"
    output_kinds = ["Image PNG"]
    inputs = ["image"]
    params = [
        ParamSpec("prompt", "text", "", "Prompt", placeholder="Describe how to transform it…"),
        ParamSpec("style_ref", "bool", False, "Style reference", control="switch",
                  help="Treat the upload as a reference to work FROM rather than a starting "
                       "image to blend: Krea-2 regenerates fully, guided by the reference plus "
                       "your prompt (ostris style-reference LoRA). Better at edits and restyles "
                       "that keep the subject — 'make this person a cyclops', 'same scene in "
                       "winter'. No trigger word needed. Needs the Krea-2 Ostris Edit node + LoRA "
                       "(ComfyUI setup panel)."),
        ParamSpec("denoise", "number", 0.6, "Denoise strength", 0.1, 1.0, 0.05, control="slider",
                  help="Lower stays close to the original; higher reinvents it.",
                  depends_on={"param": "style_ref", "value": False}),
        ParamSpec("ref_strength", "number", 1.0, "Reference strength", 0.2, 1.5, 0.05,
                  control="slider", depends_on={"param": "style_ref", "value": True},
                  help="How hard the style-reference LoRA pulls toward the reference image. "
                       "1.0 is what it was trained at; lower frees the prompt, higher clings "
                       "to the reference (and can get rigid)."),
        ParamSpec("width", "number", 1024, "Width", 512, 2048, 64, control="slider", suffix=" px",
                  help="Output is scaled to fit within Width×Height (aspect ratio preserved)."),
        ParamSpec("height", "number", 1024, "Height", 512, 2048, 64, control="slider", suffix=" px",
                  help="Output is scaled to fit within Width×Height (aspect ratio preserved)."),
        ParamSpec("quant", "select", "Q4_K_M", "Quantization", control="seg", group="advanced",
                  help="Quality vs VRAM.",
                  choices=[{"value": "Q3_K_M", "label": "Q3"}, {"value": "Q4_K_M", "label": "Q4"},
                           {"value": "Q5_K_M", "label": "Q5"}, {"value": "Q6_K", "label": "Q6"}]),
        ParamSpec("steps", "number", 8, "Steps", 4, 20, 1, control="slider", group="advanced"),
        ParamSpec("seed", "number", 0, "Seed", 0, 2_147_483_647, 1, control="stepper", group="advanced",
                  help="0 = random."),
        ParamSpec("clarity_upscale", "bool", False, "Clarity upscale (Balanced)", control="switch",
                  group="advanced",
                  help="After transforming, run Clarity Upscale (Balanced) on the result — adds fine "
                       "detail and 2× size. Needs the Clarity models installed (see the Clarity tab)."),
        ParamSpec("loras", "lora", [], "LoRAs", control="lora", group="advanced",
                  help="Stack one or more custom Krea-2 LoRAs, each with its own strength. "
                       "Drop a .safetensors file to add it to the list."),
    ]

    def run(self, inputs, params, out_dir):
        import random
        from PIL import Image
        style = bool(params.get("style_ref"))
        if style:
            _style_preflight()                    # before any upload/VRAM work
        client = ComfyUIClient()
        out_dir = Path(out_dir)

        # scale the source to fit within Width×Height (aspect preserved), snapped to /16 for the
        # VAE — this sets the img2img working/output resolution (like text2img's width/height).
        src = Image.open(inputs["image"]).convert("RGB")
        W, H = int(params.get("width", 1024)), int(params.get("height", 1024))
        f = min(W / src.width, H / src.height)
        nw = max(64, int(round(src.width * f)) // 16 * 16)
        nh = max(64, int(round(src.height * f)) // 16 * 16)
        tmp = out_dir / "img2img_input.png"
        src.resize((nw, nh), Image.LANCZOS).save(tmp)
        name = client.upload_image(str(tmp))

        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        gguf = f"krea2_turbo-{params['quant']}.gguf"
        if style:
            # nw/nh (the aspect-preserved fit of Width×Height) also sizes the empty latent,
            # so the output keeps the source's shape instead of a forced square.
            graph = _build_style_graph(name, params.get("prompt", ""), nw, nh,
                                       params["steps"], seed, gguf,
                                       loras=params.get("loras"),
                                       ref_strength=params.get("ref_strength", 1.0))
        else:
            graph = _build_graph(name, params.get("prompt", ""), params["denoise"],
                                 params["steps"], seed, gguf, loras=params.get("loras"))
        out = out_dir / "img2img.png"
        out.write_bytes(client.generate(graph))

        # optional finishing pass: reuse the Clarity feature (Balanced preset) on the result.
        if params.get("clarity_upscale"):
            from .clarity import ClarityFeature
            cf = ClarityFeature()
            return cf.run({"image": str(out)}, cf.coerce({}), out_dir)   # SD1.5 tile-CN detail upscale
        return {"image": str(out)}
