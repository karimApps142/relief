#!/usr/bin/env bash
# Relief Studio launcher (dev — Mac/Linux). On the Windows GPU box use start.bat.
set -e
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"

echo "Relief Studio  →  http://localhost:8000   (Ctrl+C to stop)"
exec "$PY" -m uvicorn server:app --host 0.0.0.0 --port 8000
