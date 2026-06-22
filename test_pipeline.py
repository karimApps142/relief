"""
test_pipeline.py — Part 03 end-to-end smoke test (lite backend, no models).
Generates a structured synthetic image, runs generate_relief in lite mode,
and checks a 16-bit heightmap + a watertight STL come out.
Run: RELIEF_BACKEND=lite python test_pipeline.py
"""
import os
from pathlib import Path
import numpy as np
import cv2
from PIL import Image

import trimesh
from pipeline import generate_relief, ReliefParams

os.environ.setdefault("RELIEF_BACKEND", "lite")

# ---- build a synthetic "photo" with luminance structure (drives lite normals) ----
H = W = 384
img = np.full((H, W), 40, np.uint8)
cv2.circle(img, (W // 2, H // 2), 130, 200, -1)          # head
cv2.circle(img, (W // 2 - 45, H // 2 - 30), 22, 90, -1)  # eye
cv2.circle(img, (W // 2 + 45, H // 2 - 30), 22, 90, -1)  # eye
cv2.ellipse(img, (W // 2, H // 2 + 45), (60, 30), 0, 0, 180, 110, -1)  # mouth
img = cv2.GaussianBlur(img, (0, 0), sigmaX=3)            # soften edges
src = Path("sample_input.png")
Image.fromarray(img).convert("RGB").save(src)

# ---- run the pipeline end-to-end (lite) ----
out_dir = "out"
result = generate_relief(str(src), out_dir,
                         ReliefParams(make_solid=True, relief_depth_mm=8.0,
                                      pixel_mm=0.1, backend="lite"))
print("result:", result)

png = Path(result["heightmap"])
stl = Path(result["stl"])
assert png.exists() and stl.exists(), "outputs missing"

h = np.array(Image.open(png))
print("heightmap mode/dtype/max:", Image.open(png).mode, h.dtype, int(h.max()))
assert h.dtype == np.uint16, "heightmap is not 16-bit"
assert h.max() > 0, "heightmap is empty"

mesh = trimesh.load(str(stl))
print("STL watertight?", mesh.is_watertight, "faces:", len(mesh.faces))
assert mesh.is_watertight, "solid STL not watertight"
print("OK: Part 03 end-to-end lite pipeline passed")
