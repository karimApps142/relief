# Relief quality + new-tools research (verified)

Research workflow: 5 angles + an adversarial verification pass, ~30 sources. Summary of
what's confirmed and the roadmap. The user's hypothesis was: *don't feed the raw photo to
the depth model — transform it into a clean "sculptural" intermediate first.*

## Verdict: the hypothesis is correct — with one refinement

- **Why raw photos fail:** a brightness/depth model reads *lighting* as *geometry* — a nose
  shadow carves a dent, pupils become pits, a glint becomes a spike, grain becomes roughness.
  Well-documented across CNC/relief communities.
- **The active ingredient is NOT a prettier RGB image** (a stylized photo with new baked
  lighting reintroduces the same false-geometry problem). It's **recovering clean surface
  geometry**, specifically bridging through a **normal map**.
- **Normals carry the high-frequency facial detail** (eyes, hair, lips, pores); **depth
  carries the low-frequency form** (face planes, nose projection). The highest-quality relief
  **fuses** them: Poisson-integrate the normals → keep depth's global shape + normals' crisp
  detail. This is the textbook bas-relief recipe (Weyrich SIGGRAPH 2007; Ji 2014) and what
  MonoRelief V2, Hi3DGen, and Carveco AI all do.

### Honest caveat (the one unproven link)
No published head-to-head proves **delight-before-depth** improves the *same* depth model.
The proven parts are the **normal bridge** and the **lighting-as-false-geometry** failure mode.
So the delight/stylize branch should be **A/B tested on our own portraits** before committing.

## What's confirmed (high confidence)
- Depth-Anything-V2 **smooths** the boundaries portraits need; **Depth-Pro** (sharp hair-strand
  edges) and **Sapiens/Sapiens2** (human-specialist; outputs normals + pointmap + albedo) are
  better for faces. Sapiens2 (ICLR 2026) dropped the depth head → use its normals + pointmap.
- **Tiling** (PatchFusion / BoostingMonocularDepth) is the right high-res tool — we already do it.
- **BiRefNet matte** first (we do this) so the background isn't false depth.
- The **mesh → orthographic heightmap** path is the real professional workflow (ZBrush "Bas
  Relief" → Vectric/Carveco). **Hunyuan3D-2.1 shape-only (~10 GB)** and **Hunyuan3D-2mv**
  (multiview, 1.1 B) fit a 12 GB 3060; **TRELLIS.2** (512³) is a single-image runner-up.
  Full *textured* Hunyuan needs 21–29 GB — but relief only needs geometry, so shape-only is fine.
- **FaceLift** (dedicated head model) needs ~80 GB — NOT 3060-runnable as shipped.

## ✅ Portrait Relief — the one-click pipeline (`features/portrait_relief.py`)
The research's recommended flow, automated into one feature: **delight (IC-Light 'even')
→ optional upscale → local depth + Sapiens-normal-fusion relief**. Cross-engine (ComfyUI
for delight/upscale, local for relief); ComfyUI VRAM is freed before the local models load.
The `delight` toggle doubles as the A/B harness (on vs off). Needs the relight assets, NOT
the 11.7 GB Krea models — so a relief-only user provisions just ~3.7 GB + the IC-Light node.

## Roadmap (by value × feasibility on a 12 GB 3060)
1. **Normal-fusion relief** — ✅ **IMPLEMENTED**. Estimate a normal map, Poisson-integrate, fuse
   its high-frequency detail onto the Depth-Anything base. Relief Advanced params: `normal_detail`
   toggle + `normal_gain` + **`normal_source`** (**Sapiens** = human-specialist, default + sharpest
   faces/hair, via `facebook/sapiens-normal-1b-torchscript`; **Marigold** = general fallback).
   (`relief_core.integrate_normals` / `fuse_depth_normals`; round-trip verified corr 0.9946.)
2. **Delight / Relight (IC-Light)** — ✅ **IMPLEMENTED** as a standalone **Relight** feature
   (`features/relight.py`, ComfyUI/IC-Light FC). The **Even** preset delights (flat, shadow-free) —
   feed its output back into Relief to A/B raw-vs-delit. Box setup: `comfy_manager` install clones
   `kijai/ComfyUI-IC-Light`; download adds `iclight_sd15_fc.safetensors` + an SD1.5 checkpoint
   (NOT in the engine gate, so it never blocks text2img/img2img/upscale). **Existing engine
   installs** add it once on the box: `git clone https://github.com/kijai/ComfyUI-IC-Light
   F:\ComfyUI\custom_nodes\ComfyUI-IC-Light`, then `curl -X POST http://127.0.0.1:8000/api/comfy/download`
   (re-runs download, skips present Krea, grabs the 2 relight files), then restart ComfyUI so the node loads.
3. **Image → 3D (Hunyuan3D-2mv, shape-only)** — full 3D busts → orthographic heightmap; biggest
   new capability, recovers true z-order (ears, nose overhang).
4. Quick wins: background removal (expose BiRefNet), face restoration (GFPGAN/CodeFormer),
   standalone depth/normal map export, ControlNet (keep identity when stylizing).

## Key sources
- Bas-relief from normals (gradient-domain): Weyrich 2007; Ji 2014 (orca.cardiff.ac.uk/id/eprint/58823)
- MonoRelief V2 — https://github.com/glp1001/MonoreliefV2 · https://arxiv.org/abs/2508.19555
- Hi3DGen (normal-bridge image→3D) — https://github.com/bytedance/Hi3DGen
- Sapiens2 (ICLR 2026) — https://arxiv.org/abs/2604.21681
- Hunyuan3D-2mv — https://huggingface.co/tencent/Hunyuan3D-2mv
- Depth-Pro — https://learnopencv.com/depth-pro-monocular-metric-depth/
- Carveco AI Image-to-Relief — https://carveco.com/ai/
- Why raw photos fail as heightmaps — http://danceswithferrets.org/geekblog/?p=1053/
