"""
test_geom.py — Part 01 smoke test for relief_core.py.
No models needed: builds a synthetic hemisphere normal map, runs the full
CPU geometry chain, and checks the outputs are 16-bit + watertight.
Run: python test_geom.py
"""
import numpy as np
import cv2
import relief_core as rc

# a fake "bump": a smooth hemisphere normal map, HxWx3 in [0,1]
H = W = 256
yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
cx, cy, r = W / 2, H / 2, 90
dx, dy = (xx - cx) / r, (yy - cy) / r
zz = np.sqrt(np.clip(1 - dx**2 - dy**2, 0, 1))
n = np.stack([-dx, -dy, np.maximum(zz, 1e-3)], -1)
n /= np.linalg.norm(n, axis=-1, keepdims=True)
normal_map = ((n + 1) / 2).astype(np.float32)
mask = (dx**2 + dy**2 <= 1).astype(np.float32)

height = rc.integrate_normals(normal_map)
height = rc.bas_relief_compress(height, beta=0.55)
height = rc.enhance_detail(height, detail_gain=1.4)
height = rc.flatten_background(height, mask)
h16 = rc.to_heightmap_16bit(height)
cv2.imwrite("test_relief.png", h16)

solid = rc.heightmap_to_solid(h16, z_scale_mm=8.0, pixel_mm=0.1)
solid.export("test_relief.stl")
surface = rc.heightmap_to_surface(h16, z_scale_mm=8.0, pixel_mm=0.1)

print("16-bit?", h16.dtype, h16.max())          # uint16, up to 65535
print("watertight?", solid.is_watertight)        # expect True
print("solid faces/verts:", len(solid.faces), len(solid.vertices))
print("surface faces/verts:", len(surface.faces), len(surface.vertices))

assert h16.dtype == np.uint16, "heightmap is not 16-bit"
assert h16.max() > 0, "heightmap is empty"
assert solid.is_watertight, "solid mesh is not watertight"
print("OK: Part 01 geometry smoke test passed")
