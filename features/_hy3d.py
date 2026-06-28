"""features/_hy3d.py — convert a ComfyUI UI-format workflow into a runnable API prompt.

ComfyUI's /prompt wants the API format ({node_id: {class_type, inputs}}), but custom nodes ship
UI-format example workflows ({nodes:[...], links:[...]}). The frontend converts one to the other
using each node's input schema (/object_info). This reimplements that conversion headlessly so we
can run the kijai Hunyuan3D wrapper's example with no manual "Save (API Format)" step:

  • resolve Reroute passthrough and inline PrimitiveNode values,
  • map positional widgets_values → named widget inputs in /object_info order,
  • skip control_after_generate's extra control widget (seed nodes),
  • drop Note / preview / display nodes,
  • prune to only the nodes feeding the chosen export, so unused optional branches
    (e.g. an upscale loader needing a model we didn't fetch) can't fail prompt validation.
"""

_VIRTUAL = {"Reroute", "PrimitiveNode", "Note", "MarkdownNote"}
_DISPLAY = {"PreviewImage", "Preview3D", "Preview3DAnimation", "MaskPreview+", "MaskPreview",
            "PreviewAny", "SaveImage"}
_PRIMITIVE_TYPES = ("INT", "FLOAT", "STRING", "BOOLEAN")
# The frontend injects a `control_after_generate` combo right after a seed widget; its value is
# one of these. /object_info doesn't always flag it, so we also detect it by name + value.
_SEED_NAMES = {"seed", "noise_seed", "rand_seed"}
_CONTROL_VALUES = {"fixed", "randomize", "increment", "decrement"}


def _links_index(ui):
    # UI link rows: [link_id, from_node, from_slot, to_node, to_slot, type]
    return {l[0]: l for l in ui.get("links", []) if isinstance(l, (list, tuple)) and len(l) >= 4}


def convert_ui_to_api(ui, object_info):
    """UI workflow dict + /object_info → API prompt dict. Best-effort: nodes missing from
    object_info still get their linked inputs (widgets skipped)."""
    nodes = {n["id"]: n for n in ui.get("nodes", []) if isinstance(n, dict) and "id" in n}
    links = _links_index(ui)

    def resolve(node_id, slot):
        """Follow Reroute / PrimitiveNode to a real (str_id, slot) or ('__value__', literal)."""
        n = nodes.get(node_id)
        if n is None:
            return None
        t = n.get("type")
        if t == "Reroute":
            ins = n.get("inputs") or []
            lk = ins[0].get("link") if ins else None
            if lk not in links:
                return None
            l = links[lk]
            return resolve(l[1], l[2])
        if t == "PrimitiveNode":
            wv = n.get("widgets_values") or [None]
            return ("__value__", wv[0])
        return (str(node_id), slot)

    api = {}
    for nid, n in nodes.items():
        t = n.get("type")
        if t in _VIRTUAL or t in _DISPLAY:
            continue
        inputs, linked = {}, set()
        # 1. connection inputs (inline a PrimitiveNode's literal value)
        for inp in (n.get("inputs") or []):
            name, lk = inp.get("name"), inp.get("link")
            if name is None or lk not in links:
                continue
            res = resolve(links[lk][1], links[lk][2])
            if res is None:
                continue
            inputs[name] = res[1] if res[0] == "__value__" else [res[0], res[1]]
            linked.add(name)
        # 2. widget inputs, mapped from widgets_values via the node's schema order
        info = (object_info or {}).get(t)
        wv = n.get("widgets_values")
        if isinstance(wv, dict):                          # newer ComfyUI: name-keyed widgets
            for k, v in wv.items():
                if k not in linked:
                    inputs.setdefault(k, v)
        elif info:
            wv = wv or []
            spec_in = info.get("input", {}) if isinstance(info, dict) else {}
            ordered = list((spec_in.get("required") or {}).items()) + \
                      list((spec_in.get("optional") or {}).items())
            wi = 0
            for name, spec in ordered:
                if name in linked or wi >= len(wv):
                    continue
                typ = spec[0] if isinstance(spec, (list, tuple)) and spec else spec
                opts = spec[1] if isinstance(spec, (list, tuple)) and len(spec) > 1 \
                    and isinstance(spec[1], dict) else {}
                is_widget = (isinstance(typ, list) or typ in _PRIMITIVE_TYPES) and not opts.get("forceInput")
                if not is_widget:
                    continue
                inputs[name] = wv[wi]; wi += 1
                # Skip the frontend-injected control_after_generate combo that trails a seed
                # widget. /object_info usually DOESN'T flag it (the frontend adds it by widget
                # name), so also detect it by value — else 'fixed'/'randomize' leaks into the
                # next input (e.g. scheduler) and shifts every widget after it.
                if wi < len(wv) and (opts.get("control_after_generate")
                        or (name in _SEED_NAMES and isinstance(wv[wi], str)
                            and wv[wi] in _CONTROL_VALUES)):
                    wi += 1
        api[str(nid)] = {"class_type": t, "inputs": inputs}
    return api


