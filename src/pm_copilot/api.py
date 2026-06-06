"""FastAPI service layer for pm_copilot.

Minimal endpoints for automation tools (n8n) + debugging.
"""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

try:
    from fastapi import Body, FastAPI, HTTPException
    from pydantic import BaseModel, Field
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "FastAPI service requires 'fastapi' and 'pydantic'. Install with: pip install fastapi uvicorn"
    ) from e

from pm_copilot.orchestration.langgraph_flow import orchestrate_debug
from pm_copilot.integrations import normalize_discord_payload, normalize_slack_payload
from pm_copilot.store_sqlite import SQLiteRunStore


class AnalyzeRequest(BaseModel):
    # One of (text, update_id) is required.
    text: Optional[str] = None
    update_id: Optional[str] = None

    project_key: Optional[str] = None
    request_id: Optional[str] = None  # client-provided idempotency key

    provider: str = "ollama"  # ollama|groq
    model: str = "phi3:latest"
    base_url: Optional[str] = None

    timeout_s: int = 120
    max_tokens: int = 512
    max_attempts: int = 2
    allow_repair: bool = True

    persist: bool = True


class AnalyzeResponse(BaseModel):
    run_id: str
    status: str
    output: Dict[str, Any]
    errors: List[str]
    warnings: List[str]


class AnalyzeDebugResponse(AnalyzeResponse):
    trace: List[Dict[str, Any]]


class IngestResponse(BaseModel):
    update_id: str
    source: str
    external_event_id: Optional[str] = None
    project_key: Optional[str] = None
    text: str


