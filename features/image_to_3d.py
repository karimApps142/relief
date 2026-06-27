"""features/image_to_3d.py — Image → 3D → CNC bas-relief (the image-upload front-half).

Upload a PHOTO → reconstruct a 3D mesh (Hunyuan3D-2.0 via ComfyUI's NATIVE nodes — shape
only, so no custom_rasterizer compile) → clean/canonicalise the mesh → orthographic-project
the front view to a 16-bit heightmap (relief_core.mesh_to_heightmap) → relief STL + 3D
preview. This is roadmap item #3 in docs/RELIEF_QUALITY_RESEARCH.md: the mesh recovers TRUE
z-order (nose/ear overhang, profiles) that monocular depth fundamentally cannot.

Generated meshes are SMOOTH and lose high-frequency detail (hair, lashes, lips), so the mesh
is treated as the global FORM only — the crisp facial detail is RE-FUSED from the ORIGINAL
photo's surface-normal map (reusing relief_core.fuse_depth_normals via tiled_relief_heightmap).
Mesh = form, photo = detail.

Cross-engine, sequenced within ~12 GB like portrait_relief: ComfyUI generates the mesh, its
VRAM is freed (client.free), then the local normal model loads. Needs ComfyUI running + the
Hunyuan3D checkpoint (comfy_manager.HUNYUAN3D_MODELS provisions it; native nodes need NO custom
node). The mesh→heightmap→STL back-half is shared with the Mesh → Relief feature.
"""
import random
from pathlib import Path
import numpy as np
from PIL import Image

from .base import Feature, ParamSpec
from ._comfy import ComfyUIClient

# ComfyUI native Hunyuan3D 2.0 checkpoint name (loaded by ImageOnlyCheckpointLoader from
# models/checkpoints/; provisioned by comfy_manager.HUNYUAN3D_MODELS).
_CKPT = "hunyuan3d-dit-v2-0-fp16.safetensors"


def _build_graph(image_name, octree, steps, seed, cfg=5.5):
    """Native ComfyUI Hunyuan3D 2.0 image→mesh graph (shape only → GLB), matching the
    official tutorial (docs.comfy.org/tutorials/3d/hunyuan3D-2):
      ImageOnlyCheckpointLoader → CLIPVisionEncode → Hunyuan3Dv2Conditioning → KSampler
      → VAEDecodeHunyuan3D (voxel) → VoxelToMesh (surface net) → SaveGLB.
    octree_resolution is the main geometry-detail knob; SaveGLB writes to output/hy3d/.
    (VoxelToMesh 'surface net' gives smoother meshes than the deprecated VoxelToMeshBasic.)"""
    return {
        "1": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": _CKPT}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "CLIPVisionEncode",
              "inputs": {"clip_vision": ["1", 1], "image": ["2", 0], "crop": "center"}},
        "4": {"class_type": "Hunyuan3Dv2Conditioning", "inputs": {"clip_vision_output": ["3", 0]}},
        "5": {"class_type": "EmptyLatentHunyuan3Dv2", "inputs": {"resolution": 3072, "batch_size": 1}},
        "6": {"class_type": "KSampler", "inputs": {
            "seed": int(seed), "steps": int(steps), "cfg": float(cfg),
            "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
            "model": ["1", 0], "positive": ["4", 0], "negative": ["4", 1], "latent_image": ["5", 0]}},
        "7": {"class_type": "VAEDecodeHunyuan3D", "inputs": {
            "samples": ["6", 0], "vae": ["1", 2], "num_chunks": 8000, "octree_resolution": int(octree)}},
        "8": {"class_type": "VoxelToMesh", "inputs": {
            "voxel": ["7", 0], "algorithm": "surface net", "threshold": 0.6}},
        "9": {"class_type": "SaveGLB", "inputs": {"mesh": ["8", 0], "filename_prefix": "hy3d/relief"}},
    }


