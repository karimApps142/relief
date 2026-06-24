"""features/_comfy.py — shared ComfyUI HTTP client for the diffusion features
(text2img / img2img / upscale). Drives a headless ComfyUI (+ComfyUI-GGUF) on
:8188 with hand-authored API-format graphs. Point at it via COMFYUI_URL."""
import os
import time
import uuid


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    """Upload inputs, queue an API-format graph, poll /history, fetch the output PNG."""

    def __init__(self, server=None, timeout=30):
        self.base = f"http://{server or os.environ.get('COMFYUI_URL', '127.0.0.1:8188')}"
        self.timeout = timeout
        self.client_id = uuid.uuid4().hex

    def _session(self):
        import requests
        return requests.Session()

    def upload_image(self, path):
        """Upload an input image to ComfyUI; return the name to use in a LoadImage node."""
        s = self._session()
        with open(path, "rb") as f:
            r = s.post(f"{self.base}/upload/image",
                       files={"image": (os.path.basename(path), f, "image/png")},
                       data={"overwrite": "true"}, timeout=self.timeout)
        r.raise_for_status()
        j = r.json()
        return f"{j['subfolder']}/{j['name']}" if j.get("subfolder") else j["name"]

    def generate(self, graph, poll=1.0, max_wait=600):
        """Queue an API-format graph; return the first output image's PNG bytes."""
        import requests
        s = self._session()
        try:
            r = s.post(f"{self.base}/prompt",
                       json={"prompt": graph, "client_id": self.client_id}, timeout=self.timeout)
        except requests.exceptions.RequestException:
            raise ComfyUIError(f"ComfyUI not reachable at {self.base} — is it running "
                               f"(python ComfyUI/main.py --listen --port 8188)?")
        if r.status_code != 200:
            raise ComfyUIError(f"/prompt {r.status_code}: {r.text[:400]}")
        pid = r.json()["prompt_id"]
        waited = 0.0
        while waited < max_wait:
            h = s.get(f"{self.base}/history/{pid}", timeout=self.timeout).json()
            if pid in h:                                  # appears only once complete
                for node in h[pid].get("outputs", {}).values():
                    for im in node.get("images", []):
                        v = s.get(f"{self.base}/view", params={
                            "filename": im["filename"], "subfolder": im.get("subfolder", ""),
                            "type": im.get("type", "output")}, timeout=self.timeout)
                        v.raise_for_status()
                        return v.content
                raise ComfyUIError("ComfyUI finished but produced no image")
            time.sleep(poll); waited += poll
        raise ComfyUIError(f"ComfyUI timed out after {max_wait}s")
