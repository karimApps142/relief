"""features/image_to_3d.py — Image → 3D (textured, industry-standard).

Upload a photo → reconstruct a TEXTURED 3D model (Hunyuan3D-2 shape + paint) via the kijai
ComfyUI-Hunyuan3DWrapper → export the textured GLB plus OBJ / STL / PLY and an interactive
3D preview. This is a real interchange-ready 3D asset (PBR-textured GLB for web/AR/DCC, STL/PLY
for print/CAD), not a relief heightmap.

WHY workflow-driven: the wrapper's textured pipeline is a large, frequently-updated graph
(shape → UV unwrap → multiview render → paint → bake → texture inpaint → export) that pulls in
several custom nodes and a compiled `custom_rasterizer` extension. Hardcoding it would rot. So we
drive an API-format workflow JSON and substitute only the input image + seed.

The workflow is built AUTOMATICALLY — no manual ComfyUI step. On first run the feature reads the
wrapper's bundled UI example (custom_nodes/ComfyUI-Hunyuan3DWrapper/example_workflows/), fetches
ComfyUI's /object_info, converts UI→API the same way the frontend does (features/_hy3d.py), prunes
to the textured-export branch, and caches it to data/hy3d_workflow_api.json. Fallbacks: a prior
ComfyUI run in /history, then an override file (or HY3D_WORKFLOW_API).

Setup once on the box (all via the in-app ComfyUI setup panel + install log):
  1. Install (clones the wrapper + essentials) → Download (the ~4.9 GB DiT) → Start the engine.
  2. Build custom_rasterizer (see the install log) — required for textures.
Then just upload an image and Generate.
"""
import os
import json
import random
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _ROOT / "data" / "hy3d_workflow_api.json"          # learned/overridable API workflow
# API-format workflow the headless run drives. Override with HY3D_WORKFLOW_API.
_WORKFLOW_CANDIDATES = [os.environ.get("HY3D_WORKFLOW_API"), str(_CACHE)]
_SETUP_HINT = (
    "Couldn't prepare the Hunyuan3D workflow automatically. Check on the box:\n"
    "  1. ComfyUI setup panel shows Install ✓ (Hunyuan3D wrapper + essentials) and the engine RUNNING.\n"
    "  2. The ~4.9 GB shape model is downloaded.\n"
    "  3. custom_rasterizer is built — needed for textures (the build command is in the Install log).\n"
    "If all of that is done and it still fails, drop an API-format graph at data/hy3d_workflow_api.json\n"
    "(or set HY3D_WORKFLOW_API to its path)."
)


def _cache(graph):
    try:
        _CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE.write_text(json.dumps(graph), encoding="utf-8")
    except Exception:
        pass


def _load_workflow():
    for p in _WORKFLOW_CANDIDATES:
        if p and Path(p).is_file():
            return json.loads(Path(p).read_text(encoding="utf-8")), p
    return None, None


def _autobuild_workflow(client):
    """Build the textured workflow ourselves — no manual ComfyUI step. Read the wrapper's bundled
    UI example and convert it to a pruned API prompt using ComfyUI's live /object_info."""
    try:
        import comfy_manager as cm
        from ._hy3d import build_textured_prompt
        exdir = cm.COMFY_DIR / "custom_nodes" / "ComfyUI-Hunyuan3DWrapper" / "example_workflows"
        example = next((exdir / n for n in ("hy3d_example_01.json", "hy3d_example_1.json")
                        if (exdir / n).is_file()), None)
        if example is None:
            return None
        ui = json.loads(example.read_text(encoding="utf-8"))
        graph, exp = build_textured_prompt(ui, client.get_object_info())
        ctypes = {nd.get("class_type") for nd in (graph or {}).values()}
        if exp is None or not ({"Hy3DGenerateMesh", "Hy3DExportMesh"} <= ctypes):
            return None
        _cache(graph)
        return graph
    except Exception as e:
        print(f"[image3d] auto-build skipped ({e})")
        return None


