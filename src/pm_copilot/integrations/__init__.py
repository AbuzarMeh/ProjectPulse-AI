"""Ingestion integrations.

Integrations are responsible for converting external payloads (Slack/Discord/etc.)
into a normalized update payload.

Important: this package must not depend on orchestration/LLM code.
"""

from .types import NormalizedUpdate
from .slack import normalize_slack_payload
from .discord import normalize_discord_payload
from .file_ingest import normalize_file_text

__all__ = [
    "NormalizedUpdate",
    "normalize_slack_payload",
    "normalize_discord_payload",
    "normalize_file_text",
]
