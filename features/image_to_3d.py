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
from ._comfy import ComfyUIClient, ComfyUIError

_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _ROOT / "data" / "hy3d_workflow_api.json"          # learned/overridable API workflow
_UNTEX_CACHE = _ROOT / "data" / "hy3d_workflow_geometry_api.json"   # geometry-only variant
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


def _example_ui():
    """The Hunyuan3D wrapper's bundled UI example workflow (dict), or None if not installed."""
    try:
        import comfy_manager as cm
        exdir = cm.COMFY_DIR / "custom_nodes" / "ComfyUI-Hunyuan3DWrapper" / "example_workflows"
        example = next((exdir / n for n in ("hy3d_example_01.json", "hy3d_example_1.json")
                        if (exdir / n).is_file()), None)
        return json.loads(example.read_text(encoding="utf-8")) if example else None
    except Exception as e:
        print(f"[image3d] example workflow unavailable ({e})")
        return None


def _autobuild_workflow(client, object_info=None):
    """Build the textured workflow ourselves — no manual ComfyUI step. Read the wrapper's bundled
    UI example and convert it to a pruned API prompt using ComfyUI's live /object_info."""
    from ._hy3d import build_textured_prompt
    ui = _example_ui()
    if ui is None:
        return None
    try:
        graph, exp = build_textured_prompt(ui, object_info or client.get_object_info())
        ctypes = {nd.get("class_type") for nd in (graph or {}).values()}
        if exp is None or not ({"Hy3DGenerateMesh", "Hy3DExportMesh"} <= ctypes):
            return None
        _cache(graph)
        return graph
    except Exception as e:
        print(f"[image3d] auto-build skipped ({e})")
        return None


def _build_geometry_workflow(client, object_info=None):
    """Geometry-only API graph (exports the mesh, NO texture bake → no custom_rasterizer needed).
    Cached separately from the textured graph. Used when texturing is off/unavailable."""
    if _UNTEX_CACHE.is_file():
        try:
            g = json.loads(_UNTEX_CACHE.read_text(encoding="utf-8"))
            if _graph_valid(g, object_info):
                return g
        except Exception:
            pass
    from ._hy3d import build_untextured_prompt
    ui = _example_ui()
    if ui is None:
        return None
    try:
        graph, exp = build_untextured_prompt(ui, object_info or client.get_object_info())
        ctypes = {nd.get("class_type") for nd in (graph or {}).values()}
        if exp is None or not ({"Hy3DGenerateMesh", "Hy3DExportMesh"} <= ctypes):
            return None
        try:
            _UNTEX_CACHE.parent.mkdir(parents=True, exist_ok=True)
            _UNTEX_CACHE.write_text(json.dumps(graph), encoding="utf-8")
        except Exception:
            pass
        return graph
    except Exception as e:
        print(f"[image3d] geometry-only build skipped ({e})")
        return None


def _rasterizer_available():
    """True if the custom_rasterizer CUDA module (texture bake) is importable in the shared venv.
    Checked without importing it (no CUDA init). When absent, we skip the doomed textured attempt
    and go straight to geometry — no wasted shape-generation pass."""
    try:
        import importlib.util
        return importlib.util.find_spec("custom_rasterizer") is not None
    except Exception:
        return False


def _is_texture_error(err):
    """A failure in the TEXTURE branch (so geometry-only would still succeed) vs a shape failure."""
    s = str(err).lower()
    return any(k in s for k in ("custom_rasterizer", "rendermultiview", "applytexture",
                                "bakefrommultiview", "texgen", "differentiable_renderer"))


def _texture_unavailable_hint():
    try:
        import comfy_manager
        whl = comfy_manager.RASTERIZER_WHEEL
    except Exception:
        whl = "the custom_rasterizer wheel"
    return ("Textured mode needs the 'custom_rasterizer' CUDA module, and it isn't available on "
            "this machine (the auto-install of the prebuilt wheel didn't take — usually a CUDA "
            "build mismatch, or ComfyUI needs a restart to pick it up).\n\n"
            "Use Texture = 'Geometry only' or 'Auto' for a fully-usable untextured mesh — for "
            "CNC / relief you don't need the texture.\n\n"
            "To enable texturing, on the box run:\n"
            f"  .venv\\Scripts\\python.exe -m pip install \"{whl}\"\n"
            "then restart ComfyUI and try again.")


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


def _combo_specs(object_info, class_type):
    """The node's {input_name: spec} for required + optional inputs (or {} if unknown)."""
    info = (object_info or {}).get(class_type)
    if not isinstance(info, dict):
        return {}
    spec_in = info.get("input") if isinstance(info.get("input"), dict) else {}
    return {**(spec_in.get("required") or {}), **(spec_in.get("optional") or {})}


