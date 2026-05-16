"""SQLite persistence for workflow runs.

Stores inputs/outputs + trace for debuggability and automation readiness.
"""

from __future__ import annotations

import json
import sqlite3
import time
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
"""


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


class SQLiteRunStore:
    def __init__(self, db_path: str):
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def init(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA_SQL)

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
    ) -> None:
        self.init()
        created = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                  run_id, created_at_unix, provider, model, base_url, status,
                  input_text, output_json, errors_json, warnings_json, trace_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        self.init()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT run_id, created_at_unix, provider, model, base_url, status,
                       input_text, output_json, errors_json, warnings_json, trace_json
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
        )

    def list_runs(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        self.init()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT run_id, created_at_unix, provider, model, status
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
            }
            for r in rows
        ]
