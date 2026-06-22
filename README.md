# relief — CNC Bas-Relief Generator

Local tool: an ordinary image → a clean, high-detail **bas-relief heightmap** (16-bit PNG) +
an **STL**, ready for CNC carving or 3D printing. Runs privately on your own GPU. The pipeline is
**normal-driven** (surface detail lives in normals, not coarse depth).

## Two ways it runs

- **`lite`** — pure CPU, **no models, no torch**. Runs on a MacBook. Crude quality, but exercises
  the whole pipeline + UI + STL export for development.
- **`full`** — real models (BiRefNet + StableNormal/Marigold + Depth Anything) on an NVIDIA GPU.
  Production quality.

## Quick start (Mac, lite mode)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # light deps — no torch
RELIEF_BACKEND=lite uvicorn service:app --reload    # API
# or, once Part 09 is built:  RELIEF_BACKEND=lite python app_gradio.py   # browser UI
```

On the Windows GPU box, also `pip install -r requirements-gpu.txt`, then press **Download
Models** once. `RELIEF_BACKEND=auto` switches to `full` automatically when weights are present.

## Docs

- **Build plan:** [`docs/cnc-bas-relief-build-plan.md`](docs/cnc-bas-relief-build-plan.md)
- **Dev workflow (Mac ↔ Windows):** [`docs/DEV_WORKFLOW_AND_HANDOVER.md`](docs/DEV_WORKFLOW_AND_HANDOVER.md)
- **Step-by-step build parts:** [`docs/parts/`](docs/parts/) — start at
  [`part-00-scaffold.md`](docs/parts/part-00-scaffold.md).
