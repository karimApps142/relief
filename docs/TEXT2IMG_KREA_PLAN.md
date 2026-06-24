# Phase 3 — Text-to-Image feature (Krea-2-Turbo, GGUF, via ComfyUI)

Status: **CODE DONE — needs the box setup (ComfyUI + 3 model files) to run.**

✅ **Implemented (in repo):** `features/text2img.py` (a `ComfyUIClient` + the
`Text2ImgFeature`, registered in `features/__init__.py`), a `"text"` ParamSpec type
(`base.py`) + prompt `<textarea>` in the React UI. The API-format graph is
**hand-authored from the verified Krea workflow's GGUF path** — no manual export
needed. The feature already shows up at `/api/features` and in the UI; it just
errors with "ComfyUI not reachable" until the box setup below is done.

⏳ **Remaining = box setup only:** install ComfyUI + ComfyUI-GGUF, drop in the 3
model files, run it headless on :8188. Then point our server at it
(`COMFYUI_URL=127.0.0.1:8188`, the default) and it works.

---

## 1. The model

- **Krea-2-Turbo** — `krea/Krea-2-Turbo` (official, ~62 GB full / ~35 GB diffusers).
  12B-parameter Diffusion Transformer, **`qwen_image` architecture** (Qwen-Image based),
  text→image. **Turbo = distilled: 8 steps, guidance/cfg 0.0.** Up to 2048×2048.
  License: **Krea 2 Community License — requires content filtering for deployment.**
- **GGUF (what makes it fit our 12 GB 3060):** `vantagewithai/Krea-2-Turbo-GGUF`
  — the **transformer only**, quantized. No text encoder / VAE in that repo.

### Why GGUF
A 12B transformer is ~24 GB in bf16 → impossible on a 12 GB card. Quantized:

| Quant | Transformer | Fit on 12 GB (with text-encoder offloaded) |
|---|---|---|
| **Q4_K_M** | **7.49 GB** | ✅ recommended (≈9–10 GB peak) |
| Q5_K_M | 8.87 GB | ✅ a bit more quality |
| Q6_K | 10.58 GB | ⚠️ tight |
| Q8_0 | 13.71 GB | ❌ exceeds 12 GB |

**Plan: Q4_K_M** (safe headroom, keeps the 8-step turbo speed).

---

## 2. Components to download (3 parts)

The GGUF repo is transformer-only, so source the rest (all standard `qwen_image`
ComfyUI assets — same encoder/VAE Qwen-Image uses):

1. **Transformer** — `vantagewithai/Krea-2-Turbo-GGUF` → `*Q4_K_M.gguf` (~7.5 GB)
   → `ComfyUI/models/unet/`
2. **Text encoder** — Qwen2.5-VL (qwen_image text encoder), fp8 or GGUF
   (e.g. Comfy-Org / city96 qwen_image text-encoder release) → `ComfyUI/models/text_encoders/`
3. **VAE** — qwen_image VAE (~0.5 GB) → `ComfyUI/models/vae/`

(Verify exact encoder/VAE filenames against the repo's `Vantage_Krea-2-Turbo.json`
workflow — it names the nodes/files it expects.)

---

## 3. Runtime — ComfyUI headless (the reliable path for GGUF diffusion)

GGUF diffusion is run via **ComfyUI + ComfyUI-GGUF**, not raw diffusers (diffusers
GGUF support for this brand-new arch is unproven). The GGUF repo even ships a
ComfyUI workflow (`Vantage_Krea-2-Turbo.json`). Bonus: once ComfyUI is the engine,
**image→image / upscale / ControlNet become easy additions** through the same path.

**Setup on the box (one-time):**
```
# in F:\ (or alongside relief), with node not required — ComfyUI is Python
git clone https://github.com/comfyanonymous/ComfyUI
cd ComfyUI && .\.venv... pip install -r requirements.txt   # or reuse our venv
git clone https://github.com/city96/ComfyUI-GGUF custom_nodes/ComfyUI-GGUF
pip install -r custom_nodes/ComfyUI-GGUF/requirements.txt   # gguf, etc.
# drop the 3 model files into models/unet, models/text_encoders, models/vae
python main.py --listen 0.0.0.0 --port 8188   # headless API on :8188
```
VRAM: Q4 transformer 7.5 GB on GPU; ComfyUI offloads the text encoder after it
encodes the prompt → peak ≈ 9–10 GB, fits the 3060.

---

## 4. Integration into our modular app (the actual code)

Mirror the relief feature. **No frontend changes** — the React UI is schema-driven.

