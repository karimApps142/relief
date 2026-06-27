"""features/_lora.py — splice an optional custom LoRA into a Krea-2-Turbo graph.

Krea-2 LoRAs (the ai-toolkit recipe trains with train_text_encoder=false) are
UNet-only, so we use the core LoraLoaderModelOnly node: it patches just the diffusion
model and leaves the CLIP/text-encoder path untouched. This also works on the GGUF UNet
(ComfyUI-GGUF makes the loaded model patchable), so it composes with our existing
UnetLoaderGGUF graphs without any extra custom node.

The LoRA file must live in ComfyUI/models/loras/ — the UI's drag-drop uploader
(POST /api/loras -> comfy_manager.save_lora) puts it there, and ComfyUI re-scans that
folder when the graph is submitted, so a freshly-added file is usable immediately.
"""

_LORA_NODE = "17"          # graph id for the spliced loader (free in our hand-authored graphs)


def model_ref_with_lora(graph, base_model_ref, lora, strength, node_id=_LORA_NODE):
    """If `lora` names a real file (not None / "none"), add a LoraLoaderModelOnly node
    fed by `base_model_ref` and return the *patched* model ref to wire into the sampler;
    otherwise return `base_model_ref` unchanged (no LoRA, no extra node)."""
    if not lora or lora == "none":
        return base_model_ref
    graph[node_id] = {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {"model": base_model_ref, "lora_name": lora,
                   "strength_model": float(strength)},
    }
    return [node_id, 0]
