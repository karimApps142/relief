# Appendix — ComfyUI Phase-0 quality prototype (OPTIONAL pre-work)

**Goal:** before committing to building the service, **eyeball the relief quality** on real images
by wiring the pipeline in ComfyUI. This is throwaway exploration — its only job is to confirm the
relief looks *carved* and to find good default knobs, so you start Parts 00–07 with confidence.

**Runs on:** 🪟 Windows 11 (the GPU box — ComfyUI needs the GPU for the normal/depth nodes).

**Prerequisites:** none in this repo — independent of Parts 00–10. Best done **first** (Phase 0)
or whenever you want to sanity-check quality outside the service.

**Files:** a ComfyUI graph + one small custom Python node. Nothing here ships in the `relief/`
repo.

---

## The big idea (plan §8, Phase 0)

Wire the pipeline in **ComfyUI** to see output on real images before building any service. You get
the visual feedback loop for free, and you only need to write **one** custom node — the
bas-relief compression — because everything else already exists as community nodes.

---

## Useful nodes

| Need | ComfyUI node |
|------|--------------|
| depth + normal estimation | `ComfyUI-LBM` (`1038lab/ComfyUI-LBM`) |
| object normals/depth | `ComfyUI-Geowizard` |
| derive normals from depth | `DepthToNormalMap` |
| heightmap → STL (for CNC) | `ComfyUI-Depth2Mesh` (`timothywong731/ComfyUI-Depth2Mesh`) |
| **bas-relief compression** | **one custom node you write** (wraps `bas_relief_compress`) |

---

## The one custom node (wraps the Part 01 math)

The only algorithm node you write — reuse `bas_relief_compress` from `relief_core.py` (Part 01 /
plan §5.1):

```python
# minimal ComfyUI node sketch: height image in -> compressed height out
import numpy as np
from relief_core import bas_relief_compress   # reuse Part 01

class BasReliefCompress:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "height": ("IMAGE",),
            "beta": ("FLOAT", {"default": 0.55, "min": 0.1, "max": 1.0, "step": 0.05}),
            "detail_boost": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 3.0, "step": 0.1}),
        }}
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "run"
    CATEGORY = "relief"

    def run(self, height, beta, detail_boost):
        h = height[0, ..., 0].cpu().numpy().astype(np.float64)   # single-channel height
        out = bas_relief_compress(h, beta=beta, detail_boost=detail_boost)
        out = (out - out.min()) / (out.max() - out.min() + 1e-8)
        import torch
        return (torch.from_numpy(out).float()[None, ..., None].repeat(1, 1, 1, 3),)
```

> Treat this as a sketch — adapt tensor shapes to your ComfyUI version's IMAGE convention. The
> point is to drop your **secret-sauce** stage into the graph, not to productionize it.

---

## Suggested graph

```
load image
  └─> LBM / Geowizard ............ normal map (+ optional depth)
  └─> (normal -> height) ......... integrate (or DepthToNormalMap path)
  └─> BasReliefCompress .......... your custom node  ← the part that makes it look carved
  └─> Depth2Mesh ................. heightmap -> STL preview
```

---

## Steps

1. Install ComfyUI on the Windows box + the nodes above.
2. Add the custom `BasReliefCompress` node (point it at your `relief_core.py`).
3. Build the graph, run it on **real images** (portraits, animals, ornaments).
4. Sweep `beta` / `detail_boost` and watch when the relief starts looking genuinely carved.
5. Record the knob ranges that work — those become your starting defaults in Part 07.

---

## Verify

- The graph runs end-to-end on a real image and previews a relief mesh.
- Sweeping `beta` visibly changes how "tall" vs flat the relief is; `detail_boost` changes
  crispness.
- You can point to specific knob values that produce a convincingly carved result.

## Done when

- [ ] ComfyUI graph runs the normal → compress → mesh path on real images.
- [ ] The custom `bas_relief_compress` node works in-graph.
- [ ] You've found and noted good default `beta` / `detail_boost` ranges to seed Part 07.

## Source

Plan §8 (Build Roadmap — Phase 0 prototype) and §12 (node/repo references).
