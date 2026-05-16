"""Output contract schema and validation.

Keep this module dependency-free so it can be reused across CLI, LangGraph, and tests.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


CONTRACT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "tasks", "risks", "followups"],
    "properties": {
        "summary": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["title", "description"],
                "properties": {
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "owner": {"type": ["string", "null"]},
                    "due_date": {"type": ["string", "null"], "description": "ISO date (YYYY-MM-DD) when known"},
                    "status": {"type": ["string", "null"], "description": "e.g., todo/in_progress/done/blocked"},
                    "priority": {"type": ["string", "null"], "description": "e.g., low/medium/high"},
                    "dependencies": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["description"],
                "properties": {
                    "description": {"type": "string"},
                    "severity": {"type": ["string", "null"], "description": "low/medium/high"},
                    "likelihood": {"type": ["string", "null"], "description": "low/medium/high"},
                    "impact": {"type": ["string", "null"]},
                    "mitigation": {"type": ["string", "null"]},
                    "owner": {"type": ["string", "null"]},
                },
            },
        },
        "followups": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": True,
                "required": ["message"],
                "properties": {
                    "message": {"type": "string"},
                    "to": {"type": ["string", "null"], "description": "person/team to follow up with"},
                    "channel": {"type": ["string", "null"], "description": "e.g., slack/email/jira"},
                    "due_date": {"type": ["string", "null"], "description": "ISO date (YYYY-MM-DD) when known"},
                },
            },
        },
    },
}


def _ensure_str(value: Any, field: str) -> str:
    if isinstance(value, str):
        return value
    raise ValueError(f"{field} must be a string")


def _ensure_optional_str(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise ValueError(f"{field} must be a string or null")


def _ensure_list(value: Any, field: str) -> List[Any]:
    if isinstance(value, list):
        return value
    raise ValueError(f"{field} must be a list")


def normalize_and_validate(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce missing fields to defaults and validate basic types."""

    out: Dict[str, Any] = {}
    out["summary"] = _ensure_str(obj.get("summary", ""), "summary")

    tasks_raw = obj.get("tasks", [])
    risks_raw = obj.get("risks", [])
    followups_raw = obj.get("followups", [])

    tasks: List[Dict[str, Any]] = []
    for i, t in enumerate(_ensure_list(tasks_raw, "tasks")):
        if not isinstance(t, dict):
            raise ValueError(f"tasks[{i}] must be an object")
        title = _ensure_str(t.get("title"), f"tasks[{i}].title")
        desc = _ensure_str(t.get("description"), f"tasks[{i}].description")
        deps = t.get("dependencies", [])
        deps_list = _ensure_list(deps, f"tasks[{i}].dependencies")
        deps_norm = []
        for j, d in enumerate(deps_list):
            if not isinstance(d, str):
                raise ValueError(f"tasks[{i}].dependencies[{j}] must be a string")
            deps_norm.append(d)

        tasks.append(
            {
                "title": title,
                "description": desc,
                "owner": _ensure_optional_str(t.get("owner", None), f"tasks[{i}].owner"),
                "due_date": _ensure_optional_str(t.get("due_date", None), f"tasks[{i}].due_date"),
                "status": _ensure_optional_str(t.get("status", None), f"tasks[{i}].status"),
                "priority": _ensure_optional_str(t.get("priority", None), f"tasks[{i}].priority"),
                "dependencies": deps_norm,
            }
        )

    risks: List[Dict[str, Any]] = []
    for i, r in enumerate(_ensure_list(risks_raw, "risks")):
        if not isinstance(r, dict):
            raise ValueError(f"risks[{i}] must be an object")
        risks.append(
            {
                "description": _ensure_str(r.get("description"), f"risks[{i}].description"),
                "severity": _ensure_optional_str(r.get("severity", None), f"risks[{i}].severity"),
                "likelihood": _ensure_optional_str(r.get("likelihood", None), f"risks[{i}].likelihood"),
                "impact": _ensure_optional_str(r.get("impact", None), f"risks[{i}].impact"),
                "mitigation": _ensure_optional_str(r.get("mitigation", None), f"risks[{i}].mitigation"),
                "owner": _ensure_optional_str(r.get("owner", None), f"risks[{i}].owner"),
            }
        )

    followups: List[Dict[str, Any]] = []
    for i, f in enumerate(_ensure_list(followups_raw, "followups")):
        if not isinstance(f, dict):
            raise ValueError(f"followups[{i}] must be an object")
        followups.append(
            {
                "message": _ensure_str(f.get("message"), f"followups[{i}].message"),
                "to": _ensure_optional_str(f.get("to", None), f"followups[{i}].to"),
                "channel": _ensure_optional_str(f.get("channel", None), f"followups[{i}].channel"),
                "due_date": _ensure_optional_str(f.get("due_date", None), f"followups[{i}].due_date"),
            }
        )

    out["tasks"] = tasks
    out["risks"] = risks
    out["followups"] = followups

    return out


def normalize_partial(
    *,
    summary: Optional[str] = None,
    tasks: Optional[List[Dict[str, Any]]] = None,
    risks: Optional[List[Dict[str, Any]]] = None,
    followups: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return normalize_and_validate(
        {
            "summary": summary if summary is not None else "",
            "tasks": tasks if tasks is not None else [],
            "risks": risks if risks is not None else [],
            "followups": followups if followups is not None else [],
        }
    )
