"""Legacy compatibility shim.

The real implementation lives in src/pm_copilot/schema.py.
"""

from __future__ import annotations

import os
import sys

_repo_root = os.path.dirname(__file__)
_src_path = os.path.join(_repo_root, "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from pm_copilot.schema import CONTRACT_SCHEMA, normalize_and_validate, normalize_partial  # noqa: F401

__all__ = [
    "CONTRACT_SCHEMA",
    "normalize_and_validate",
    "normalize_partial",
]
