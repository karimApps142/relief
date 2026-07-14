"""relief_progress.py — phase + per-tile progress for the (synchronous) relief pipeline.

The relief run moves through real phases (depth+tiling → heightmap → STL → preview).
The depth+tiling phase dominates wall-clock, so instead of stalling the bar at 0% until
that phase flips, we drive its share of the bar by TILES COMPLETED (each depth forward
pass ticks once). generate_relief reports both; /api/progress surfaces it so the UI shows
a truthful, steadily-rising bar + a "tiles done / total" readout.
"""
import time
import threading

_lock = threading.Lock()
_state = {"active": False, "feature": "relief", "phases": [], "phase_idx": 0,
          "tiles_total": 0, "tiles_done": 0, "node": "", "started": 0.0}
_preview = None       # artifact URL of a mid-run intermediate image (e.g. the depth map the
                      # 2.5D-Relief pipeline shows while the AI stage runs); None = nothing to show

# the depth+tiling phase (index 0) owns this share of the bar; the quick finishing
# phases (heightmap / STL / preview) split the remainder. Keeps the bar honest.
_DEPTH_SHARE = 0.80


def get():
    with _lock:
        s = dict(_state)
    n = len(s["phases"]) or 1
    if not s["active"] and s["phase_idx"] >= n:
        pct = 100
    elif s["phase_idx"] <= 0 and s["tiles_total"] > 0:
        pct = round(100 * _DEPTH_SHARE * min(s["tiles_done"], s["tiles_total"]) / s["tiles_total"])
    else:                                   # finishing phases share the remaining 1-share
        pct = round(100 * (_DEPTH_SHARE + (1 - _DEPTH_SHARE) * s["phase_idx"] / n))
    s["percent"] = min(100, pct)
    s["elapsed"] = round(time.monotonic() - s["started"], 1) if s["started"] else 0
    return s


def start(phases, tiles_total=0):
    with _lock:
        _state.update(active=True, phases=list(phases), phase_idx=0,
                      tiles_total=int(tiles_total), tiles_done=0,
                      started=time.monotonic(), node=phases[0] if phases else "")


def set_tiles(total):
    with _lock:
        _state.update(tiles_total=int(total), tiles_done=0)


def tick_tile(n=1):
    """One depth forward-pass finished. Passed as the on_tile callback into tiling."""
    with _lock:
        cap = _state["tiles_total"] or (_state["tiles_done"] + n)
        _state["tiles_done"] = min(_state["tiles_done"] + n, cap)


def phase(idx):
    with _lock:
        ph = _state["phases"]
        _state.update(phase_idx=idx, node=ph[idx] if 0 <= idx < len(ph) else "")


def stop():
    with _lock:
        _state.update(active=False, phase_idx=len(_state["phases"]))


def set_preview(url):
    """Publish (or clear, with None) a mid-run intermediate image the UI should show while the
    run continues — e.g. the generated depth map before the AI-relief stage. The URL must point
    at an already-written artifact (/api/jobs/<job>/<name>): the <img> src is constant, so a 404
    on a half-written file would never retry."""
    global _preview
    with _lock:
        _preview = url


def preview_url():
    with _lock:
        return _preview
