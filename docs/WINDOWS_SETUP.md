# Windows 11 setup — real run on the RTX 3060

Complete walkthrough to run the `full` (real-models) backend on the GPU box
(`DESKTOP-BVI0N3I` — Windows 11 Pro, Ryzen 5 5600, 32 GB RAM, **RTX 3060 12 GB**).
12 GB is comfortable: StableNormal + depth fusion fit without unloading.

All commands are **PowerShell**. Companion to [`parts/part-06-gpu-models.md`](parts/part-06-gpu-models.md)
and [`parts/part-07-windows-run.md`](parts/part-07-windows-run.md).

---

## 0. One-time machine prerequisites

1. **NVIDIA driver** (the only GPU thing you must install — the torch wheel bundles its own CUDA
   runtime, so you do **not** need the CUDA Toolkit or conda).
   - Install the latest **Game Ready** or **Studio** driver for the RTX 3060 (GeForce Experience
     or nvidia.com).
   - Verify in PowerShell:
     ```powershell
     nvidia-smi
     ```
     Should list the RTX 3060 and a CUDA version (e.g. 12.x) top-right.

2. **Python 3.11** — install from python.org. ✅ **Check "Add python.exe to PATH"** in the
   installer. Verify:
   ```powershell
   python --version        # Python 3.11.x
   ```
   (3.11 matches what was tested on the Mac. 3.12 also works; avoid 3.13+ for now.)

3. **Git for Windows** — from git-scm.com. It bundles **Git Credential Manager**, which handles
   GitHub login in a browser on first clone of a private repo.

---

## 1. Get the code

```powershell
cd $HOME\Desktop
git clone https://github.com/karimApps142/relief.git
cd relief
```

- If the repo is **private**, the first clone pops a browser to sign in to GitHub (Credential
  Manager). If you prefer SSH and have a key on this box added to GitHub, use
  `git clone git@github.com:karimApps142/relief.git` instead.

---

## 2. Create the venv + install (light, then GPU)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip

pip install -r requirements.txt          # light stack (no torch)
pip install -r requirements-gpu.txt      # cu121 torch wheel + diffusers/transformers (~2.5 GB)
```

> **If `Activate.ps1` is blocked** ("running scripts is disabled"), run this once, then retry:
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```
> (Or use `cmd` and `.venv\Scripts\activate.bat`.)

---

## 3. Verify CUDA is live

```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
# expect:  2.x.x+cu121 True
```

If it prints `False` or a non-`+cu121` version, see **Troubleshooting** below (almost always the
CPU torch wheel got installed instead of the cu121 one).

Optional CPU sanity check (proves the geometry + lite pipeline work before any download):
```powershell
python test_geom.py
python test_pipeline.py
```

---

## 4. Run the UI + download the models (once)

```powershell
python app_gradio.py
```

1. Open **http://localhost:7860**.
2. Expand **"Models (Windows GPU box)"** → click **Download Models**.
   First run pulls a few GB into `C:\Users\<you>\.cache\huggingface`: BiRefNet,
   Marigold-Normals-v1-1, Depth-Anything-V2-Large (StableNormal warms via torch.hub). Wait for
   the status to flip to **✅ full mode**.
3. Upload an image → **Generate relief**. It now runs the **full** backend (real models) and you
   get a sharp 16-bit heightmap preview + downloadable **PNG** and **STL**.

> Both the Gradio app and the API call `backend="auto"`, which resolves to **full** automatically
> once weights are present — you don't need to set `RELIEF_BACKEND`.

### Or run the API instead of the UI
```powershell
uvicorn service:app --host 0.0.0.0 --port 8000
```
```powershell
# in another PowerShell, inside the repo + venv:
curl.exe -X POST http://localhost:8000/models/download         # once; poll status:
curl.exe http://localhost:8000/models/status
curl.exe -F "file=@yourimage.jpg" -F "backend=auto" -F "make_solid=false" http://localhost:8000/relief
```

---

## 5. Tune for your subjects

Drive it from the UI sliders, or in Python for repeatable runs:

```powershell
python -c "from pipeline import generate_relief, ReliefParams; print(generate_relief('portrait.jpg','out/', ReliefParams(normals='stable', use_depth_fusion=True, relief_depth_mm=8.0, pixel_mm=0.1), backend='full'))"
```

| Knob | Effect | If wrong |
|------|--------|----------|
| `compress_beta` | global depth compression | too tall/distorted → lower; too flat → raise |
| `detail_gain` | high-frequency punch | mushy → raise; noisy → lower |
| `relief_depth_mm` | physical carve depth | set to your stock/material limit |
| `pixel_mm` | plate size & resolution | controls final dimensions |
| `flip_y` | normal green-channel convention | relief inverted/embossed-inward → toggle |
| `invert` | white=high vs black=high | toggle if your CAM expects the opposite |
| `normals` | `stable` vs `marigold` | try `marigold` if stable looks off |

Always export 16-bit (the pipeline does). Test on ~20–30 varied images and lock in defaults.

Day-to-day: edit on Mac → `git push` → here `git pull` → restart the app. Weights stay in the HF
cache (downloaded once); only code moves.

---

## Troubleshooting

**`torch.cuda.is_available()` is False / version isn't `+cu121`.**
The CPU wheel got installed. Force the cu121 wheel:
```powershell
pip uninstall -y torch torchvision
pip install -r requirements-gpu.txt --force-reinstall
```
Then re-check. Also confirm `nvidia-smi` works (driver installed).

**StableNormal fails to download or import.**
It loads via `torch.hub` and has extra deps; `download_models` wraps the warm-up in try/except, so
the rest still installs. Just use **Marigold** instead: in the UI set *Normals model* to
`marigold` (or pass `normals="marigold"`). Quality is excellent and it needs only the pinned
`diffusers`/`transformers`.

**`MarigoldNormalsPipeline` import error.**
Bump diffusers: `pip install -U diffusers`.

**Out of memory (rare at 12 GB).**
Only on very large inputs. Reduce input resolution, or call `models.unload_all()` between stages.
Depth fusion + StableNormal normally fit in 12 GB.

**Windows Firewall prompt when the server starts.**
Allow on private networks if you want other machines on your LAN to reach it; for local-only use,
`127.0.0.1` is fine and you can deny.

**Disk space.**
The HF cache needs ~8–10 GB for all weights. It lives in `C:\Users\<you>\.cache\huggingface`,
outside the repo.

---

## Docker (later, for the other Windows machines)

Once native works here, containerize for the rest — see
[`parts/part-08-docker.md`](parts/part-08-docker.md). Needs WSL2 + Docker Desktop (WSL2 backend) +
the NVIDIA driver; run with `--gpus all` and a `-v hf_cache:/root/.cache/huggingface` volume so
weights persist. Don't bother on the Mac (no NVIDIA passthrough on Apple Silicon).
