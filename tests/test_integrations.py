"""Integration adapter + store idempotency sanity tests.

Run:
  python tests\test_integrations.py
"""

from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pm_copilot.integrations import normalize_discord_payload, normalize_slack_payload
from pm_copilot.store_sqlite import SQLiteRunStore


def test_slack_incoming_webhook() -> None:
    upd = normalize_slack_payload({"text": "Hello from Slack"}, project_key="demo")
    assert upd.source == "slack"
    assert upd.text == "Hello from Slack"
    assert upd.project_key == "demo"


def test_slack_events_api() -> None:
    payload = {
        "event_id": "Ev123",
        "event": {"text": "Update", "ts": "1710000000.0001", "channel": "C1", "user": "U1"},
    }
    upd = normalize_slack_payload(payload)
    assert upd.source == "slack"
    assert upd.text == "Update"
    assert upd.channel == "C1"
    assert upd.user == "U1"


def test_discord_webhook() -> None:
    payload = {"content": "Hello from Discord", "id": "m1", "channel_id": "c1", "author": {"username": "alice"}}
    upd = normalize_discord_payload(payload, project_key="demo")
    assert upd.source == "discord"
    assert upd.text == "Hello from Discord"
    assert upd.external_event_id == "m1"
    assert upd.user == "alice"
    assert upd.project_key == "demo"


def test_store_update_idempotency() -> None:
    with tempfile.TemporaryDirectory() as td:
        db_path = os.path.join(td, "test.sqlite3")
        store = SQLiteRunStore(db_path=db_path)
        first = store.save_update(source="slack", text="x", external_event_id="E1", raw={"text": "x"})
        second = store.save_update(source="slack", text="x", external_event_id="E1", raw={"text": "x"})
        assert first == second
        rec = store.get_update(first)
        assert rec is not None
        assert rec.external_event_id == "E1"


def main() -> int:
    test_slack_incoming_webhook()
    test_slack_events_api()
    test_discord_webhook()
    test_store_update_idempotency()
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
