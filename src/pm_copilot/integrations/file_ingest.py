from __future__ import annotations

from typing import Optional

from .types import NormalizedUpdate


def normalize_file_text(text: str, *, file_name: Optional[str] = None, project_key: Optional[str] = None) -> NormalizedUpdate:
    t = (text or "").strip()
    if not t:
        raise ValueError("No text provided")

    external_id = None
    if file_name:
        external_id = f"file:{file_name}"

    return NormalizedUpdate(
        source="file",
        text=t,
        external_event_id=external_id,
        project_key=project_key,
        raw={"file_name": file_name} if file_name else None,
    )
