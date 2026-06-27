"""features/_comfy.py — shared ComfyUI HTTP/WS client for the diffusion features
(text2img / img2img / upscale).

generate() drives a headless ComfyUI: it queues an API-format graph, connects to the
/ws progress socket, and reports live sampler progress into a process-global state
(read by GET /api/comfy/progress) while waiting for completion. If the websocket is
unavailable (or stalls / drops) it falls back to polling /history — generation still
works, just without the live bar. Point at ComfyUI via COMFYUI_URL (default
127.0.0.1:8188).

Design notes (hardened after review):
- The prompt is submitted EXACTLY ONCE up front, so a ws failure can never re-queue it.
- A single monotonic deadline bounds the whole call (ws watch + any HTTP fallback),
  so total wait is capped at max_wait regardless of which path runs.
- stdlib-only for HTTP (urllib) so the server venv needs no extra deps; `websockets`
  (ships with uvicorn[standard]) is optional.
"""
import os
import json
import time
import uuid
import asyncio
import threading
import urllib.error
import urllib.parse
import urllib.request

try:                                                      # optional: drives the live bar
    import websockets
    _HAS_WS = True
except Exception:                                         # pragma: no cover
    _HAS_WS = False

_WS_SILENCE = 120                                         # s of ws quiet → fall back to poll


class ComfyUIError(RuntimeError):
    pass


# --- process-global generation progress (single-user box: one gen at a time) ------
_progress_lock = threading.Lock()
_progress = {"active": False, "value": 0, "max": 0, "node": None, "label": ""}


def get_progress():
    with _progress_lock:
        return dict(_progress)


def _reset_progress(label=""):
    with _progress_lock:
        _progress.update(active=True, value=0, max=0, node=None, label=label)


def _clear_progress():
    with _progress_lock:
        _progress.update(active=False, value=0, max=0, node=None)


def _set_progress(**kw):
    with _progress_lock:
        _progress.update(**kw)


