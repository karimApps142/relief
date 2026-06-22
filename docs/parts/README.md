# CNC Bas-Relief — Build Parts (index & progress tracker)

This folder breaks the two canonical planning docs into **small, self-contained, buildable
parts** you can pick up one at a time, execute, verify, and check off — without re-reading the
whole plan each session. Each part carries its goal, the actual reference code, copy-paste steps,
a verify command, and a done-checklist.

**Canonical reference (unchanged — read these for full context):**
- [`../cnc-bas-relief-build-plan.md`](../cnc-bas-relief-build-plan.md) — the full pipeline,
  architecture, roadmap, tuning, licensing.
- [`../DEV_WORKFLOW_AND_HANDOVER.md`](../DEV_WORKFLOW_AND_HANDOVER.md) — the Mac↔Windows lite/full
  dev workflow.

---

## What this is

A **local tool**: ordinary image → clean high-detail **bas-relief heightmap** (16-bit) + **STL**,
ready for CNC carving or 3D printing. It runs privately on your own GPU (Sculptok / 翰林AI-style
output). The pipeline is **normal-driven** — the carved-looking detail lives in surface normals,
not coarse depth:

```
image
  └─> remove background ........... (subject mask + clean plane)
  └─> estimate surface normals .... (fine detail: feathers, folds)
  └─> [optional] estimate depth ... (global proportion)
  └─> integrate normals -> height . (surface-from-gradient)
  └─> bas-relief compression ...... (squash global depth, keep detail)  ← the secret sauce
  └─> enhance + flatten + 16-bit .. (CNC-ready heightmap)
  └─> heightmap -> STL ............ (CNC / 3D print)
```

Only **one** stage is real algorithm code you write (bas-relief compression, Part 01). Everything
else is a model you call or glue.

---

## The Mac ↔ Windows split (why parts are tagged 🍎 / 🪟)

Develop **all the logic + UI** on the MacBook with **no heavy models** (`lite` backend, no torch),
then run the **real models** on the Windows GPU box (`full` backend).

| Backend | Where | Models? | torch/CUDA? | Quality | Purpose |
|---------|-------|---------|-------------|---------|---------|
| **`lite`** | 🍎 MacBook | none | not installed | crude | test pipeline + UI + STL, zero downloads |
| **`full`** | 🪟 Windows RTX 3060 | downloaded on demand | installed | production | the real relief |

**Real box:** `DESKTOP-BVI0N3I` — **Windows 11 Pro**, Ryzen 5 5600, **32 GB RAM**, RTX 3060
**12 GB**. Comfortable: StableNormal + depth fusion fit; unload only on tight runs.

---

## Parts & suggested order

### Core — local pipeline (do these in order)

| # | Part | Runs on | Produces |
|---|------|---------|----------|
| 00 | [Scaffold & repo setup](part-00-scaffold.md) | 🍎 | repo tree, `requirements*.txt`, ignores, GitHub |
| 01 | [Geometry core](part-01-geometry-core.md) | 🍎🪟 | `relief_core.py` (verified, low-risk) |
| 02 | [Backends (lite/full)](part-02-backends.md) | 🍎 | `backends.py` — the lite/full switch |
| 03 | [Pipeline](part-03-pipeline.md) | 🍎 | `pipeline.py` — E2E lite relief + STL on Mac |
| 04 | [FastAPI service](part-04-service.md) | 🍎 | `service.py` — `/health` + `/relief` |
| 05 | [Model manager](part-05-model-manager.md) | 🍎→🪟 | `model_manager.py` + `/models/*` + `auto` backend |
| 06 | [GPU models](part-06-gpu-models.md) | 🪟 | `models.py` — BiRefNet/StableNormal/Marigold/Depth |
| 07 | [Windows run + tuning](part-07-windows-run.md) | 🪟 | real high-detail relief on the 3060; tuned knobs |

### Deploy

| # | Part | Runs on | Produces |
|---|------|---------|----------|
| 08 | [Docker (multi-machine)](part-08-docker.md) | 🪟 | `Dockerfile`, reproducible GPU image |

### Optional / Later

| # | Part | Runs on | Produces |
|---|------|---------|----------|
| 09 | [Gradio UI (all-Python)](part-09-gradio-ui.md) | 🍎🪟 | `app_gradio.py` — upload→tune→preview→download |
| 10 | [The moat](part-10-moat.md) | 🪟 | fine-tuned normals, presets, CAM/G-code |
| A | [ComfyUI Phase-0 prototype](appendix-comfyui-prototype.md) | 🪟 | eyeball quality before building |

### Dependency / order graph

```
            🍎 MacBook (lite)                          🪟 Windows 11 (full)
  00 ─▶ 01 ─▶ 02 ─▶ 03 ─▶ 04 ─▶ 05  ──push/pull──▶  06 ─▶ 07 ─▶ 08
                                                             │
   (Appendix A: ComfyUI prototype — optional, do first to derisk quality)
                                                             ▼
                                  09 Gradio UI ·· 10 moat   (optional, parallelable)
```

01 only needs 00. 02 needs 01. 03 needs 01+02. 04 needs 03. 05 needs 04. 06 needs the repo on
Windows. 07 needs 06. 08 needs 07. 09 (Gradio) needs 03 (+05 for the models panel). 10 needs 06–07.

---

## Progress tracker

- [ ] **00** Scaffold & repo setup
- [ ] **01** Geometry core (`relief_core.py`)
- [ ] **02** Backends (`backends.py`)
- [ ] **03** Pipeline (`pipeline.py`)
- [ ] **04** FastAPI service (`service.py`)
- [ ] **05** Model manager + `/models/*` + `auto`
- [ ] **06** GPU models (`models.py`)  ·  🪟 Windows
- [ ] **07** Windows run + tuning  ·  🪟 Windows
- [ ] **08** Docker multi-machine  ·  🪟 Windows
- [ ] **09** Gradio UI — `app_gradio.py` (optional)
- [ ] **10** The moat (later/ongoing)
- [ ] **A** ComfyUI prototype (optional)

---

## "What runs where" cheat-sheet (handover §6, updated for Windows 11)

| | 🍎 MacBook (dev) | 🪟 Windows 11 RTX 3060 (real) |
|---|---|---|
| Install | `requirements.txt` | `requirements.txt` + `requirements-gpu.txt` |
| torch / CUDA | not installed | installed (cu121 wheel) |
| Model weights | none | downloaded on demand (HF cache) |
| Backend | `lite` (CPU) | `full` (GPU); `auto` resolves to it |
| Docker | no | optional, recommended for multi-machine |
| You're testing | UI, pipeline, geometry, STL, the API | real relief quality |

---

## Key invariants (don't break these while building)

- **`requirements.txt` stays torch-free.** Mac installs only the light file; torch / diffusers /
  transformers live only in `requirements-gpu.txt`. (Parts 00, 06)
- **`FullBackend` imports `models` lazily** — importing `backends.py` on the Mac must never pull
  torch. (Part 02)
- **Backend selection:** `RELIEF_BACKEND=lite|full`, plus `auto` → `full` if `models_present()`
  else `lite`. (Parts 02, 05)
- **Always export 16-bit** heightmaps — 8-bit terraces the carve. (Part 01, plan §9)
- **Windows 11**, not 10, in Parts 07–08.
