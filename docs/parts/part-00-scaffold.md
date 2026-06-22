# Part 00 — Project scaffold & repo setup

**Goal:** create the empty `relief/` project skeleton — the file tree, the **two**
requirements files (light + GPU), ignore files, a README — and push it to GitHub. After this
part the repo installs cleanly on the Mac with **no torch**, ready for the geometry code in
Part 01.

**Runs on:** 🍎 Mac (everything here is CPU/setup only)

**Prerequisites:** none — this is the first part.

**Files created:** `requirements.txt`, `requirements-gpu.txt`, `.gitignore`, `.dockerignore`,
`README.md` (the project's own readme, not this parts index).

---

## The big idea (why two requirements files)

The whole Mac↔Windows workflow hinges on **keeping torch out of the light requirements**. The
Mac installs only `requirements.txt` (numpy/opencv/fastapi/… — no torch), runs the `lite`
backend, and can exercise the entire pipeline + UI + STL export with zero model downloads. The
Windows box additionally installs `requirements-gpu.txt` (torch/diffusers/transformers) for the
real models. **Do not let any GPU dependency leak into `requirements.txt`.**

---

## The code / files

### Target repo tree (built across Parts 00–06)

```
relief/
├── relief_core.py         # CPU geometry — runs everywhere (Part 01)
├── backends.py            # lite (Mac) + full (GPU); full imports models lazily (Part 02)
├── models.py              # real model wrappers — only used by FullBackend (Part 06)
├── model_manager.py       # check + download weights (the UI button) (Part 05)
├── pipeline.py            # backend-aware orchestration (Part 03)
├── service.py             # FastAPI: /relief + /models/status + /models/download (Parts 04–05)
├── requirements.txt       # LIGHT deps — installs on Mac, NO torch        ← this part
├── requirements-gpu.txt   # torch / diffusers / transformers — GPU box only ← this part
├── Dockerfile             # GPU image for Windows / other machines (Part 08)
├── .dockerignore          # ← this part
├── .gitignore             # ← this part
└── README.md              # ← this part
```

> In this part you only create the files marked "← this part". The rest land in their own parts;
> the tree is here so you know where everything is headed.

### `requirements.txt` (light — all the Mac installs)

```txt
numpy
scipy
opencv-python-headless
Pillow
scikit-image
trimesh
fastapi
uvicorn[standard]
python-multipart
pydantic
huggingface_hub          # for the download manager; pulls no torch by itself
```

### `requirements-gpu.txt` (Windows / NVIDIA box only, installed *after* the light file)

```txt
--extra-index-url https://download.pytorch.org/whl/cu121
torch
torchvision
diffusers>=0.30
transformers>=4.44
accelerate
einops
```

### `.gitignore` (weights live in the HF cache, never in git)

```gitignore
.venv/
venv/
__pycache__/
*.pyc
.DS_Store
/data/
/outputs/
# HF model cache lives in ~/.cache/huggingface — outside the repo by design
```

### `.dockerignore`

```gitignore
.venv/
venv/
__pycache__/
.git/
data/
outputs/
```

### `README.md` (project readme — short stub is fine for now)

A minimal readme: one-line description ("local image → bas-relief heightmap + STL"), a pointer
to `docs/cnc-bas-relief-build-plan.md` and `docs/parts/`, and the two-line run hint:
`pip install -r requirements.txt` then `RELIEF_BACKEND=lite uvicorn service:app --reload`.

---

## Steps

```bash
# 1. make the project folder (separate from this CNC-BRG/docs planning folder, or reuse it —
#    your call; the handover assumes a repo named "relief")
mkdir relief && cd relief

# 2. create the files above (requirements.txt, requirements-gpu.txt, .gitignore,
#    .dockerignore, README.md) with the exact contents shown

# 3. prove the light deps install on the Mac with NO torch
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip freeze | grep -i torch     # expect: NO output

# 4. init git and push to GitHub
git init
git add .
git commit -m "relief scaffold: light/gpu requirements + ignores"
git branch -M main
git remote add origin git@github.com:karimapps142/relief.git
git push -u origin main
```

---

## Verify

- `pip install -r requirements.txt` completes on the Mac.
- `pip freeze | grep -i torch` prints **nothing** (torch did not sneak in).
- `git remote -v` shows the GitHub origin; `git push` succeeded.

## Done when

- [ ] `requirements.txt` exists and contains **no** torch/diffusers/transformers.
- [ ] `requirements-gpu.txt` exists with the cu121 torch stack.
- [ ] `.gitignore` and `.dockerignore` exist.
- [ ] `README.md` stub exists.
- [ ] Light deps install clean in a fresh venv on the Mac.
- [ ] Repo pushed to `github.com/karimapps142/relief`.

## Source

Handover §3 (repo structure, requirements files, .gitignore) and §4 (GitHub workflow).
