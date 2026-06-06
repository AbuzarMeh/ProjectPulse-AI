"""SQLite persistence for workflow runs.

Stores inputs/outputs + trace for debuggability and automation readiness.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  created_at_unix REAL NOT NULL,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT NOT NULL,
  status TEXT NOT NULL,
  input_text TEXT NOT NULL,
  output_json TEXT NOT NULL,
  errors_json TEXT NOT NULL,
  warnings_json TEXT NOT NULL,
  trace_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at_unix);

CREATE TABLE IF NOT EXISTS updates (
    update_id TEXT PRIMARY KEY,
    created_at_unix REAL NOT NULL,
    source TEXT NOT NULL,
    external_event_id TEXT,
    project_key TEXT,
    channel TEXT,
    user TEXT,
    timestamp TEXT,
    text TEXT NOT NULL,
    raw_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_updates_created_at ON updates(created_at_unix);
CREATE INDEX IF NOT EXISTS idx_updates_external_event_id ON updates(external_event_id);
CREATE INDEX IF NOT EXISTS idx_updates_project_key ON updates(project_key);
"""


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
        return any(r[1] == column for r in rows)


def _maybe_add_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        if not _has_column(conn, table, column):
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    created_at_unix: float
    provider: str
    model: str
    base_url: str
    status: str
    input_text: str
    output: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
    trace: List[Dict[str, Any]]

    # Optional operational metadata (added via migrations)
    update_id: Optional[str] = None
    project_key: Optional[str] = None
    request_id: Optional[str] = None


@dataclass(frozen=True)
class UpdateRecord:
    update_id: str
    created_at_unix: float
    source: str
    external_event_id: Optional[str]
    project_key: Optional[str]
    channel: Optional[str]
    user: Optional[str]
    timestamp: Optional[str]
    text: str
    raw: Dict[str, Any]


class SQLiteRunStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            try:
                yield conn
                conn.commit()
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                raise
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

            # Lightweight migrations for operational metadata.
            # These are safe to run repeatedly.
            _maybe_add_column(conn, "runs", "update_id", "update_id TEXT")
            _maybe_add_column(conn, "runs", "project_key", "project_key TEXT")
            _maybe_add_column(conn, "runs", "request_id", "request_id TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_update_id ON runs(update_id);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_project_key ON runs(project_key);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_request_id ON runs(request_id);")

    def _new_id(self) -> str:
        return str(uuid.uuid4())

    # -----------------
    # Updates ingestion
    # -----------------
    def save_update(
        self,
        *,
        source: str,
        text: str,
        external_event_id: Optional[str] = None,
        project_key: Optional[str] = None,
        channel: Optional[str] = None,
        user: Optional[str] = None,
        timestamp: Optional[str] = None,
        raw: Optional[Dict[str, Any]] = None,
        update_id: Optional[str] = None,
    ) -> str:
        """Persist a normalized update.

        If `external_event_id` is provided and already exists, returns the existing update_id
        (idempotent ingestion).
        """
        self.init()
        created = time.time()
        raw_json = json.dumps(raw or {}, ensure_ascii=False)

        with self._connect() as conn:
            if external_event_id:
                existing = conn.execute(
                    "SELECT update_id FROM updates WHERE external_event_id = ? ORDER BY created_at_unix DESC LIMIT 1",
                    (external_event_id,),
                ).fetchone()
                if existing and existing[0]:
                    return str(existing[0])

            uid = update_id or self._new_id()
            conn.execute(
                """
                INSERT OR REPLACE INTO updates (
                  update_id, created_at_unix, source, external_event_id, project_key,
                  channel, user, timestamp, text, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uid,
                    created,
                    source,
                    external_event_id,
                    project_key,
                    channel,
                    user,
                    timestamp,
                    text,
                    raw_json,
                ),
            )

        return uid

    def get_update(self, update_id: str) -> Optional[UpdateRecord]:
        self.init()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT update_id, created_at_unix, source, external_event_id, project_key,
                       channel, user, timestamp, text, raw_json
                FROM updates
                WHERE update_id = ?
                """,
                (update_id,),
            ).fetchone()

        if not row:
            return None

        (
            uid,
            created,
            source,
            external_event_id,
            project_key,
            channel,
            user,
            timestamp,
            text,
            raw_json,
        ) = row

        return UpdateRecord(
            update_id=str(uid),
            created_at_unix=float(created),
            source=str(source),
            external_event_id=str(external_event_id) if external_event_id is not None else None,
            project_key=str(project_key) if project_key is not None else None,
            channel=str(channel) if channel is not None else None,
            user=str(user) if user is not None else None,
            timestamp=str(timestamp) if timestamp is not None else None,
            text=str(text),
            raw=json.loads(raw_json or "{}"),
        )

    def list_updates(self, *, limit: int = 50, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        self.init()
        with self._connect() as conn:
            if project_key:
                rows = conn.execute(
                    """
                    SELECT update_id, created_at_unix, source, external_event_id, project_key
                    FROM updates
                    WHERE project_key = ?
                    ORDER BY created_at_unix DESC
                    LIMIT ?
                    """,
                    (project_key, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT update_id, created_at_unix, source, external_event_id, project_key
                    FROM updates
                    ORDER BY created_at_unix DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()

        return [
            {
                "update_id": r[0],
                "created_at_unix": float(r[1]),
                "source": r[2],
                "external_event_id": r[3],
                "project_key": r[4],
            }
            for r in rows
        ]

    def save_run(
        self,
        *,
        run_id: str,
        provider: str,
        model: str,
        base_url: str,
        status: str,
        input_text: str,
        output: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
        trace: List[Dict[str, Any]],
        update_id: Optional[str] = None,
        project_key: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        self.init()
        created = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                  run_id, created_at_unix, provider, model, base_url, status,
                  input_text, output_json, errors_json, warnings_json, trace_json,
                  update_id, project_key, request_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    created,
                    provider,
                    model,
                    base_url,
                    status,
                    input_text,
                    json.dumps(output, ensure_ascii=False),
                    json.dumps(errors, ensure_ascii=False),
                    json.dumps(warnings, ensure_ascii=False),
                    json.dumps(trace, ensure_ascii=False),
                    update_id,
                    project_key,
                    request_id,
                ),
            )

    def get_run_by_request_id(self, request_id: str) -> Optional[RunRecord]:
        if not request_id:
            return None
        self.init()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_id
                FROM runs
                WHERE request_id = ?
                ORDER BY created_at_unix DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        if not row or not row[0]:
            return None
        return self.get_run(str(row[0]))

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        self.init()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_id, created_at_unix, provider, model, base_url, status,
                       input_text, output_json, errors_json, warnings_json, trace_json,
                       update_id, project_key, request_id
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if not row:
            return None

        (
            rid,
            created,
            provider,
            model,
            base_url,
            status,
            input_text,
            output_json,
            errors_json,
            warnings_json,
            trace_json,
            update_id,
            project_key,
            request_id,
        ) = row

        return RunRecord(
            run_id=rid,
            created_at_unix=float(created),
            provider=str(provider),
            model=str(model),
            base_url=str(base_url),
            status=str(status),
            input_text=str(input_text),
            output=json.loads(output_json or "{}"),
            errors=list(json.loads(errors_json or "[]")),
            warnings=list(json.loads(warnings_json or "[]")),
            trace=list(json.loads(trace_json or "[]")),
            update_id=str(update_id) if update_id is not None else None,
            project_key=str(project_key) if project_key is not None else None,
            request_id=str(request_id) if request_id is not None else None,
        )

    def list_runs(self, *, limit: int = 50, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        self.init()
        with self._connect() as conn:
            if project_key:
                rows = conn.execute(
                    """
                    SELECT run_id, created_at_unix, provider, model, status, project_key, update_id
                    FROM runs
                    WHERE project_key = ?
                    ORDER BY created_at_unix DESC
                    LIMIT ?
                    """,
                    (project_key, int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT run_id, created_at_unix, provider, model, status, project_key, update_id
                    FROM runs
                    ORDER BY created_at_unix DESC
                    LIMIT ?
                    """,
                    (int(limit),),
                ).fetchall()

        return [
            {
                "run_id": r[0],
                "created_at_unix": float(r[1]),
                "provider": r[2],
                "model": r[3],
                "status": r[4],
                "project_key": r[5],
                "update_id": r[6],
            }
            for r in rows
        ]
