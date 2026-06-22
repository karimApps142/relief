# Part 10 — The moat: closing the quality gap (LATER / ongoing)

**Goal:** the work that takes output from "recognizably carved" to "Sculptok/idiaoke-exact
polish." None of this is a missing magic model — it's **data and tuning**. This part is a
research/roadmap track, not a single buildable file; acceptance is "documented, prioritized next
steps + measurable quality improvement," not "code merged."

**Runs on:** 🪟 Windows (training/inference) — research workflow.

**Prerequisites:** Parts 06–07 (the full pipeline producing real reliefs you can evaluate
against).

**Files:** training scripts / dataset tooling / CAM integration — created as you go.

---

## The big idea (plan §11, in payoff order)

A naive version of this pipeline produces a recognizable carved relief immediately. The distance
to *exact* polish comes from three things, **in order of payoff**:

1. **Fine-tuned normal estimation on relief data — the real moat.** Generic StableNormal is
   trained on indoor scenes; fine-tuned on busts/sculptures/ornaments it gets dramatically cleaner
   on your actual subjects. This is the single biggest quality jump and what the Chinese players
   (Sculptok / 翰林AI) actually did.
2. **Per-material compression presets.** Jade, wood, and jewelry have different depth budgets —
   hand-tune `compress_beta` / `detail_gain` (and `relief_depth_mm`) per material and ship them as
   named presets.
3. **Clean input generation.** If you later add AI image generation (FLUX / Qwen-Image), bias it
   toward high-contrast, single-subject, clutter-free images so the pipeline behaves. Optionally
   add 4K upscaling (Real-ESRGAN / SUPIR) of the input before processing (plan §8 Phase 3).

---

## Workstreams (plan §8 Phase 3–4)

### A. Fine-tune the normal model (biggest payoff)
- Assemble a relief/sculpture/ornament dataset (image → normal pairs; can bootstrap from renders
  of 3D sculpture assets).
- Fine-tune StableNormal (or Marigold-Normals) on it.
- Swap the fine-tuned checkpoint into `models.py` (`estimate_normals_stable` /
  `estimate_normals_marigold`).
- **Measure:** A/B the new vs old normals on your held-out subjects; cleaner feathers/folds/hair,
  fewer blobs.

### B. Per-material presets
- Define presets (jade / wood / jewelry / …) as `ReliefParams` bundles with tuned
  `compress_beta`, `detail_gain`, `relief_depth_mm`.
- Expose a material selector in the UI (Part 09) and/or the `/relief` form.

### C. Interactive relief-depth control
- An interactive relief-depth slider in the UI driving `relief_depth_mm` / `compress_beta` with
  a fast preview.

### D. Input upscaling
- Optional 4K upscaling (Real-ESRGAN / SUPIR) of the input before the pipeline for crisper detail.

### E. Toolpath / G-code (CAM) — make it machine-ready
- Integrate CAM (Vectric Aspire relief module, or open-source CAM) so output is **machine-ready
  G-code**, not just an STL. This is the §1 out-of-scope "Phase 4" item — the difference between a
  mesh and something the CNC actually runs.

---

## Licensing gate (only if you ever distribute — plan §10)

For **local/private use this does not apply** — run whatever's best. It matters only if you ship
commercially:

- **Safe to ship as-is:** BiRefNet (MIT), Marigold-Normals (the Apache `-lcm-v0-1` checkpoint),
  trimesh (MIT), and all the §5.1 geometry (public-domain math).
- **Would need swapping:** StableNormal, GeoWizard, Depth Anything V2 *Large* — several research
  checkpoints are **CC-BY-NC**. For a paid product, switch normals to the Apache Marigold-LCM and
  depth to Depth-Anything **Small/Base**.
- The bas-relief algorithm itself is unencumbered.

> If you fine-tune (workstream A) on a non-commercial base checkpoint, the license of that base
> carries forward — pick the base with distribution in mind if a paid product is the goal.

---

## Done when (this is ongoing — milestones, not a single finish line)

- [ ] A fine-tuned normal checkpoint measurably beats stock StableNormal on your held-out
      subjects, and is swapped into `models.py`.
- [ ] Per-material presets defined and selectable.
- [ ] (If shipping commercially) the licensing swap done per plan §10.
- [ ] (Stretch) CAM/G-code path produces machine-ready output.

## Source

Plan §8 (Build Roadmap, Phase 3–4), §10 (Licensing), §11 (Closing the Quality Gap), §12 (repos &
models reference).

## Quick reference — repos & models (plan §12)

**Models (HF / hub):** `ZhengPeng7/BiRefNet` (bg, MIT) · `Stable-X/StableNormal` (normals, best
detail) · `prs-eth/marigold-normals-v1-1` (normals full; `-lcm-v0-1` = fast Apache) ·
`lemonaddie/geowizard` (normals/depth, strong object model) ·
`depth-anything/Depth-Anything-V2-Large-hf` (depth).

**Repos (geometry / glue):** `HugoTini/NormalHeight` (Frankot-Chellappa reference) ·
`Sajjad-Mahmoudi/Photometric-Stereo` (clean `frankotchellappa()`) ·
`timothywong731/ComfyUI-Depth2Mesh` (heightmap→STL) · `1038lab/ComfyUI-LBM` (depth+normal nodes).

**Key papers (Stage 4 math):** Ji, Sun, Ma — *Normal Image Manipulation for Bas-relief
Generation* (arXiv:1804.06092) · Weyrich et al. 2007 / Fattal et al. 2002 (gradient-domain
compression).
