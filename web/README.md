# Relief Studio — web UI (Vite + React + Tailwind)

A **schema-driven** frontend for the modular feature API (`../server.py`). It
fetches `/api/features` and renders each feature's UI from its param schema, so
new features (relief, upscale, text→image, …) appear **automatically** with no
frontend changes.

## Run — Mac drives the box (recommended; no node needed on the box)

**On the box** — start the feature API (GPU):
```
cd /d F:\relief
.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```

**On the Mac** — run the UI dev server pointed at the box:
```
cd web
npm install                                          # once
RELIEF_API=http://100.86.189.84:8000 npm run dev
```
Open **http://localhost:5173** on the Mac. Vite proxies `/api` → the box, so the
GPU does the work and the UI is served locally with hot-reload.

## Single-process deploy (optional; needs node on the box)
```
cd web && npm install && npm run build               # -> web/dist
# server.py auto-serves web/dist at "/" — then just:
.venv\Scripts\python.exe -m uvicorn server:app --host 0.0.0.0 --port 8000
```
Open `http://100.86.189.84:8000`.

> The legacy Gradio UI (`app_gradio.py`) still works unchanged during the migration.