def create_app() -> FastAPI:
    app = FastAPI(title="pm_copilot", version="0.1")

    db_path = os.environ.get("PM_COPILOT_DB_PATH", "pm_copilot.sqlite3")
    store = SQLiteRunStore(db_path=db_path)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    def _resolve_text(req: AnalyzeRequest) -> str:
        if req.text and req.text.strip():
            return req.text
        if req.update_id:
            rec = store.get_update(req.update_id)
            if rec is None:
                raise HTTPException(status_code=404, detail="update not found")
            return rec.text
        raise HTTPException(status_code=422, detail="One of 'text' or 'update_id' is required")

    def _resolve_request_id(req: AnalyzeRequest) -> str:
        rid = (req.request_id or "").strip()
        return rid or str(uuid.uuid4())

    @app.post("/analyze", response_model=AnalyzeResponse)
    def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
        # Idempotency: if a request_id was already processed, return the last run.
        request_id = _resolve_request_id(req)
        existing = store.get_run_by_request_id(request_id)
        if existing is not None:
            return AnalyzeResponse(
                run_id=existing.run_id,
                status=existing.status,
                output=existing.output,
                errors=existing.errors,
                warnings=existing.warnings,
            )

        input_text = _resolve_text(req)

        try:
            result = orchestrate_debug(
                input_text=input_text,
                provider=req.provider,
                model=req.model,
                base_url=req.base_url,
                timeout_s=req.timeout_s,
                max_tokens=req.max_tokens,
                max_attempts=req.max_attempts,
                allow_repair=req.allow_repair,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        if req.persist:
            try:
                store.save_run(
                    run_id=result["run_id"],
                    provider=req.provider,
                    model=req.model,
                    base_url=(req.base_url or ""),
                    status=result.get("status", "unknown"),
                    input_text=input_text,
                    output=result.get("output", {}),
                    errors=result.get("errors", []),
                    warnings=result.get("warnings", []),
                    trace=result.get("trace", []),
                    update_id=req.update_id,
                    project_key=req.project_key,
                    request_id=request_id,
                )
            except Exception as e:
                # Don't fail the request if persistence fails
                result.setdefault("warnings", []).append(f"Persistence failed: {e}")

        return AnalyzeResponse(
            run_id=result["run_id"],
            status=result.get("status", "unknown"),
            output=result.get("output", {}),
            errors=result.get("errors", []),
            warnings=result.get("warnings", []),
        )

    @app.post("/analyze/debug", response_model=AnalyzeDebugResponse)
    def analyze_debug(req: AnalyzeRequest) -> AnalyzeDebugResponse:
        request_id = _resolve_request_id(req)
        existing = store.get_run_by_request_id(request_id)
        if existing is not None:
            return AnalyzeDebugResponse(
                run_id=existing.run_id,
                status=existing.status,
                output=existing.output,
                errors=existing.errors,
                warnings=existing.warnings,
                trace=existing.trace,
            )

        input_text = _resolve_text(req)
        try:
            result = orchestrate_debug(
                input_text=input_text,
                provider=req.provider,
                model=req.model,
                base_url=req.base_url,
                timeout_s=req.timeout_s,
                max_tokens=req.max_tokens,
                max_attempts=req.max_attempts,
                allow_repair=req.allow_repair,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        if req.persist:
            try:
                store.save_run(
                    run_id=result["run_id"],
                    provider=req.provider,
                    model=req.model,
                    base_url=(req.base_url or ""),
                    status=result.get("status", "unknown"),
                    input_text=input_text,
                    output=result.get("output", {}),
                    errors=result.get("errors", []),
                    warnings=result.get("warnings", []),
                    trace=result.get("trace", []),
                    update_id=req.update_id,
                    project_key=req.project_key,
                    request_id=request_id,
                )
            except Exception as e:
                result.setdefault("warnings", []).append(f"Persistence failed: {e}")

        return AnalyzeDebugResponse(
            run_id=result["run_id"],
            status=result.get("status", "unknown"),
            output=result.get("output", {}),
            errors=result.get("errors", []),
            warnings=result.get("warnings", []),
            trace=result.get("trace", []),
        )

    @app.post("/ingest/slack/webhook", response_model=IngestResponse)
    def ingest_slack_webhook(
        payload: Dict[str, Any] = Body(...),
        project_key: Optional[str] = None,
        persist: bool = True,
    ) -> IngestResponse:
        try:
            normalized = normalize_slack_payload(payload, project_key=project_key)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        update_id = ""
        if persist:
            try:
                update_id = store.save_update(
                    source=normalized.source,
                    text=normalized.text,
                    external_event_id=normalized.external_event_id,
                    project_key=normalized.project_key,
                    channel=normalized.channel,
                    user=normalized.user,
                    timestamp=normalized.timestamp,
                    raw=normalized.raw,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Persistence failed: {e}")
        else:
            update_id = str(uuid.uuid4())

        return IngestResponse(
            update_id=update_id,
            source=normalized.source,
            external_event_id=normalized.external_event_id,
            project_key=normalized.project_key,
            text=normalized.text,
        )

    @app.post("/ingest/discord/webhook", response_model=IngestResponse)
    def ingest_discord_webhook(
        payload: Dict[str, Any] = Body(...),
        project_key: Optional[str] = None,
        persist: bool = True,
    ) -> IngestResponse:
        try:
            normalized = normalize_discord_payload(payload, project_key=project_key)
        except Exception as e:
            raise HTTPException(status_code=422, detail=str(e))

        update_id = ""
        if persist:
            try:
                update_id = store.save_update(
                    source=normalized.source,
                    text=normalized.text,
                    external_event_id=normalized.external_event_id,
                    project_key=normalized.project_key,
                    channel=normalized.channel,
                    user=normalized.user,
                    timestamp=normalized.timestamp,
                    raw=normalized.raw,
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Persistence failed: {e}")
        else:
            update_id = str(uuid.uuid4())

        return IngestResponse(
            update_id=update_id,
            source=normalized.source,
            external_event_id=normalized.external_event_id,
            project_key=normalized.project_key,
            text=normalized.text,
        )

    @app.get("/runs")
    def list_runs(limit: int = 50, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        return store.list_runs(limit=limit, project_key=project_key)

    @app.get("/runs/{run_id}")
    def get_run(run_id: str) -> Dict[str, Any]:
        rec = store.get_run(run_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="run not found")
        return {
            "run_id": rec.run_id,
            "created_at_unix": rec.created_at_unix,
            "provider": rec.provider,
            "model": rec.model,
            "base_url": rec.base_url,
            "status": rec.status,
            "input_text": rec.input_text,
            "output": rec.output,
            "errors": rec.errors,
            "warnings": rec.warnings,
            "trace": rec.trace,
            "update_id": rec.update_id,
            "project_key": rec.project_key,
            "request_id": rec.request_id,
        }

    @app.get("/updates")
    def list_updates(limit: int = 50, project_key: Optional[str] = None) -> List[Dict[str, Any]]:
        return store.list_updates(limit=limit, project_key=project_key)

    @app.get("/updates/{update_id}")
    def get_update(update_id: str) -> Dict[str, Any]:
        rec = store.get_update(update_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="update not found")
        return {
            "update_id": rec.update_id,
            "created_at_unix": rec.created_at_unix,
            "source": rec.source,
            "external_event_id": rec.external_event_id,
            "project_key": rec.project_key,
            "channel": rec.channel,
            "user": rec.user,
            "timestamp": rec.timestamp,
            "text": rec.text,
            "raw": rec.raw,
        }

    return app


app = create_app()
