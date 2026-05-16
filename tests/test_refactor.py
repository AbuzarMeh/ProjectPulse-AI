"""Basic import + schema sanity tests.

Run: python -m tests.test_refactor  (or just python tests\test_refactor.py)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pm_copilot.schema import CONTRACT_SCHEMA, normalize_and_validate, normalize_partial
from pm_copilot.prompts import SYSTEM_PROMPT


def main() -> int:
    assert "properties" in CONTRACT_SCHEMA
    assert "summary" in CONTRACT_SCHEMA["properties"]

    obj = {
        "summary": "Test",
        "tasks": [{"title": "T", "description": "D"}],
        "risks": [],
        "followups": [],
    }
    normalized = normalize_and_validate(obj)
    assert normalized["summary"] == "Test"

    partial = normalize_partial(summary="X")
    assert partial["summary"] == "X"

    assert isinstance(SYSTEM_PROMPT, str) and len(SYSTEM_PROMPT) > 50
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
