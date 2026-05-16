"""FastAPI service layer for pm_copilot.

Minimal endpoints for automation tools (n8n) + debugging.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel, Field
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "FastAPI service requires 'fastapi' and 'pydantic'. Install with: pip install fastapi uvicorn"
    ) from e

from pm_copilot.orchestration.langgraph_flow import orchestrate_debug
from pm_copilot.store_sqlite import SQLiteRunStore


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1)

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


def create_app() -> FastAPI:
    app = FastAPI(title="pm_copilot", version="0.1")

    db_path = os.environ.get("PM_COPILOT_DB_PATH", "pm_copilot.sqlite3")
    store = SQLiteRunStore(db_path=db_path)

    @app.get("/health")
    def health() -> Dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze", response_model=AnalyzeResponse)
    def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
        try:
            result = orchestrate_debug(
                input_text=req.text,
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
                    input_text=req.text,
                    output=result.get("output", {}),
                    errors=result.get("errors", []),
                    warnings=result.get("warnings", []),
                    trace=result.get("trace", []),
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

    @app.get("/runs")
    def list_runs(limit: int = 50) -> List[Dict[str, Any]]:
        return store.list_runs(limit=limit)

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
        }

    return app


app = create_app()