1. **`features/text2img.py`** — new `Feature`:
   ```python
   class Text2ImgFeature(Feature):
       id = "text2img"; name = "Text → Image"; inputs = ["text"]
       params = [ ParamSpec("prompt","text",""), ParamSpec("width","number",1024,...),
                  ParamSpec("height","number",1024,...), ParamSpec("steps","number",8,...),
                  ParamSpec("seed","number",0,...) ]
       def run(self, inputs, params, out_dir):
           # 1. load Vantage_Krea-2-Turbo.json (workflow template)
           # 2. inject prompt / width / height / steps / seed into the right nodes
           # 3. POST to ComfyUI  http://127.0.0.1:8188/prompt   (returns prompt_id)
           # 4. poll /history/{prompt_id} until done; read the output image path
           # 5. copy the PNG into out_dir, return {"image": path}
   ```
   - Need a small ComfyUI API client (`POST /prompt`, `GET /history/{id}`,
     `GET /view?filename=...`). ~40 lines.
   - `inputs` gains a **`"text"`** kind — extend the base/`server.py` to accept a
     text field (currently only `file`/image). One small addition to `run_feature`
     (read a `prompt` form field) + the React `FeaturePanel` already can render a
     text input if we add a `"text"` ParamSpec type (add a `<textarea>` branch).
2. **`features/__init__.py`** — `register(Text2ImgFeature())`. Done — it auto-appears.
3. **`base.py` ParamSpec** — add a `"text"` type; **`FeaturePanel.tsx`** — render
   `"text"` as a `<textarea>` (rebuild `web/dist`). Small, one-time.
4. **ComfyUI lifecycle** — either run ComfyUI as a separate always-on service
   (simplest), or have the feature module start/check it. Keep relief on our
   `server.py`; text2img just calls ComfyUI's API.

---

## 5. VERIFIED box setup (the only remaining work)

Exact files the code expects (verified from the Krea workflow JSON):

| File | ComfyUI folder | Source |
|---|---|---|
| `krea2_turbo-Q4_K_M.gguf` (or Q3_K_M/Q5_K_M/Q6_K — selectable in UI) | `models/unet/` | `vantagewithai/Krea-2-Turbo-GGUF` |
| `qwen3vl_4b_fp8_scaled.safetensors` (Qwen3-VL 4B encoder) | `models/text_encoders/` | qwen_image / Krea ComfyUI release |
| `qwen_image_vae.safetensors` | `models/vae/` | qwen_image release |

Steps on the box:
```
# 1. ComfyUI + the GGUF node (reuse the relief venv or a fresh one)
git clone https://github.com/comfyanonymous/ComfyUI
git clone https://github.com/city96/ComfyUI-GGUF ComfyUI/custom_nodes/ComfyUI-GGUF
.venv\Scripts\python.exe -m pip install -r ComfyUI/requirements.txt
.venv\Scripts\python.exe -m pip install -r ComfyUI/custom_nodes/ComfyUI-GGUF/requirements.txt
# 2. download the 3 files above into the listed folders (hf download / browser)
# 3. run ComfyUI headless
.venv\Scripts\python.exe ComfyUI/main.py --listen 0.0.0.0 --port 8188
# 4. run our app in another shell; it auto-finds ComfyUI at 127.0.0.1:8188
.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Then in the UI pick **Text → Image**, type a prompt, Generate. (No manual workflow
export — the graph is built in `features/text2img.py:_build_graph`. If the exact
node names ever change, that's the one function to update.)

Verified graph (GGUF path): `UnetLoaderGGUF(16)` → `KSampler(2)` ← `CLIPTextEncode(6)`
← `CLIPLoader(18, type="krea2")`, `ConditioningZeroOut(8)` as negative,
`EmptyLatentImage(10)`, `VAEDecode(3)` ← `VAELoader(4)`, `SaveImage(22)`.
Defaults: 8 steps, cfg 1.0, sampler `er_sde`, scheduler `simple`.

Last: add a content-filter stub (license requirement) before any non-internal use.

---

## 6. Risks / notes
- **VRAM**: Q4_K_M fits with headroom; Q6/Q8 don't. Stay ≤ Q5_K_M on the 3060.
- **License**: Krea 2 Community License requires content filtering — fine internal,
  flag before public launch.
- **Encoder/VAE sourcing**: confirm exact files from the workflow JSON; qwen_image
  assets are on HF (Comfy-Org / city96).
- **Two processes**: ComfyUI (:8188) + our server (:8000). Acceptable; document the
  run order in the quick-start.
- **Speed**: 8-step turbo at Q4 on a 3060 ≈ a few seconds–tens of seconds per image
  (much faster than the tiled relief).

## Sources
- https://huggingface.co/krea/Krea-2-Turbo
- https://huggingface.co/vantagewithai/Krea-2-Turbo-GGUF
- https://github.com/comfyanonymous/ComfyUI
- https://github.com/city96/ComfyUI-GGUF