def _graph_valid(graph, object_info):
    """False if any combo (list-typed) widget value is no longer allowed by the node's current
    schema — e.g. a cache built before the Hy3D sampler dropped the 'fixed' scheduler option (or
    one with widgets shifted by a leaked control_after_generate value). Triggers a clean rebuild."""
    if not object_info:
        return True                                       # can't check → assume ok
    for nd in graph.values():
        if not isinstance(nd, dict):
            continue
        specs = _combo_specs(object_info, nd.get("class_type"))
        for name, val in (nd.get("inputs") or {}).items():
            if isinstance(val, list):                     # a link [node, slot], not a widget value
                continue
            spec = specs.get(name)
            if isinstance(spec, (list, tuple)) and spec and isinstance(spec[0], list) and val not in spec[0]:
                return False
    return True


def _repair_combos(graph, object_info):
    """Clamp any combo widget whose value isn't in the node's allowed options to the node's
    default (or first option). A self-healing net for example/cache enum drift (the dropped
    scheduler option), so a single removed value can't fail the whole prompt."""
    if not object_info:
        return graph
    for nd in graph.values():
        if not isinstance(nd, dict):
            continue
        specs = _combo_specs(object_info, nd.get("class_type"))
        for name, val in list((nd.get("inputs") or {}).items()):
            if isinstance(val, list):
                continue
            spec = specs.get(name)
            if not (isinstance(spec, (list, tuple)) and spec and isinstance(spec[0], list)):
                continue
            options = spec[0]
            if options and val not in options:
                opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                default = opts.get("default", options[0])
                nd["inputs"][name] = default if default in options else options[0]
                print(f"[image3d] repaired {nd.get('class_type')}.{name}: {val!r} → {nd['inputs'][name]!r}")
    return graph


def _repair_numbers(graph, object_info):
    """Reset any INT/FLOAT widget whose value falls outside the node's schema [min,max] back to
    the node default — the numeric twin of _repair_combos. Guards against a misaligned widget
    (e.g. a 512 resolution landing in cfg_image, which maxes at 100) failing the whole prompt
    with 'value_bigger_than_max', and against a node lowering a bound after the cache was built."""
    if not object_info:
        return graph
    for nd in graph.values():
        if not isinstance(nd, dict):
            continue
        specs = _combo_specs(object_info, nd.get("class_type"))
        for name, val in list((nd.get("inputs") or {}).items()):
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                continue                                   # skip links, bools, strings
            spec = specs.get(name)
            if not (isinstance(spec, (list, tuple)) and spec and spec[0] in ("INT", "FLOAT")):
                continue
            opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
            lo, hi = opts.get("min"), opts.get("max")
            if (lo is not None and val < lo) or (hi is not None and val > hi):
                default = opts.get("default", lo if lo is not None else 0)
                nd["inputs"][name] = default
                print(f"[image3d] repaired {nd.get('class_type')}.{name}: {val!r} → {default!r} "
                      f"(outside [{lo}, {hi}])")
    return graph


