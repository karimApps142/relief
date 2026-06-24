"""relief_progress.py — phase-level progress for the (synchronous) relief pipeline.

The relief run isn't a step-loop like diffusion, but it does move through real phases
(depth+tiling → heightmap → STL → preview). generate_relief reports those boundaries
here; /api/progress surfaces them so the UI shows a real stepper + elapsed instead of a
blind spinner. Percent reflects genuine phase completion (no fabricated curve).
"""
import time
import threading

_lock = threading.Lock()
_state = {"active": False, "feature": "relief", "phases": [], "phase_idx": 0,
          "tiles_total": 0, "node": "", "started": 0.0}


def get():
    with _lock:
        s = dict(_state)
    n = len(s["phases"]) or 1
    s["percent"] = 100 if not s["active"] and s["phase_idx"] >= n else round(100 * s["phase_idx"] / n)
    s["elapsed"] = round(time.monotonic() - s["started"], 1) if s["started"] else 0
    return s


def start(phases, tiles_total=0):
    with _lock:
        _state.update(active=True, phases=list(phases), phase_idx=0, tiles_total=tiles_total,
                      started=time.monotonic(), node=phases[0] if phases else "")


def phase(idx):
    with _lock:
        ph = _state["phases"]
        _state.update(phase_idx=idx, node=ph[idx] if 0 <= idx < len(ph) else "")


def stop():
    with _lock:
        _state.update(active=False, phase_idx=len(_state["phases"]))