def _learn_workflow_from_history(client):
    """Fallback: recover the API graph from a prior ComfyUI run (its exact prompt is in /history)."""
    try:
        hist = client.get_history(max_items=200)
    except Exception:
        return None
    best_num, best_graph = -1.0, None
    for entry in (hist or {}).values():
        prompt = entry.get("prompt") if isinstance(entry, dict) else None
        if not isinstance(prompt, list) or len(prompt) < 3 or not isinstance(prompt[2], dict):
            continue
        num, graph = prompt[0], prompt[2]
        if any(isinstance(nd, dict) and str(nd.get("class_type", "")).startswith("Hy3D")
               for nd in graph.values()):
            try:
                num = float(num)
            except Exception:
                num = 0.0
            if num >= best_num:
                best_num, best_graph = num, graph
    if best_graph is not None:
        _cache(best_graph)
    return best_graph


def _nodes_of(graph, class_type):
    return [nid for nid, nd in graph.items()
            if isinstance(nd, dict) and nd.get("class_type") == class_type]


class ImageTo3DFeature(Feature):
    id = "image3d"
    name = "Image → 3D"
    description = ("Photo → textured 3D model (Hunyuan3D shape + paint). Exports a PBR-textured "
                  "GLB plus OBJ / STL / PLY and an interactive 3D preview.")
    needs_comfy = True
    inputs = ["image"]
    engine = "comfy"
    icon = "box"
    est_runtime = "~2–8 min"
    vram = "~8–12 GB"
    output_kinds = ["Textured GLB", "3D preview", "OBJ", "STL", "PLY"]
    params = [
        ParamSpec("seed", "number", 0, "Seed (0 = random)", 0, 2_147_483_647, 1, control="stepper",
                  help="Patched into the workflow's shape-generation node. 0 = a fresh random seed each run."),
        ParamSpec("formats", "select", "all", "Extra exports", control="seg", group="advanced",
                  help="The textured GLB is always produced; also re-export these geometry formats.",
                  choices=[{"value": "all", "label": "OBJ+STL+PLY"}, {"value": "obj", "label": "OBJ"},
                           {"value": "stl", "label": "STL"}, {"value": "none", "label": "GLB only"}]),
    ]

    def run(self, inputs, params, out_dir):
        out = Path(out_dir)
        client = ComfyUIClient()

        # 0. find the API workflow: an override/cached file → else build it from the wrapper's
        #    example via /object_info → else recover it from a prior ComfyUI run in /history.
        graph, _src = _load_workflow()
        if graph is None:
            graph = _autobuild_workflow(client) or _learn_workflow_from_history(client)
        if graph is None:
            raise RuntimeError(_SETUP_HINT)
        graph = json.loads(json.dumps(graph))             # deep copy so we don't mutate the template

        # 1. upload the photo, point every LoadImage / Hy3DUploadMesh-style image input at it.
        src = Image.open(inputs["image"]).convert("RGB")
        tmp = out / "img3d_input.png"; src.save(tmp)
        name = client.upload_image(str(tmp))
        load_nodes = _nodes_of(graph, "LoadImage")
        for nid in load_nodes:
            graph[nid].setdefault("inputs", {})["image"] = name
        if not load_nodes:
            raise RuntimeError("The workflow has no LoadImage node to feed the photo into — "
                               "re-export an API-format workflow whose input is a LoadImage node.")

        # 2. seed: patch the shape-generation node unless the user pinned one.
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        for nid in _nodes_of(graph, "Hy3DGenerateMesh"):
            if "seed" in graph[nid].get("inputs", {}):
                graph[nid]["inputs"]["seed"] = seed

        # 3. run headless → fetch the TEXTURED glb (the graph exports an untextured one too).
        glb = client.generate_file(graph, exts=(".glb",), prefer="textured",
                                   label="image3d·textured", max_wait=1800)
        model = out / "model.glb"; model.write_bytes(glb)
        arts = {"model_glb": str(model), "preview3d": str(model)}

        # 4. re-export industry-standard geometry formats from the textured GLB.
        want = {"all": ("obj", "stl", "ply"), "obj": ("obj",), "stl": ("stl",), "none": ()}
        exts = want.get(params.get("formats", "all"), ("obj", "stl", "ply"))
        if exts:
            try:
                import trimesh
                mesh = trimesh.load(str(model), force="mesh")
                for ext in exts:
                    p = out / f"model.{ext}"
                    try:
                        mesh.export(str(p)); arts[f"model_{ext}"] = str(p)
                    except Exception as e:
                        print(f"[image3d] {ext} export skipped ({e})")
            except Exception as e:
                print(f"[image3d] geometry re-export skipped ({e})")
        return arts
