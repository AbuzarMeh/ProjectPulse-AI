"""JSON extraction helpers for model outputs."""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        if t.strip().endswith("```"):
            t = t.strip()[: -3]
    return t.strip()


def extract_json_object(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse a JSON object from the model response.

    Returns: (obj, parse_strategy)
    """

    t = strip_code_fences(text)

    try:
        obj = json.loads(t)
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON must be an object")
        return obj, "full"
    except Exception:
        pass

    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        sliced = t[start : end + 1]
        obj = json.loads(sliced)
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON must be an object")
        return obj, "sliced"

    raise ValueError("Could not locate a JSON object in model output")