class ImageTo3DReliefFeature(Feature):
    id = "image3d"
    name = "Image → Relief (3D)"
    description = ("Photo → AI 3D reconstruction (Hunyuan3D) → orthographic relief heightmap + STL. "
                  "Recovers true z-order (nose/ear overhang); re-fuses the photo's normal detail.")
    needs_comfy = True
    inputs = ["image"]
    engine = "comfy"
    icon = "box"
    est_runtime = "~1–5 min"
    vram = "~6–10 GB"
    output_kinds = ["Heightmap PNG", "3D preview GLB", "STL mesh", "Source mesh GLB"]
    params = [
        ParamSpec("octree_resolution", "select", "256", "Mesh detail", control="seg",
                  help="Hunyuan3D octree resolution — higher = finer geometry + slower.",
                  choices=[{"value": "128", "label": "Fast · 128"}, {"value": "256", "label": "Standard · 256"},
                           {"value": "384", "label": "Fine · 384"}]),
        ParamSpec("steps", "number", 30, "Diffusion steps", 10, 60, 1, control="slider"),
        ParamSpec("view", "select", "front", "View", control="seg",
                  help="Which side faces the carve. Use this to fix orientation if the mesh comes out turned.",
                  choices=[{"value": "front", "label": "Front"}, {"value": "back", "label": "Back"},
                           {"value": "left", "label": "Left"}, {"value": "right", "label": "Right"}]),
        ParamSpec("resolution", "number", 1024, "Heightmap resolution", 256, 2048, 64, control="slider", suffix=" px",
                  help="Heightmap pixels along the longest side. Higher = finer + slower render."),
        ParamSpec("relief_depth_mm", "number", 8.0, "Relief depth", 2, 20, 0.5, control="slider", suffix=" mm"),
        ParamSpec("pixel_mm", "number", 0.1, "Pixel size", 0.02, 0.5, 0.01, control="slider", suffix=" mm/px"),
        ParamSpec("normal_fusion", "bool", True, "Re-fuse photo detail",
                  help="Add the original photo's surface-normal detail (eyes/hair/lips) onto the smooth mesh "
                       "form — the mesh is the shape, the photo is the fine detail. Best on centred frontal "
                       "portraits (the photo normals are aligned to the render grid)."),
        ParamSpec("normal_source", "select", "sapiens", "Detail source", control="seg",
                  depends_on={"param": "normal_fusion", "value": True},
                  help="Sapiens = human-specialist (sharpest faces); Marigold = general fallback.",
                  choices=[{"value": "sapiens", "label": "Sapiens"}, {"value": "marigold", "label": "Marigold"}]),
        ParamSpec("normal_gain", "number", 0.6, "Detail strength", 0.0, 1.5, 0.05, control="slider",
                  depends_on={"param": "normal_fusion", "value": True},
                  help="How strongly the photo-derived detail stands out on the mesh form."),
        ParamSpec("decimate_faces", "number", 200000, "Decimate to", 20000, 1000000, 10000, control="slider",
                  suffix=" tris", group="advanced",
                  help="Cap the mesh triangle count before the (pure-python) projection. Lower = faster."),
        ParamSpec("seed", "number", 0, "Seed (0 = random)", 0, 2_147_483_647, 1, control="stepper", group="advanced"),
        ParamSpec("invert", "bool", False, "Invert depth", group="advanced"),
        ParamSpec("black_bg", "bool", True, "Black background", group="advanced"),
        ParamSpec("make_solid", "bool", False, "Make solid", group="advanced"),
    ]

    def run(self, inputs, params, out_dir):
        import cv2
        import trimesh
        import relief_core as rc
        out = Path(out_dir)
        client = ComfyUIClient()

        # 1. upload the photo (bound the upload; CLIP-vision resizes internally anyway).
        src = Image.open(inputs["image"]).convert("RGB")
        m = max(src.size)
        if m > 1024:
            s = 1024 / m
            src = src.resize((max(8, int(src.width * s)), max(8, int(src.height * s))))
        tmp = out / "img3d_input.png"; src.save(tmp)
        name = client.upload_image(str(tmp))

        # 2. ComfyUI native Hunyuan3D 2.0 → GLB (shape only).
        seed = int(params.get("seed") or 0) or random.randint(1, 2_147_483_647)
        graph = _build_graph(name, params.get("octree_resolution", "256"),
                             params.get("steps", 30), seed)
        glb = client.generate_file(graph, exts=(".glb",), label="image3d·reconstruct", max_wait=1200)
        raw = out / "mesh_raw.glb"; raw.write_bytes(glb)

        # 3. free ComfyUI VRAM before the local normal model loads (12 GB budget).
        client.free()

        # 4. load + clean/canonicalise the generated mesh (CPU only).
        mesh = trimesh.load(str(raw), force="mesh")
        if mesh is None or not hasattr(mesh, "vertices") or len(mesh.vertices) == 0:
            raise RuntimeError("Hunyuan3D produced no usable mesh (check ComfyUI log / the Hunyuan3D checkpoint).")
        mesh = rc.clean_generated_mesh(mesh, target_faces=int(params.get("decimate_faces", 200000)))

        # 5. orthographic render → height field + mask (captures true z-order).
        depth, mask = rc.mesh_to_heightmap(mesh, view=params.get("view", "front"),
                                           resolution=int(params["resolution"]))

        # 6. optional: re-fuse the PHOTO's normal detail onto the mesh FORM (the hybrid).
        #    Resized to the render grid — aligns well on centred frontal portraits.
        normal_map = None
        if params.get("normal_fusion", True):
            try:
                from backends import get_backend
                be = get_backend("auto")
                nm = np.clip(np.asarray(be.estimate_normals(
                    src, which=params.get("normal_source", "sapiens")), np.float32), 0.0, 1.0)
                normal_map = cv2.resize(nm, (depth.shape[1], depth.shape[0]))
            except Exception as e:                        # graceful: mesh-form-only if normals unavailable
                print(f"[image3d] normal fusion skipped ({e}) — mesh form only")

        # 7. seat on the relief plate (reuse the relief math + depth+normal fusion).
        height = rc.tiled_relief_heightmap(
            depth, mask, invert=bool(params.get("invert")), base=0.5, fig_span=0.45,
            bg=(0.0 if params.get("black_bg", True) else None),
            normal_map=normal_map, normal_detail=float(params.get("normal_gain", 0.6)))
        height16 = rc.to_heightmap_16bit(height, normalize=False)
        png = out / "relief_heightmap.png"; cv2.imwrite(str(png), height16)

        # 8. STL + interactive preview (same back-half as Mesh → Relief).
        if params.get("make_solid"):
            relief = rc.heightmap_to_solid(height16, params["relief_depth_mm"], params["pixel_mm"])
        else:
            relief = rc.heightmap_to_surface(height16, params["relief_depth_mm"], params["pixel_mm"])
        stl = out / "relief.stl"; relief.export(str(stl))
        prev = out / "preview.glb"
        rc.heightmap_to_preview(height16, params["relief_depth_mm"], params["pixel_mm"]).export(str(prev))

        return {"mesh3d": str(raw), "heightmap": str(png), "stl": str(stl), "preview3d": str(prev)}
