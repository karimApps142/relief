# Part 08 — Dockerize for multi-machine Windows 11 deployment

**Goal:** containerize the GPU service so it reproduces identically across several Windows 11
machines without re-fighting the torch/diffusers/CUDA install on each. Do this **only after the
native run (Part 07) works** — containerize for portability, not to debug.

**Runs on:** 🪟 Windows 11 (WSL2 + Docker Desktop). 🍎 **Not on the Mac** — Docker on Apple
Silicon can't reach an NVIDIA GPU, and you don't need a container for CPU/lite testing.

**Prerequisites:** Part 07 (native run confirmed on at least one Windows box).

**Files created:** `Dockerfile`, `.dockerignore` (the `.dockerignore` was scaffolded in Part 00 —
confirm it's present).

---

## The big idea & honest caveats

You're distributing to **several Windows 11 machines**, so Docker is the right tool eventually —
it removes the *Python-dependency* pain. But it does **not** remove the *GPU-driver* setup: each
Windows machine still needs the NVIDIA driver + WSL2 plumbing. So:

- **Mac: don't bother.** Just the venv (Parts 00–05, lite).
- **First Windows box: go native first** (Part 07), then containerize for the *other* machines.

> **Windows 11 note (corrects the original "Windows 10" doc):** on Windows 11, WSL2 and the NVIDIA
> CUDA-on-WSL2 passthrough are built in and smoother than on Win 10. The prerequisite steps are
> the same list, just easier — recent Docker Desktop wires the GPU through WSL2 automatically.

---

## Windows 11 + Docker + GPU prerequisites

1. Latest NVIDIA driver (Game Ready or Studio — WSL2 CUDA support is built in).
2. **WSL2** enabled, with a Linux distro installed (`wsl --install` on Windows 11 does this in one
   step).
3. **Docker Desktop** using the **WSL2 backend**.
4. NVIDIA GPU support (recent Docker Desktop wires this through WSL2 automatically).

Verify the GPU is visible to Docker:

```bash
docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi
# should list your RTX 3060
```

---

## The code

### `Dockerfile` (GPU image)

```dockerfile
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y \
        python3 python3-pip git libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt requirements-gpu.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt -r requirements-gpu.txt
COPY . .
ENV RELIEF_BACKEND=auto
EXPOSE 8000
CMD ["uvicorn", "service:app", "--host", "0.0.0.0", "--port", "8000"]
```

> `libgl1` + `libglib2.0-0` are required by OpenCV in a slim image.

### `.dockerignore` (scaffolded in Part 00 — confirm)

```gitignore
.venv/
venv/
__pycache__/
.git/
data/
outputs/
```

---

## Build & run (on the Windows box, inside WSL2/Docker)

```bash
docker build -t relief-gpu .
docker run --gpus all -p 8000:8000 \
  -v hf_cache:/root/.cache/huggingface \
  relief-gpu
```

The `-v hf_cache:...` volume **persists the downloaded weights** across container restarts —
without it, every `docker run` re-downloads several GB. Press **Download Models** once; the volume
keeps them.

---

## Deploy to the other machines

1. On each target Windows 11 box: install driver + WSL2 + Docker Desktop (the prereqs above) once.
2. Either `docker build` from the repo, or push `relief-gpu` to a registry and `docker pull`.
3. `docker run --gpus all -p 8000:8000 -v hf_cache:/root/.cache/huggingface relief-gpu`.
4. Hit **Download Models** once per machine (or pre-seed the `hf_cache` volume).

---

## Verify

- `docker run --rm --gpus all nvidia/cuda:12.1.1-base-ubuntu22.04 nvidia-smi` lists the 3060.
- `docker build -t relief-gpu .` succeeds.
- `docker run --gpus all -p 8000:8000 -v hf_cache:... relief-gpu` serves `http://localhost:8000`
  (`/health` → `{"ok": true}`).
- After one Download Models, restarting the container does **not** re-download weights (volume
  persisted).
- A `backend=auto` relief request inside the container uses the GPU.

## Done when

- [ ] WSL2 + Docker Desktop + driver verified (`nvidia-smi` via Docker lists the 3060).
- [ ] `Dockerfile` + `.dockerignore` present.
- [ ] Image builds and serves the API on `:8000` with `--gpus all`.
- [ ] `hf_cache` volume persists weights across restarts.
- [ ] Reproduced on a second Windows 11 machine.

## Source

Handover §5 (Docker), corrected from "Windows 10" to **Windows 11** throughout.
