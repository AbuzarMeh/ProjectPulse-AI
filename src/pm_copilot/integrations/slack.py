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


def normalize_slack_payload(payload: Dict[str, Any], *, project_key: Optional[str] = None) -> NormalizedUpdate:
    """Normalize Slack payloads.

    Supports best-effort parsing for:
    - Slack Incoming Webhook payloads: {"text": "...", ...}
    - Slack Events API callbacks: {"event": {"text": "...", "ts": "...", ...}, ...}

    Returns a NormalizedUpdate with `source="slack"`.
    """

    # 1) Incoming webhook style
    text = _as_str(payload.get("text"))
    if text:
        return NormalizedUpdate(
            source="slack",
            text=text,
            external_event_id=_as_str(payload.get("trigger_id")) or _as_str(payload.get("event_id")),
            channel=_as_str(payload.get("channel")) or _as_str(payload.get("channel_id")),
            user=_as_str(payload.get("user")) or _as_str(payload.get("user_id")),
            timestamp=_as_str(payload.get("ts")) or _as_str(payload.get("timestamp")),
            project_key=project_key,
            raw=payload,
        )

    # 2) Events API style
    event = payload.get("event")
    if isinstance(event, dict):
        text = _as_str(event.get("text"))
        if text:
            external_id = (
                _as_str(event.get("client_msg_id"))
                or _as_str(payload.get("event_id"))
                or _as_str(event.get("event_ts"))
                or _as_str(event.get("ts"))
            )
            return NormalizedUpdate(
                source="slack",
                text=text,
                external_event_id=external_id,
                channel=_as_str(event.get("channel")),
                user=_as_str(event.get("user")),
                timestamp=_as_str(event.get("event_ts")) or _as_str(event.get("ts")),
                project_key=project_key,
                raw=payload,
            )

    # 3) Fallback: look for common text-ish fields
    for key in ("message", "content", "body"):
        text = _as_str(payload.get(key))
        if text:
            return NormalizedUpdate(source="slack", text=text, project_key=project_key, raw=payload)

    raise ValueError("Unsupported Slack payload: could not locate a text field")
