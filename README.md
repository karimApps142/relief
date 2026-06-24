# Relief Studio

A local, GPU-backed AI studio with a schema-driven React UI. Modular features:

- **Image → Relief** — a photo becomes a clean bas-relief **heightmap** (16-bit PNG) + **STL**
  (and a 3D preview), ready for CNC carving / 3D printing. Depth-driven (monocular depth + tiling).
- **Text → Image**, **Image → Image**, **Upscale** — backed by **Krea-2-Turbo (GGUF)** running in
  a ComfyUI engine that the app installs, downloads, and launches for you (you never open ComfyUI).

Everything runs privately on your own machine. The server (`server.py`) serves both the API and the
prebuilt React UI on one port.

## Start it

**Windows GPU box** — double-click **`start.bat`** (or run it over SSH). It pulls the latest and
launches the server:

```cmd
cd /d F:\relief
start.bat
```

**Mac / Linux (dev / lite mode):**

```bash
./start.sh
```

Then open **http://localhost:8000** (or, on the box via Tailscale, **http://100.86.189.84:8000**).

> First run: on the **Relief** tab click **Download models** (BiRefNet + Depth-Anything, ~2.3 GB)
> for full quality. For the image tabs, the **Set up the image engine** wizard installs ComfyUI and
> downloads the Krea models — all from buttons in the UI. No env vars needed.

## Manual launch (what the launcher runs)

```bash
.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000      # Mac/Linux
.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000   # Windows
```

`lite` vs `full`: the relief feature uses crude CPU depth until the GPU weights are present, then
switches to `full` automatically (no restart).

## First-time setup (per machine)

```bash
python3 -m venv .venv
# Mac (lite/dev):   .venv/bin/pip install -r requirements.txt
# GPU box (full):   .venv\Scripts\python.exe -m pip install -r requirements-gpu.txt
```

## Docs

- **Image engine (Krea/ComfyUI) plan + in-app management:** [`docs/TEXT2IMG_KREA_PLAN.md`](docs/TEXT2IMG_KREA_PLAN.md)
- **Remote access / box deployment:** [`docs/REMOTE_ACCESS_AND_DOCKER.md`](docs/REMOTE_ACCESS_AND_DOCKER.md)
- **Build plan:** [`docs/cnc-bas-relief-build-plan.md`](docs/cnc-bas-relief-build-plan.md)
