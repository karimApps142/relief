"""features/mesh_relief.py — turn a 3D model into a CNC bas-relief (orthographic project).

Upload an OBJ/STL/GLB/PLY (from ZBrush/Blender/a scan, or — later — the Image→3D tool) →
project the chosen view to a 16-bit heightmap → relief STL. Captures true z-order
(ears/nose/profiles) that monocular depth can't. This is the 'project a 3D model to a
heightmap' workflow that ZBrush 'Bas Relief' / Carveco / Aspire use. Local, CPU-only.
"""
from pathlib import Path
import cv2

from .base import Feature, ParamSpec
import relief_core as rc


class MeshReliefFeature(Feature):
    id = "mesh_relief"
    name = "Mesh → Relief"
    description = "Project a 3D model (OBJ/STL/GLB/PLY) to a carve-ready relief heightmap + STL."
    inputs = ["mesh"]
    engine = "local"
    icon = "box"
    est_runtime = "~5–60 s"
    vram = "CPU only"
    output_kinds = ["Heightmap PNG", "3D preview GLB", "STL mesh"]
    params = [
        ParamSpec("view", "select", "front", "View", control="seg",
                  help="Which side faces the carve. Front works for most busts.",
                  choices=[{"value": "front", "label": "Front"}, {"value": "back", "label": "Back"},
                           {"value": "left", "label": "Left"}, {"value": "right", "label": "Right"},
                           {"value": "top", "label": "Top"}]),
        ParamSpec("resolution", "number", 1024, "Resolution", 256, 2048, 64, control="slider", suffix=" px",
                  help="Heightmap pixels along the longest side. Higher = finer + slower."),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth", 2, 20, 0.5, control="slider", suffix=" mm"),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size", 0.02, 0.5, 0.01, control="slider", suffix=" mm/px"),
        ParamSpec("invert", "bool", False, "Invert depth", group="advanced"),
        ParamSpec("black_bg", "bool", True, "Black background", group="advanced"),
        ParamSpec("make_solid", "bool", False, "Make solid", group="advanced"),
    ]

    def run(self, inputs, params, out_dir):
        import trimesh
        out = Path(out_dir)
        mesh_path = inputs.get("image")           # server stores the uploaded file under "image"
        loaded = trimesh.load(mesh_path, force="mesh")
        if loaded is None or not hasattr(loaded, "vertices") or len(loaded.vertices) == 0:
            raise RuntimeError("Could not read a mesh from that file (OBJ/STL/GLB/PLY supported).")

        depth, mask = rc.mesh_to_heightmap(loaded, view=params.get("view", "front"),
                                           resolution=int(params["resolution"]))
        height = rc.tiled_relief_heightmap(depth, mask, invert=bool(params.get("invert")),
                                           base=0.5, fig_span=0.45,
                                           bg=(0.0 if params.get("black_bg", True) else None))
        height16 = rc.to_heightmap_16bit(height, normalize=False)
        png = out / "relief_heightmap.png"; cv2.imwrite(str(png), height16)

        if params.get("make_solid"):
            mesh = rc.heightmap_to_solid(height16, params["relief_depth_mm"], params["pixel_mm"])
        else:
            mesh = rc.heightmap_to_surface(height16, params["relief_depth_mm"], params["pixel_mm"])
        stl = out / "relief.stl"; mesh.export(str(stl))
        prev = out / "preview.glb"
        rc.heightmap_to_preview(height16, params["relief_depth_mm"], params["pixel_mm"]).export(str(prev))
        return {"heightmap": str(png), "stl": str(stl), "preview3d": str(prev)}