def _feeds_from(api, nid, targets, seen=None):
    seen = seen or set()
    if nid in seen:
        return False
    seen.add(nid)
    if nid in targets:
        return True
    nd = api.get(nid)
    if not nd:
        return False
    for v in nd["inputs"].values():
        if isinstance(v, list) and len(v) == 2 and v[0] in api and _feeds_from(api, v[0], targets, seen):
            return True
    return False


def pick_textured_export(api):
    """The Hy3DExportMesh node that emits the TEXTURED mesh: the one fed (transitively) by
    Hy3DApplyTexture, else one whose path/prefix mentions 'textur', else the last export."""
    exports = [nid for nid, nd in api.items() if nd["class_type"] == "Hy3DExportMesh"]
    if not exports:
        return None
    applied = {nid for nid, nd in api.items() if nd["class_type"] == "Hy3DApplyTexture"}
    for nid in exports:
        if _feeds_from(api, nid, applied):
            return nid
    for nid in exports:
        for v in api[nid]["inputs"].values():
            if isinstance(v, str) and "textur" in v.lower():
                return nid
    return exports[-1]


def prune_to(api, keep_ids):
    """Keep only nodes reachable backward (via input links) from keep_ids, so unused optional
    branches can't trip ComfyUI's prompt validation."""
    keep, stack = set(), list(keep_ids)
    while stack:
        nid = stack.pop()
        if nid in keep or nid not in api:
            continue
        keep.add(nid)
        for v in api[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in api:
                stack.append(v[0])
    return {k: v for k, v in api.items() if k in keep}


def build_textured_prompt(ui, object_info):
    """UI workflow → pruned API prompt that produces the textured GLB. Returns (graph, export_id)."""
    api = convert_ui_to_api(ui, object_info)
    exp = pick_textured_export(api)
    if exp is None:
        return api, None
    return prune_to(api, [exp]), exp


def _mesh_producer(api):
    """The node emitting the bare generated mesh — what Hy3DApplyTexture would texture. Used to
    export geometry directly, skipping the texture bake (and its custom_rasterizer dependency)."""
    applied = [nid for nid, nd in api.items() if nd["class_type"] == "Hy3DApplyTexture"]
    if applied:
        for v in api[applied[0]]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and v[0] in api and "Mesh" in api[v[0]]["class_type"]:
                return v[0]
    for ct in ("Hy3DPostprocessMesh", "Hy3DGenerateMesh"):
        c = [nid for nid, nd in api.items() if nd["class_type"] == ct]
        if c:
            return c[-1]
    return None


def pick_untextured_export(api):
    """An Hy3DExportMesh NOT fed (transitively) by Hy3DApplyTexture — the geometry-only export."""
    exports = [nid for nid, nd in api.items() if nd["class_type"] == "Hy3DExportMesh"]
    applied = {nid for nid, nd in api.items() if nd["class_type"] == "Hy3DApplyTexture"}
    return next((nid for nid in exports if not _feeds_from(api, nid, applied)), None)


def build_untextured_prompt(ui, object_info):
    """UI workflow → pruned API prompt that exports GEOMETRY only — no texture bake, so it does
    NOT need the custom_rasterizer CUDA module. Uses the example's untextured export if it has one,
    else synthesizes an Hy3DExportMesh straight off the mesh producer. Returns (graph, export_id)."""
    api = convert_ui_to_api(ui, object_info)
    exp = pick_untextured_export(api)
    if exp is None:                                       # synthesize one off the mesh producer
        mesh_src = _mesh_producer(api)
        if mesh_src is None:
            return api, None
        tmpl = next((nd for nd in api.values() if nd["class_type"] == "Hy3DExportMesh"), None)
        inputs = dict(tmpl["inputs"]) if tmpl else {"file_format": "glb", "save_file": True}
        inputs["trimesh"] = [mesh_src, 0]                 # the wrapper's mesh slot is named 'trimesh'
        exp = str(max((int(k) for k in api if str(k).isdigit()), default=0) + 1)
        api[exp] = {"class_type": "Hy3DExportMesh", "inputs": inputs}
    g = prune_to(api, [exp])
    if exp in g:                                          # ensure it writes a fetchable .glb
        g[exp]["inputs"]["file_format"] = "glb"
        g[exp]["inputs"]["save_file"] = True
    return g, exp
