# Relief Studio

A local, GPU-backed AI studio with a schema-driven React UI. Modular features:

- **Image → Relief** — a photo becomes a clean bas-relief **heightmap** (16-bit PNG) + **STL**
  (and a 3D preview), ready for CNC carving / 3D printing. Depth-driven (monocular depth + tiling).
- **Text → Image**, **Image → Image**, **Upscale** — backed by **Krea-2-Turbo (GGUF)** running in
  a ComfyUI engine that the app installs, downloads, and launches for you (you never open ComfyUI).
- **Chat** — a ChatGPT-style conversation with **Bonsai 27B** (Prism ML's ternary / 1-bit
  quantization of Qwen3.6-27B) running locally via llama.cpp. Streaming replies, markdown + code
  blocks, collapsible thought process, and per-thread history. See below.

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

## Chat (Bonsai 27B, local LLM)

Open the **Chat** tab in the icon rail. It walks through a one-time setup:

1. **Install the engine.** These GGUFs declare a custom `dspark` architecture with `Q2_0_g128`
   ternary kernels, so **stock llama.cpp and `llama-cpp-python` cannot load them** — Prism's fork
   is required. The button downloads Prism's **prebuilt binaries** for the machine, so there is
   **no CMake, Visual Studio or CUDA Toolkit to install**:
   - Windows + NVIDIA → the CUDA 12.4 build plus the `cudart` pack that carries the CUDA runtime
     DLLs (~650 MB total). Only the GPU *driver* is needed, never the toolkit.
   - Apple Silicon / Intel Mac → the Metal build (~11 MB). Linux and CPU-only variants likewise.

   A **Build from source** link remains as a fallback for platforms with no published binary;
   that path does need `git`, CMake and a C++ compiler.
2. **Download a model** (this does *not* wait for the build — it can run in parallel):

   | Model | File | Size | Notes |
   | :--- | :--- | ---: | :--- |
   | Ternary Bonsai 27B · Q2_0 | `Ternary-Bonsai-27B-Q2_0.gguf` | 7.17 GB | ~1.71 bits/weight, ~95% of FP16 quality |
   | Bonsai 27B · Q1_0 | `Bonsai-27B-Q1_0.gguf` | 3.80 GB | the 1-bit companion — lighter, lower quality |

3. **Load into VRAM.** Only one model is resident at a time; loading one unloads the depth models
   and stops ComfyUI, because a 27B model and a Krea checkpoint do not co-exist on a 12 GB card.
   "Unload · free VRAM" in the settings drawer hands the GPU back to the image features.

Sampling defaults are Prism's published benchmark settings (temp 0.7 · top-p 0.95 · top-k 20) and
are adjustable, along with the system prompt, in the settings drawer.

Environment overrides: `LLAMA_CPP_DIR` (default `<repo-parent>/llama.cpp-prism`), `LLM_MODELS_DIR` (default `<repo-parent>/llm-models`),
`LLM_URL` (default `127.0.0.1:8899`), `LLM_CTX` (default `8192`).

**Slow downloads?** Weights and engine are fetched as 8 concurrent byte ranges, because a single
TCP stream to a distant CDN is usually latency-bound rather than bandwidth-bound (GitHub Releases
is much worse for this than HuggingFace's CDN). Raise `LLM_DOWNLOAD_SEGMENTS` to 16 on a very
high-latency link, or set it to `1` to disable parallel fetching if a proxy or firewall objects.
Any failure falls back to a single stream automatically, and a dropped segment resumes rather
than restarting.

## Docs

- **Image engine (Krea/ComfyUI) plan + in-app management:** [`docs/TEXT2IMG_KREA_PLAN.md`](docs/TEXT2IMG_KREA_PLAN.md)
- **Remote access / box deployment:** [`docs/REMOTE_ACCESS_AND_DOCKER.md`](docs/REMOTE_ACCESS_AND_DOCKER.md)
- **Build plan:** [`docs/cnc-bas-relief-build-plan.md`](docs/cnc-bas-relief-build-plan.md)
