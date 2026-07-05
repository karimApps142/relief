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


def model_ref_with_loras(graph, base_model_ref, loras):
    """Stack N model-only LoRAs by CHAINING LoraLoaderModelOnly nodes (each node's model
    output feeds the next), returning the final patched model ref. `loras` is a list of
    {"name": <file>, "strength": <float>} (bare strings also accepted, strength 1.0).
    Entries with a missing / "none" name are skipped. Order is irrelevant — model-only
    patches are additive deltas that commute. Uses string node ids ("lora0", "lora1", …)
    so they never collide with the hand-authored numeric ids.

    Only strength_model is meaningful: Krea-2 LoRAs are UNet-only (train_text_encoder=false),
    so there is no CLIP/text-encoder strength to set. Works over the GGUF UNet because
    ComfyUI-GGUF keeps it patchable. A LoRA whose keys don't match logs "lora key not
    loaded" in ComfyUI and is a silent no-op — the image is simply unchanged."""
    ref = base_model_ref
    i = 0
    for item in (loras or []):
        if isinstance(item, str):
            name, strength = item, 1.0
        elif isinstance(item, dict):
            name, strength = item.get("name"), item.get("strength", 1.0)
        else:
            continue
        if not name or name == "none":
            continue
        nid = f"lora{i}"
        i += 1
        graph[nid] = {"class_type": "LoraLoaderModelOnly", "inputs": {
            "model": ref, "lora_name": name, "strength_model": float(strength)}}
        ref = [nid, 0]
    return ref
