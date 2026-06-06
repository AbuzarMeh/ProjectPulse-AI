from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class NormalizedUpdate:
    """Normalized project update payload.

    This is the common interface produced by all ingestion adapters.

    Notes:
    - `external_event_id` should be stable for retry/idempotency (e.g., Slack ts or message id).
    - `project_key` is an optional routing key for longitudinal grouping (e.g., "acme-web").
    """

    source: str  # slack|discord|file|manual|...
    text: str

    external_event_id: Optional[str] = None
    channel: Optional[str] = None
    user: Optional[str] = None
    timestamp: Optional[str] = None  # external timestamp string if available

    project_key: Optional[str] = None

    raw: Optional[Dict[str, Any]] = None
