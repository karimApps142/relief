"""
features/base.py — the feature-module contract.

Every AI feature (relief, text2img, img2img, upscale, …) is a `Feature` subclass:
declarative metadata, a typed param schema the UI renders generically, and a single
`run(inputs, params, out_dir) -> {name: path}`.

The schema is rich enough that the React UI renders the exact control + grouping +
helper text per param, with no per-feature frontend code. Adding a feature = drop a
module in `features/` and register it in `features/__init__.py`.
"""
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

# data type -> default render control, when ParamSpec.control is not given
_DEFAULT_CONTROL = {"number": "slider", "bool": "switch", "select": "select", "text": "textarea"}


@dataclass
class ParamSpec:
    """One UI-renderable parameter.

    type    — data type: 'number' | 'bool' | 'select' | 'text'
    control — render hint: 'slider' | 'stepper' | 'seg' | 'select' | 'switch' | 'textarea'
              (defaults from type when omitted)
    choices — for select/seg: list of {"value","label"} (or bare strings)
    """
    name: str
    type: str
    default: Any = None
    label: str = ""
    min: float = None
    max: float = None
    step: float = None
    choices: list = None
    control: str = None
    group: str = "basic"          # 'basic' | 'advanced'
    help: str = ""
    suffix: str = ""              # unit shown after the value, e.g. " mm", " px"
    placeholder: str = ""
    depends_on: dict = None       # {"param": <name>, "value": <v>} → conditional visibility

    def as_dict(self):
        d = asdict(self)
        d["control"] = self.control or _DEFAULT_CONTROL.get(self.type, self.type)
        return d


def _choice_values(choices):
    return [c["value"] if isinstance(c, dict) else c for c in (choices or [])]


class Feature:
    id: str = ""
    name: str = ""
    description: str = ""
    inputs: list = ["image"]        # input kinds to collect, e.g. ["image"] | []
    params: list = []               # list[ParamSpec]
    needs_comfy: bool = False       # runs on the ComfyUI engine (UI shows the setup gate)
    engine: str = "local"           # 'local' | 'comfy'
    est_runtime: str = ""           # approx wall-clock, e.g. "~5 s – 4 min"
    vram: str = ""                  # approx peak VRAM, e.g. "~2–4 GB"
    output_kinds: list = []         # ["Heightmap PNG", "3D preview GLB", "STL mesh"]
    icon: str = "box"               # semantic icon hint: box|text|image|upscale

    def run(self, inputs: dict, params: dict, out_dir: Path) -> dict:
        """inputs: {kind: value}. params: coerced dict. Returns {artifact_name: path}."""
        raise NotImplementedError

    # ---- shared helpers (the API + UI use these) ----
    def schema(self) -> dict:
        return {
            "id": self.id, "name": self.name, "description": self.description,
            "inputs": self.inputs, "needs_image": "image" in self.inputs,
            "needs_comfy": self.needs_comfy, "engine": self.engine,
            "est_runtime": self.est_runtime, "vram": self.vram,
            "output_kinds": self.output_kinds, "icon": self.icon,
            "params": [p.as_dict() for p in self.params],
        }

    def coerce(self, raw: dict) -> dict:
        """Validate / clamp incoming params against the schema; fill defaults."""
        out = {}
        for p in self.params:
            v = raw.get(p.name, p.default)
            if p.type == "number" and v is not None:
                v = float(v)
                if p.min is not None:
                    v = max(p.min, v)
                if p.max is not None:
                    v = min(p.max, v)
            elif p.type == "bool":
                v = v.lower() in ("1", "true", "yes", "on") if isinstance(v, str) else bool(v)
            elif p.type == "text":
                v = "" if v is None else str(v)
            elif p.type == "select":
                vals = _choice_values(p.choices)
                if vals and v not in vals:
                    v = p.default
            out[p.name] = v
        return out
