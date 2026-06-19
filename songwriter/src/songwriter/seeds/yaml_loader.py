from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected top-level mapping, got {type(data).__name__}")
    return data


def load_all_in(directory: Path) -> list[dict]:
    """Recursively load all .yml/.yaml files in directory, return list of dicts."""
    out = []
    for ext in ("*.yml", "*.yaml"):
        for p in sorted(directory.rglob(ext)):
            out.append(load_yaml(p))
    return out


def require_keys(data: dict, keys: list[str], *, context: str) -> None:
    missing = [k for k in keys if k not in data]
    if missing:
        raise ValueError(f"{context}: missing required keys: {missing}")
