"""system_info.py — real GPU/host telemetry for the System & health panel.

Primary source is `nvidia-smi` (utilization, temp, power, VRAM in one call). Disk-free
comes from the model drive. `resident` tracks which engine currently holds the GPU
(relief vs image vs idle) — set by server.run_feature. Off the box (no nvidia-smi) it
returns available=False with safe placeholders so the UI degrades gracefully.
"""
import os
import shutil
import subprocess
from pathlib import Path

_QUERY = "name,memory.total,memory.used,utilization.gpu,temperature.gpu,power.draw"

_resident = {"engine": "idle", "model": "—"}     # 'relief' | 'image' | 'idle'


def set_resident(engine, model="—"):
    _resident.update(engine=engine, model=model)


def _nvidia_smi():
    try:
        r = subprocess.run(
            ["nvidia-smi", f"--query-gpu={_QUERY}", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4)
        if r.returncode != 0 or not r.stdout.strip():
            return None
        p = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")]
        name, mtot, mused, util, temp, power = (p + ["0"] * 6)[:6]
        return {"device": name, "vram_total_mb": float(mtot), "vram_used_mb": float(mused),
                "util": float(util), "temp": float(temp), "power": float(power)}
    except Exception:
        return None


def _disk_free_gb():
    target = Path(os.environ.get("COMFYUI_DIR") or Path.cwd())
    try:
        while not target.exists() and target != target.parent:
            target = target.parent
        return round(shutil.disk_usage(str(target)).free / 1e9, 1)
    except Exception:
        return None


def system():
    g = _nvidia_smi()
    res = dict(_resident)
    disk = _disk_free_gb()
    if g:
        vt, vu = g["vram_total_mb"] / 1024.0, g["vram_used_mb"] / 1024.0
        return {
            "available": True, "device": g["device"],
            "vram_total": round(vt, 1), "vram_used": round(vu, 1), "vram_free": round(vt - vu, 1),
            "vram_percent": round(100 * vu / vt) if vt else 0,
            "util": round(g["util"]), "temp": round(g["temp"]), "power": round(g["power"]),
            "disk_free": disk, "resident": res["engine"], "model_loaded": res["model"],
        }
    return {
        "available": False, "device": "GPU — telemetry unavailable",
        "vram_total": 12, "vram_used": 0, "vram_free": 12, "vram_percent": 0,
        "util": 0, "temp": 0, "power": 0,
        "disk_free": disk, "resident": res["engine"], "model_loaded": res["model"],
    }
