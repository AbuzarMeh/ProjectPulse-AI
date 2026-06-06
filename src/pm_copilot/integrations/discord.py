from __future__ import annotations

from typing import Any, Dict, Optional

from .types import NormalizedUpdate


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    return None


def normalize_discord_payload(payload: Dict[str, Any], *, project_key: Optional[str] = None) -> NormalizedUpdate:
    """Normalize Discord webhook payloads.

    Supports best-effort parsing for common Discord webhook shapes:
    - Standard message webhook: {"content": "...", "id": "...", "channel_id": "...", "author": {...}}

    Returns a NormalizedUpdate with `source="discord"`.
    """

    content = _as_str(payload.get("content"))
    if content:
        author = payload.get("author")
        user = None
        if isinstance(author, dict):
            user = _as_str(author.get("username")) or _as_str(author.get("id"))

        return NormalizedUpdate(
            source="discord",
            text=content,
            external_event_id=_as_str(payload.get("id")) or _as_str(payload.get("message_id")),
            channel=_as_str(payload.get("channel_id")) or _as_str(payload.get("channel")),
            user=user,
            timestamp=_as_str(payload.get("timestamp")) or _as_str(payload.get("ts")),
            project_key=project_key,
            raw=payload,
        )

    # Fallback for alternative payload names
    for key in ("text", "message"):
        content = _as_str(payload.get(key))
        if content:
            return NormalizedUpdate(source="discord", text=content, project_key=project_key, raw=payload)

    raise ValueError("Unsupported Discord payload: could not locate a content field")
