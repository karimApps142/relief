# Part 07 — Windows 11 native run + tuning (the real relief)

**Goal:** run the whole thing on the real box — clone, install both requirements, start the
service, press **Download Models** once, and produce a genuine high-detail 16-bit relief + STL on
the RTX 3060. Then tune the §9 knobs for your typical subjects.

**Runs on:** 🪟 Windows 11 Pro — `DESKTOP-BVI0N3I`, Ryzen 5 5600, 32 GB RAM, RTX 3060 **12 GB**

**Prerequisites:** Parts 00–06 pushed to GitHub; latest NVIDIA driver installed on Windows.

**Files:** none new — this is install, run, and tune.

> The dev doc originally said "Windows 10"; your box is **Windows 11 Pro**. Everything below works
> the same (native venv); Win 11's WSL2/CUDA story only matters for the optional Docker path
> (Part 08).

---

## The big idea

Go **native first** (plain venv + the cu121 torch wheel) before any Docker. It's far easier to
debug, and you do **not** need conda — the PyTorch wheels bundle their own CUDA runtime, so `pip`
in a venv is enough on Windows. With 12 GB VRAM you can keep all models resident and run
`use_depth_fusion=True`; only call `models.unload_all()` between stages on tight runs.

---

## Steps

### 1. Clone + install (PowerShell)

```powershell
git clone git@github.com:karimapps142/relief.git
cd relief
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-gpu.txt       # torch+cuda (cu121), diffusers, transformers
python -c "import torch; print(torch.cuda.is_available())"   # expect: True
```

### 2. Run the service

```powershell
uvicorn service:app --host 0.0.0.0 --port 8000
```

### 3. Download the weights once (the button)

```powershell
# trigger the download (or click the Download Models button in your UI)
curl -X POST http://localhost:8000/models/download
# poll until installed:true (first run pulls a few GB into the HF cache)
curl http://localhost:8000/models/status
```

### 4. Generate a real relief

With `backend=auto` (Part 05), once weights are present the service resolves to `full`
automatically:

```powershell
curl -F "file=@portrait.jpg" -F "make_solid=false" -F "backend=auto" http://localhost:8000/relief
# -> full backend: BiRefNet mask + StableNormal normals + Depth Anything fusion
```

Or drive it directly in Python to iterate on knobs:

```python
from pipeline import generate_relief, ReliefParams
generate_relief("portrait.jpg", "out/",
                ReliefParams(normals="stable", use_depth_fusion=True,
                             relief_depth_mm=8.0, pixel_mm=0.1), backend="full")
```

---

## Tuning guide — the knobs that matter (plan §9)

| Knob (`ReliefParams`) | Effect | If output looks wrong |
|------|--------|----------------------|
| `compress_beta` | global depth compression | too "tall"/distorted → lower it; too flat → raise it |
| `detail_gain` | high-frequency punch | mushy/soft → raise; noisy/harsh → lower |
| `relief_depth_mm` | physical carve depth | set to your stock/material limit |
| `pixel_mm` | physical plate size & resolution | controls final dimensions |
| `flip_y` | normal green-channel convention | relief inverted/embossed-inward → toggle |
| `invert` | white=high vs black=high | if your CAM expects the opposite, toggle |
| `normals` | `"stable"` vs `"marigold"` | marigold = more steps, sometimes sharper |

**Always export 16-bit** — 8-bit causes visible stepping ("terracing") on the carved surface.

**GPU sizing reference (plan §7):** at 12 GB you're in the "keep all models resident,
`use_depth_fusion=True`, fastest" tier. Unload between stages only if you hit OOM on very large
inputs.

---

## Process

Day-to-day loop (handover §4): edit on Mac → `git push` → on Windows `git pull` → restart the
service. Code only; the multi-GB weights stay in the Windows HF cache and download once.

Test on **20–30 varied images** (portraits, animals, ornaments) and lock in good default knobs
for your typical subjects (plan §8 Phase 1).

---

## Verify

- `torch.cuda.is_available()` is `True`; `nvidia-smi` shows the process using the 3060 during a
  run.
- After Download Models, `GET /models/status` → `installed: true`.
- A `backend=auto` relief request now uses the **full** backend (sharp, carved detail — clearly
  better than the Mac lite output from Part 03).
- Output PNG is 16-bit; STL opens cleanly.

## Done when

- [ ] Both requirements installed on Windows 11; CUDA available.
- [ ] Weights downloaded once into the HF cache; status reports `installed: true`.
- [ ] A real, high-detail 16-bit relief + STL produced from the 3060.
- [ ] Default knobs tuned against ~20–30 representative images and recorded.

## Source

Handover §4 (GitHub workflow), §6 (what-runs-where), §7 (suggested order); plan §7 (running
locally, GPU sizing) and §9 (tuning guide).
