"""
test_features.py — feature registry + relief module smoke test (lite backend).
Verifies the Feature contract end-to-end: schema, param coercion, run() -> artifacts.
Run: RELIEF_BACKEND=lite python test_features.py
"""
import os
os.environ.setdefault("RELIEF_BACKEND", "lite")
from pathlib import Path
import numpy as np
import cv2
from PIL import Image
import trimesh

from features import REGISTRY

assert "relief" in REGISTRY, "relief feature not registered"
feat = REGISTRY["relief"]

sch = feat.schema()
print("feature:", sch["id"], "| name:", sch["name"], "| params:", len(sch["params"]))
assert sch["inputs"] == ["image"] and len(sch["params"]) >= 8

# coercion: clamps out-of-range, fills defaults, parses string bools
p = feat.coerce({"relief_depth_mm": 999, "make_solid": "true", "depth_model": "bogus"})
assert p["relief_depth_mm"] == 20.0, "number not clamped to max"
assert p["make_solid"] is True, "string bool not parsed"
assert p["depth_model"] == "depth-anything", "bad select not reset to default"
print("coerce OK:", {k: p[k] for k in ("relief_depth_mm", "make_solid", "depth_model")})

# run end-to-end (lite)
img = np.full((160, 160), 40, np.uint8)
cv2.circle(img, (80, 80), 55, 210, -1)
src = Path("out/feat_src.png"); src.parent.mkdir(exist_ok=True)
Image.fromarray(img).convert("RGB").save(src)

res = feat.run({"image": str(src)}, feat.coerce({"make_solid": True}), Path("out"))
print("artifacts:", {k: Path(v).name for k, v in res.items()})
assert Path(res["heightmap"]).exists() and Path(res["stl"]).exists()
assert np.asarray(Image.open(res["heightmap"])).dtype == np.uint16
assert trimesh.load(res["stl"]).is_watertight
print("OK: feature registry + relief.run passed")
