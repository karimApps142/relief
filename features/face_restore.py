"""features/face_restore.py — restore/enhance faces (GFPGAN via spandrel + facexlib).

Local GPU feature. Detects every face, restores it (sharper eyes, skin, hair), and
pastes it back onto the original image — great as a pre-step before relief, or on its
own. Avoids basicsr entirely (spandrel loads the GFPGAN net; facexlib does detect/paste).

Box dependency (one-time):  pip install facexlib spandrel
The GFPGAN weights + facexlib detection models auto-download on first use.
"""
from pathlib import Path
from PIL import Image

from .base import Feature, ParamSpec


class FaceRestoreFeature(Feature):
    id = "face_restore"
    name = "Face Restore"
    description = "Restore/enhance faces (GFPGAN) — crisper eyes, skin, hair. Great before relief."
    inputs = ["image"]
    engine = "local"
    icon = "face"
    est_runtime = "~3–15 s"
    vram = "~2 GB"
    output_kinds = ["Restored image"]
    params = [
        ParamSpec("fidelity", "number", 0.4, "Fidelity (closer to original)", 0.0, 1.0, 0.05,
                  control="slider",
                  help="0 = maximum restoration, 1 = stay closest to the original face."),
    ]

    def run(self, inputs, params, out_dir):
        img = Image.open(inputs["image"]).convert("RGB")
        try:
            import models
            rgb = models.restore_faces(img, weight=float(params.get("fidelity", 0.4)))
        except Exception as e:
            raise RuntimeError(
                f"Face restore unavailable ({e}). On the GPU box, install it once: "
                f"pip install facexlib spandrel")
        out = Path(out_dir) / "restored.png"
        Image.fromarray(rgb).save(out)
        return {"restored": str(out)}
