"""
features/base.py — the feature-module contract.

Every AI feature (relief, text2img, img2img, upscale, …) is a `Feature` subclass:
declarative metadata (id / name / description), a typed param schema the UI can
render generically, and a single `run(inputs, params, out_dir) -> {name: path}`.

Adding a feature = drop a new module in `features/` and register it in
`features/__init__.py`. Nothing else in the app needs to change — the API and
(eventually) the frontend enumerate the registry and render from the schema.
"""
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class ParamSpec:
    """One UI-renderable parameter. `type`: 'number' | 'bool' | 'select'."""
    name: str
    type: str
    default: Any = None
    label: str = ""
    min: float = None
    max: float = None
    step: float = None
    choices: list = None

    def as_dict(self):
        return asdict(self)


class Feature:
    id: str = ""
    name: str = ""
    description: str = ""
    inputs: list = ["image"]        # input kinds the UI should collect, e.g. ["image"] | ["text"]
    params: list = []               # list[ParamSpec]

    def run(self, inputs: dict, params: dict, out_dir: Path) -> dict:
        """inputs: {kind: value} (e.g. {'image': '/path.png'} or {'text': '…'}).
        params: coerced param dict. Returns {artifact_name: filesystem_path}."""
        raise NotImplementedError

    # ---- shared helpers (the API + UI use these; features don't override) ----
    def schema(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "inputs": self.inputs, "params": [p.as_dict() for p in self.params]}

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
            elif p.type == "select" and p.choices and v not in p.choices:
                v = p.default
            out[p.name] = v
        return out