class ComfyUIClient:
    """Upload inputs, queue an API-format graph, stream progress, fetch the output PNG."""

    def __init__(self, server=None, timeout=30):
        self.server = server or os.environ.get("COMFYUI_URL", "127.0.0.1:8188")
        self.base = f"http://{self.server}"
        self.port = self.server.split(":")[-1]
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    # ----------------------------------------------------------------- HTTP (urllib)
    def _get_json(self, path, params=None):
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return json.loads(r.read().decode())

    def _get_bytes(self, path, params=None):
        url = f"{self.base}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=self.timeout) as r:
            return r.read()

    def _unreachable(self):
        return ComfyUIError(f"ComfyUI not reachable at {self.base} — is it running "
                            f"(ComfyUI/main.py --listen --port {self.port})?")

    def upload_image(self, path):
        """Upload an input image to ComfyUI (multipart); return the LoadImage name."""
        # sanitise the filename — it goes raw into a Content-Disposition header.
        fname = os.path.basename(path).replace('"', "").replace("\\", "").replace("\r", "").replace("\n", "")
        with open(path, "rb") as f:
            file_data = f.read()
        boundary = "----comfy" + uuid.uuid4().hex
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; "
            f"filename=\"{fname}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
        ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(
            f"{self.base}/upload/image", data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                j = json.loads(r.read().decode())
        except urllib.error.URLError:
            raise self._unreachable()
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    # ----------------------------------------------------------------- internals
    def free(self):
        """Ask ComfyUI to unload its models + free VRAM, so the local depth/normal
        models have room on a 12 GB card (cross-engine pipelines run sequentially)."""
        try:
            data = json.dumps({"unload_models": True, "free_memory": True}).encode()
            req = urllib.request.Request(f"{self.base}/free", data=data, method="POST",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=self.timeout)
        except Exception:
            pass

    def _submit(self, graph):
        data = json.dumps({"prompt": graph, "client_id": self.client_id}).encode()
        req = urllib.request.Request(f"{self.base}/prompt", data=data, method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode())["prompt_id"]
        except urllib.error.HTTPError as e:               # ComfyUI rejected the graph
            raise ComfyUIError(f"/prompt {e.code}: {e.read().decode(errors='replace')[:400]}")
        except urllib.error.URLError:
            raise self._unreachable()

    async def _watch_ws(self, pid, deadline):
        """Stream progress for the already-queued prompt `pid` until it completes.
        Raises ComfyUIError on an execution error or the overall deadline; raises
        asyncio.TimeoutError on prolonged ws silence (caller then falls back to poll)."""
        url = f"ws://{self.server}/ws?clientId={self.client_id}"
        async with websockets.connect(url, max_size=None, open_timeout=5) as ws:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ComfyUIError(f"ComfyUI timed out")
                try:
                    out = await asyncio.wait_for(ws.recv(), timeout=min(remaining, _WS_SILENCE))
                except asyncio.TimeoutError:
                    if deadline - time.monotonic() <= 0:
                        raise ComfyUIError(f"ComfyUI timed out")
                    raise                                  # ws went quiet → caller polls instead
                if isinstance(out, (bytes, bytearray)):
                    continue                               # preview image (binary) — ignore
                try:
                    msg = json.loads(out)
                except ValueError:
                    continue                               # skip a malformed frame, keep watching
                t, d = msg.get("type"), (msg.get("data") or {})
                if t == "progress":
                    _set_progress(value=int(d.get("value", 0)), max=int(d.get("max", 0)),
                                  node=d.get("node"))
                elif t == "progress_state":                # newer builds: per-node dict
                    try:
                        running = [v for v in (d.get("nodes") or {}).values() if v.get("max")]
                        if running:
                            v = max(running, key=lambda x: x.get("value", 0))
                            _set_progress(value=int(v.get("value", 0)), max=int(v.get("max", 0)))
                    except Exception:
                        pass
                elif d.get("prompt_id") == pid:
                    if t == "execution_error":
                        raise ComfyUIError(d.get("exception_message") or "ComfyUI execution error")
                    if t == "execution_success" or (t == "executing" and d.get("node") is None):
                        return                             # this prompt finished

    def _poll_until_done(self, pid, deadline):
        while time.monotonic() < deadline:
            try:
                if pid in self._get_json(f"/history/{pid}"):
                    return
            except urllib.error.URLError:
                raise self._unreachable()
            time.sleep(1.0)
        raise ComfyUIError(f"ComfyUI timed out")

    def _fetch_output(self, pid):
        try:
            h = self._get_json(f"/history/{pid}")
            for node in h.get(pid, {}).get("outputs", {}).values():
                for im in node.get("images", []):
                    return self._get_bytes("/view", {
                        "filename": im["filename"], "subfolder": im.get("subfolder", ""),
                        "type": im.get("type", "output")})
        except urllib.error.URLError:
            raise self._unreachable()
        raise ComfyUIError("ComfyUI finished but produced no image")

    def _fetch_output_file(self, pid, exts, prefer=None):
        """Fetch a saved output file whose name ends in one of `exts` (e.g. an exported
        GLB mesh). Scans every output node key-agnostically, since non-image savers list
        their files under their own ui key ('3d', etc.). When several match and `prefer`
        is given, return the one whose filename contains it (e.g. 'textured'); else the
        LAST match (export nodes usually run last)."""
        exts = tuple(e.lower() for e in exts)
        cands = []
        try:
            h = self._get_json(f"/history/{pid}")
            for node in h.get(pid, {}).get("outputs", {}).values():
                for items in node.values():
                    if not isinstance(items, list):
                        continue
                    for it in items:
                        if isinstance(it, dict) and isinstance(it.get("filename"), str) \
                                and it["filename"].lower().endswith(exts):
                            cands.append(it)
        except urllib.error.URLError:
            raise self._unreachable()
        if not cands:
            raise ComfyUIError(f"ComfyUI finished but produced no {'/'.join(exts)} file")
        pick = next((c for c in cands if prefer and prefer.lower() in c["filename"].lower()), cands[-1])
        return self._get_bytes("/view", {
            "filename": pick["filename"], "subfolder": pick.get("subfolder", ""),
            "type": pick.get("type", "output")})

    # --------------------------------------------------------------------- public
    def generate(self, graph, label="", max_wait=600):
        """Queue the graph and return the first output image's PNG bytes, streaming
        live progress. Submits once; ws for progress; HTTP-poll fallback for the rest."""
        _reset_progress(label)
        deadline = time.monotonic() + max_wait
        try:
            pid = self._submit(graph)                     # queue EXACTLY once
            if _HAS_WS:
                try:
                    asyncio.run(self._watch_ws(pid, deadline))
                except ComfyUIError:
                    raise                                  # real execution error / deadline
                except Exception:
                    self._poll_until_done(pid, deadline)   # ws missing/closed/quiet → poll
            else:
                self._poll_until_done(pid, deadline)
            return self._fetch_output(pid)
        finally:
            _clear_progress()

    def generate_file(self, graph, exts=(".glb",), prefer=None, label="", max_wait=900):
        """Like generate(), but returns the bytes of a saved FILE output matching `exts`
        (e.g. an exported GLB mesh) instead of an image. `prefer` picks among several
        matches by filename substring (e.g. 'textured'). Image→3D and other mesh-producing
        graphs save to disk rather than emitting an `images` output."""
        _reset_progress(label)
        deadline = time.monotonic() + max_wait
        try:
            pid = self._submit(graph)                     # queue EXACTLY once
            if _HAS_WS:
                try:
                    asyncio.run(self._watch_ws(pid, deadline))
                except ComfyUIError:
                    raise
                except Exception:
                    self._poll_until_done(pid, deadline)   # ws missing/closed/quiet → poll
            else:
                self._poll_until_done(pid, deadline)
            return self._fetch_output_file(pid, exts, prefer)
        finally:
            _clear_progress()
