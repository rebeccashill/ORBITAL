"""Strict JSON serialization helpers for ORBITAL artifacts."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional, Set

import numpy as np


def finite_float_or_none(value: Optional[float]) -> Optional[float]:
    """Return a JSON-safe finite float, or None for NaN and infinities."""
    if value is None:
        return None
    as_float = float(value)
    return as_float if math.isfinite(as_float) else None


def to_strict_jsonable(value: Any, *, _seen: Optional[Set[int]] = None) -> Any:
    """
    Convert common Python and NumPy values into strict JSON-safe values.

    Python's standard encoder emits NaN and Infinity by default, even though those
    tokens are not valid JSON. This helper replaces non-finite floats with null
    and lets unknown object types raise TypeError instead of silently stringifying.
    """
    if _seen is None:
        _seen = set()

    if value is None or isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, float):
        return finite_float_or_none(value)

    if isinstance(value, np.generic):
        return to_strict_jsonable(value.item(), _seen=_seen)

    if isinstance(value, np.ndarray):
        return to_strict_jsonable(value.tolist(), _seen=_seen)

    if isinstance(value, Enum):
        return to_strict_jsonable(value.value, _seen=_seen)

    if isinstance(value, (datetime, date, Path)):
        return str(value)

    if hasattr(value, "to_jsonable") and callable(value.to_jsonable):
        return to_strict_jsonable(value.to_jsonable(), _seen=_seen)

    if is_dataclass(value) and not isinstance(value, type):
        return to_strict_jsonable(asdict(value), _seen=_seen)

    container_id = id(value)
    if isinstance(value, dict):
        if container_id in _seen:
            raise TypeError("Cannot serialize recursive dictionary to JSON.")
        _seen.add(container_id)
        out: Dict[str, Any] = {}
        for key, item in value.items():
            json_key = str(key)
            if json_key in out:
                raise TypeError(f"Duplicate JSON object key after string conversion: {json_key}")
            out[json_key] = to_strict_jsonable(item, _seen=_seen)
        _seen.remove(container_id)
        return out

    if isinstance(value, (list, tuple, set)):
        if container_id in _seen:
            raise TypeError("Cannot serialize recursive sequence to JSON.")
        _seen.add(container_id)
        out_list = [to_strict_jsonable(item, _seen=_seen) for item in value]
        _seen.remove(container_id)
        return out_list

    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def strict_json_dumps(value: Any, **kwargs: Any) -> str:
    """Serialize a payload as strict JSON, rejecting any remaining non-finite values."""
    kwargs.pop("allow_nan", None)
    return json.dumps(to_strict_jsonable(value), allow_nan=False, **kwargs)


def write_strict_json(out_path: Path, value: Any, *, indent: int = 2) -> None:
    """Write strict JSON to disk, creating the parent directory if needed."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(strict_json_dumps(value, indent=indent), encoding="utf-8")