class ImageTo3DFeature(Feature):
    id = "image3d"
    name = "Image → 3D"
    description = ("Photo → 3D model (Hunyuan3D shape). Exports a GLB plus OBJ / STL / PLY and an "
                  "interactive 3D preview. Adds PBR texture when the custom_rasterizer module is "
                  "installed, otherwise returns clean geometry.")
    needs_comfy = True
    inputs = ["image"]
    engine = "comfy"
    icon = "cube"
    est_runtime = "~2–8 min"
    vram = "~8–12 GB"
    output_kinds = ["GLB", "3D preview", "OBJ", "STL", "PLY"]
    guide = [
        {"h": "What it does",
         "b": "Generates a full 3D model from a single photo (Hunyuan3D). The shape always works; "
              "PBR texturing is an extra step that needs the custom_rasterizer CUDA module."},
        {"h": "Texture modes",
         "b": "Auto (recommended): textures if the custom_rasterizer module is present, else "
              "returns clean geometry — no wasted run. Textured: force the bake — auto-installs the "
              "prebuilt custom_rasterizer wheel the first time (restart ComfyUI if it doesn't load). "
              "Geometry only: skip texturing for a faster, untextured mesh."},
        {"h": "Geometry vs texture",
         "b": "For CNC relief / 3D-printing you usually only need the GEOMETRY — an untextured mesh "
              "is fully usable (it just previews gray). Texturing adds surface color/PBR maps, which "
              "matter for rendering, not for carving."},
    ]
    params = [
        ParamSpec("texture", "select", "auto", "Texture", control="seg",
                  help="Auto = texture if custom_rasterizer is available, else clean geometry. "
                       "Textured = force the bake. Geometry only = skip texturing (faster).",
                  choices=[{"value": "auto", "label": "Auto"},
                           {"value": "on", "label": "Textured"},
                           {"value": "off", "label": "Geometry only"}]),
        ParamSpec("seed", "number", 0, "Seed (0 = random)", 0, 2_147_483_647, 1, control="stepper",
                  help="Patched into the workflow's shape-generation node. 0 = a fresh random seed each run."),
        ParamSpec("formats", "select", "all", "Extra exports", control="seg", group="advanced",
                  help="The GLB is always produced; also re-export these geometry formats.",
                  choices=[{"value": "all", "label": "OBJ+STL+PLY"}, {"value": "obj", "label": "OBJ"},
                           {"value": "stl", "label": "STL"}, {"value": "none", "label": "GLB only"}]),
    ]

    def run(self, inputs, params, out_dir):
        out = Path(out_dir)
        client = ComfyUIClient()
        try:
            oi = client.get_object_info()
        except Exception:
            oi = None

        # upload the photo once — reused by the textured attempt and the geometry fallback.
        src = Image.open(inputs["image"]).convert("RGB")
        tmp = out / "img3d_input.png"; src.save(tmp)
        name = client.upload_image(str(tmp))
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)

        def _prep(graph):
            """Deep-copy, heal enum/number drift, point LoadImage at our photo, patch the seed."""
            g = json.loads(json.dumps(graph))             # never mutate the template/cache
            _repair_combos(g, oi); _repair_numbers(g, oi)
            load_nodes = _nodes_of(g, "LoadImage")
            if not load_nodes:
                raise RuntimeError("The workflow has no LoadImage node to feed the photo into — "
                                   "re-export an API-format workflow whose input is a LoadImage node.")
            for nid in load_nodes:
                g[nid].setdefault("inputs", {})["image"] = name
            for nid in _nodes_of(g, "Hy3DGenerateMesh"):
                if "seed" in g[nid].get("inputs", {}):
                    g[nid]["inputs"]["seed"] = seed
            return g

        def _load_textured():
            # cached/override file → build from the wrapper example → recover from /history. A stale
            # cache (an option the node dropped, or shifted widgets) is rebuilt cleanly.
            graph, _src = _load_workflow()
            if graph is not None and not _graph_valid(graph, oi):
                print("[image3d] cached workflow uses an option the node no longer accepts — rebuilding")
                graph = None
            return graph or _autobuild_workflow(client, oi) or _learn_workflow_from_history(client)

        def _run_geometry():
            g = _build_geometry_workflow(client, oi)
            if g is None:
                raise RuntimeError("Couldn't build a geometry-only workflow.\n" + _SETUP_HINT)
            glb = client.generate_file(_prep(g), exts=(".glb",), label="image3d·geometry", max_wait=1800)
            return glb, False

        # texture only if asked AND the custom_rasterizer CUDA module is actually present — so on a
        # box without it Auto goes straight to geometry (no wasted shape-generation pass). When the
        # user explicitly forces 'Textured', try to auto-provision the prebuilt wheel first.
        mode = params.get("texture", "auto")
        if mode == "on" and not _rasterizer_available():
            try:
                import comfy_manager
                print("[image3d] custom_rasterizer missing — installing the prebuilt wheel …")
                comfy_manager.install_rasterizer()
            except Exception as e:
                print(f"[image3d] custom_rasterizer auto-install failed: {e}")
        want_texture = mode == "on" or (mode == "auto" and _rasterizer_available())

        if not want_texture:
            if mode == "on":                              # forced texture but it couldn't be provisioned
                raise RuntimeError(_texture_unavailable_hint())
            glb, textured = _run_geometry()
        else:
            graph = _load_textured()
            if graph is None:
                raise RuntimeError(_SETUP_HINT)
            try:
                glb = client.generate_file(_prep(graph), exts=(".glb",), prefer="textured",
                                           label="image3d·textured", max_wait=1800)
                textured = True
            except ComfyUIError as e:
                if not _is_texture_error(e):
                    raise
                if mode == "auto":                        # graceful: untextured mesh instead
                    print(f"[image3d] texture bake unavailable ({e}); exporting geometry only")
                    glb, textured = _run_geometry()
                else:                                     # forced: clear, actionable message
                    raise RuntimeError(_texture_unavailable_hint() + f"\n\n(engine said: {e})")

        print(f"[image3d] produced {'textured' if textured else 'geometry-only'} mesh")
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
