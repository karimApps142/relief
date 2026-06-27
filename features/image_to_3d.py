"""features/image_to_3d.py — Image → 3D (textured, industry-standard).

Upload a photo → reconstruct a TEXTURED 3D model (Hunyuan3D-2 shape + paint) via the kijai
ComfyUI-Hunyuan3DWrapper → export the textured GLB plus OBJ / STL / PLY and an interactive
3D preview. This is a real interchange-ready 3D asset (PBR-textured GLB for web/AR/DCC, STL/PLY
for print/CAD), not a relief heightmap.

WHY workflow-driven: the wrapper's textured pipeline is a large, frequently-updated graph
(shape → UV unwrap → multiview render → paint → bake → texture inpaint → export) that pulls in
several custom nodes and a compiled `custom_rasterizer` extension. Hardcoding it would rot. So we
drive an API-format workflow JSON exported once from ComfyUI (after validating it there — which
also confirms the custom_rasterizer build), substituting only the input image + seed. Provision
the nodes/model from the in-app ComfyUI setup panel; comfy_manager clones the wrapper + essentials
and fetches the shape DiT (paint/delight models auto-download on first run).

Setup the workflow once on the box:
  1. ComfyUI setup panel → Install (clones the wrapper + essentials) → Download (the ~4.9 GB DiT).
  2. Build custom_rasterizer (see the install log) — required for textures.
  3. In ComfyUI, load custom_nodes/ComfyUI-Hunyuan3DWrapper/example_workflows/hy3d_example_01.json,
     run it once to confirm a textured GLB comes out, then Save (API Format) to
     <repo>/data/hy3d_workflow_api.json  (or set HY3D_WORKFLOW_API to its path).
"""
import os
import json
import random
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

_ROOT = Path(__file__).resolve().parent.parent
# API-format workflow the headless run drives. Override with HY3D_WORKFLOW_API.
_WORKFLOW_CANDIDATES = [
    os.environ.get("HY3D_WORKFLOW_API"),
    str(_ROOT / "data" / "hy3d_workflow_api.json"),
]
_SETUP_HINT = (
    "No Hunyuan3D workflow found. One-time setup on the box:\n"
    "  1. ComfyUI setup panel → Install (clones the Hunyuan3D wrapper + essentials) → Download (the ~4.9 GB DiT).\n"
    "  2. Build custom_rasterizer for textures (see the install log).\n"
    "  3. In ComfyUI, load custom_nodes/ComfyUI-Hunyuan3DWrapper/example_workflows/hy3d_example_01.json,\n"
    "     run it once, then Save (API Format) to:\n"
    f"     {_ROOT / 'data' / 'hy3d_workflow_api.json'}\n"
    "     (or set the HY3D_WORKFLOW_API env var to wherever you saved it)."
)


def _load_workflow():
    for p in _WORKFLOW_CANDIDATES:
        if p and Path(p).is_file():
            return json.loads(Path(p).read_text(encoding="utf-8")), p
    return None, None


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
        graph, wf_path = _load_workflow()
        if graph is None:
            raise RuntimeError(_SETUP_HINT)
        graph = json.loads(json.dumps(graph))             # deep copy so we don't mutate the template

        client = ComfyUIClient()

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
