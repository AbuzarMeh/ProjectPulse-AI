"""Phase 3: LangGraph Stateful Orchestration.

Workflow:
  START → Summary Node → Task Node → [Tasks Empty?] → Risk Node → Followup Node → END

State flows through all nodes, enabling:
- Centralized state management
- Conditional routing
- Retry handling
- Graceful error management
"""

from __future__ import annotations

import json
import re
import time
import uuid
import warnings
from datetime import datetime, timezone
from typing import Any, Dict, List, TypedDict

# typing-only imports for older Python versions
try:  # pragma: no cover
    from typing import Any as _Any
except Exception:  # pragma: no cover
    pass

try:  # Best-effort: keep demo/CLI output clean
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except Exception:
    warnings.filterwarnings(
        "ignore",
        message=r"The default value of `allowed_objects` will change in a future version\..*",
        category=Warning,
    )

from langgraph.graph import END, StateGraph

from pm_copilot.schema import normalize_partial


_SECTION_HEADER_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /&_-]{2,})(?:\s*\(.*\))?\s*:\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.*\S)\s*$")


def _extract_section_items(text: str, *, section_keywords: List[str]) -> List[Dict[str, str]]:
    """Extract bullet/numbered items from matching sections.

    This is a deterministic fallback to avoid empty outputs when an LLM call fails.
    """
    keywords = [k.lower() for k in section_keywords]
    items: List[Dict[str, str]] = []

    current_section: str | None = None
    in_target_section = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\n")
        header_m = _SECTION_HEADER_RE.match(line)
        if header_m:
            current_section = header_m.group(1).strip()
            sec_lower = current_section.lower()
            in_target_section = any(k in sec_lower for k in keywords)
            continue

        if not in_target_section:
            continue

        bullet_m = _BULLET_RE.match(line)
        numbered_m = _NUMBERED_RE.match(line)
        content = (bullet_m.group(1) if bullet_m else (numbered_m.group(1) if numbered_m else "")).strip()
        if not content:
            continue

        # Normalize trailing punctuation
        content = content.rstrip(" .;:")
        items.append({"section": current_section or "", "text": content})

    return items


def _heuristic_tasks_from_text(text: str) -> List[Dict[str, Any]]:
    action_items = _extract_section_items(
        text,
        section_keywords=[
            "immediate actions",
            "follow-up actions",
            "follow up actions",
            "followups",
            "immediate fixes",
            "committed items",
            "actions",
        ],
    )

    tasks: List[Dict[str, Any]] = []
    for it in action_items:
        title = it["text"]
        desc = f"From {it['section']}".strip() if it.get("section") else ""
        tasks.append(
            {
                "title": title,
                "description": desc,
                "owner": None,
                "due_date": None,
                "status": None,
                "priority": None,
                "dependencies": [],
            }
        )

    return tasks


def _heuristic_risks_from_text(text: str) -> List[Dict[str, Any]]:
    risk_items = _extract_section_items(text, section_keywords=["risks", "blockers"]) 

    risks: List[Dict[str, Any]] = []
    for it in risk_items:
        risks.append(
            {
                "description": it["text"],
                "severity": None,
                "likelihood": None,
                "impact": None,
                "mitigation": None,
                "owner": None,
            }
        )

    return risks


class ProjectState(TypedDict):
    """Centralized state object flowing through all workflow nodes."""

    # Raw Input
    input_text: str

    # Agent Outputs
    summary: str
    tasks: List[Dict[str, Any]]
    risks: List[Dict[str, Any]]
    followups: List[Dict[str, Any]]

    # Workflow Metadata
    current_step: str
    status: str

    # Observability / Debugging
    errors: List[str]
    warnings: List[str]

    # Retry Tracking
    retry_counts: Dict[str, int]

    # LLM Configuration
    provider: str
    model: str
    base_url: str
    timeout_s: int
    max_tokens: int
    max_attempts: int
    allow_repair: bool

    # Future extensibility
    metadata: Dict[str, Any]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace(state: ProjectState, event: str, **data: Any) -> None:
    meta = state.get("metadata") or {}
    trace = meta.setdefault("trace", [])
    trace.append(
        {
            "ts": _utc_now_iso(),
            "event": event,
            "step": state.get("current_step"),
            "status": state.get("status"),
            "data": data,
        }
    )
    state["metadata"] = meta


def _initialize_state(
    input_text: str,
    provider: str,
    model: str,
    base_url: str,
    timeout_s: int,
    max_tokens: int,
    max_attempts: int,
    allow_repair: bool,
) -> ProjectState:
    """Initialize workflow state."""
    run_id = str(uuid.uuid4())
    state = ProjectState(
        input_text=input_text,
        summary="",
        tasks=[],
        risks=[],
        followups=[],
        current_step="init",
        status="pending",
        errors=[],
        warnings=[],
        retry_counts={},
        provider=provider,
        model=model,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
        metadata={"run_id": run_id, "started_at": _utc_now_iso(), "trace": []},
    )
    _trace(state, "workflow_init", provider=provider, model=model)
    return state


def node_summary(state: ProjectState) -> ProjectState:
    """Summary node: extract summary from input."""
    state["current_step"] = "summary"
    _trace(state, "node_start", node="summary")
    t0 = time.monotonic()
    try:
        from pm_copilot.agents.runner import run_json_agent
        from pm_copilot.prompts import SUMMARY_AGENT_PROMPT

        result = run_json_agent(
            system_prompt=SUMMARY_AGENT_PROMPT,
            user_content=state["input_text"],
            expected_contract='{"summary": string}',
            provider=state["provider"],
            model=state["model"],
            base_url=state["base_url"],
            timeout_s=state["timeout_s"],
            max_tokens=state["max_tokens"],
            max_attempts=state["max_attempts"],
            allow_repair=state["allow_repair"],
        )
        state["summary"] = result.get("summary", "")
        state["status"] = "summary_complete"
        _trace(state, "node_end", node="summary", elapsed_ms=int((time.monotonic() - t0) * 1000))
    except Exception as e:
        state["errors"].append(f"Summary node failed: {str(e)}")
        state["status"] = "summary_failed"
        _trace(state, "node_error", node="summary", error=str(e))

    return state


def node_tasks(state: ProjectState) -> ProjectState:
    """Tasks node: extract actionable tasks from input."""
    state["current_step"] = "tasks"
    _trace(state, "node_start", node="tasks")
    t0 = time.monotonic()
    try:
        from pm_copilot.agents.runner import run_json_agent
        from pm_copilot.prompts import TASKS_AGENT_PROMPT

        def _validate_tasks(obj: Dict[str, Any]) -> None:
            # Will raise if structure is invalid (triggers repair loop)
            normalize_partial(tasks=obj.get("tasks", []))

        result = run_json_agent(
            system_prompt=TASKS_AGENT_PROMPT,
            user_content=state["input_text"],
            expected_contract=(
                '{"tasks": ['
                '{"title": string, "description": string, '
                '"owner": string|null, "due_date": string|null, '
                '"status": string|null, "priority": string|null, '
                '"dependencies": array}'
                ']}'
            ),
            provider=state["provider"],
            model=state["model"],
            base_url=state["base_url"],
            timeout_s=state["timeout_s"],
            max_tokens=state["max_tokens"],
            max_attempts=state["max_attempts"],
            allow_repair=state["allow_repair"],
            validate_fn=_validate_tasks,
        )
        tasks = normalize_partial(tasks=result.get("tasks", [])).get("tasks", [])

        if not tasks:
            fallback = _heuristic_tasks_from_text(state["input_text"])
            if fallback:
                state["warnings"].append("LLM returned no tasks; using heuristic task extraction")
                tasks = fallback
                state["status"] = "tasks_fallback"
            else:
                state["warnings"].append("No tasks extracted")
                state["status"] = "tasks_complete"
        else:
            state["status"] = "tasks_complete"

        state["tasks"] = tasks
        _trace(
            state,
            "node_end",
            node="tasks",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            tasks_count=len(tasks),
        )

    except Exception as e:
        state["errors"].append(f"Tasks node failed: {str(e)}")
        _trace(state, "node_error", node="tasks", error=str(e))

        fallback = _heuristic_tasks_from_text(state["input_text"])
        if fallback:
            state["warnings"].append("Tasks LLM failed; using heuristic task extraction")
            state["tasks"] = fallback
            state["status"] = "tasks_fallback"
        else:
            state["status"] = "tasks_failed"

    return state


def _should_continue_to_risks(state: ProjectState) -> str:
    """Conditional routing: skip risks if tasks are empty."""
    if not state["tasks"]:
        state["warnings"].append("No tasks extracted; skipping risk analysis")
        return "end"
    return "risks"


def node_risks(state: ProjectState) -> ProjectState:
    """Risks node: identify blockers, dependencies, risks and generate followups."""
    state["current_step"] = "risks"
    _trace(state, "node_start", node="risks")
    t0 = time.monotonic()
    try:
        from pm_copilot.agents.runner import run_json_agent
        from pm_copilot.prompts import RISKS_AGENT_PROMPT

        import textwrap

        risks_input = textwrap.dedent(
            f"""\
            Raw project update:
            ---
            {state['input_text'].strip()}
            ---

            Context (from other agents):
            Summary: {state['summary']}
            Extracted tasks (JSON): {json.dumps(state['tasks'], ensure_ascii=False)}
            """
        ).strip()

        def _validate_risks(obj: Dict[str, Any]) -> None:
            normalize_partial(risks=obj.get("risks", []), followups=obj.get("followups", []))

        result = run_json_agent(
            system_prompt=RISKS_AGENT_PROMPT,
            user_content=risks_input,
            expected_contract=(
                '{"risks": ['
                '{"description": string, "severity": string|null, "likelihood": string|null, '
                '"impact": string|null, "mitigation": string|null, "owner": string|null}'
                '], '
                '"followups": ['
                '{"message": string, "to": string|null, "channel": string|null, "due_date": string|null}'
                ']}'
            ),
            provider=state["provider"],
            model=state["model"],
            base_url=state["base_url"],
            timeout_s=state["timeout_s"],
            max_tokens=state["max_tokens"],
            max_attempts=state["max_attempts"],
            allow_repair=state["allow_repair"],
            validate_fn=_validate_risks,
        )

        normalized = normalize_partial(
            risks=result.get("risks", []),
            followups=result.get("followups", []),
        )
        risks = normalized.get("risks", [])
        followups = normalized.get("followups", [])

        if not risks:
            fallback_risks = _heuristic_risks_from_text(state["input_text"])
            if fallback_risks:
                state["warnings"].append("LLM returned no risks; using heuristic risk extraction")
                risks = fallback_risks
                state["status"] = "risks_fallback"

        state["risks"] = risks
        state["followups"] = followups
        if state.get("status") not in ("risks_fallback",):
            state["status"] = "risks_complete"

        _trace(
            state,
            "node_end",
            node="risks",
            elapsed_ms=int((time.monotonic() - t0) * 1000),
            risks_count=len(risks),
            followups_count=len(followups),
        )

    except Exception as e:
        state["errors"].append(f"Risks node failed: {str(e)}")
        _trace(state, "node_error", node="risks", error=str(e))

        fallback_risks = _heuristic_risks_from_text(state["input_text"])
        if fallback_risks:
            state["warnings"].append("Risks LLM failed; using heuristic risk extraction")
            state["risks"] = fallback_risks
            state["followups"] = []
            state["status"] = "risks_fallback"
        else:
            state["status"] = "risks_failed"

    return state


def _build_graph() -> StateGraph:
    """Build the LangGraph StateGraph."""
    graph = StateGraph(ProjectState)

    # Add nodes
    graph.add_node("summary", node_summary)
    graph.add_node("tasks", node_tasks)
    graph.add_node("risks", node_risks)

    # Define edges
    graph.add_edge("summary", "tasks")

    # Conditional edge: skip risks if tasks are empty
    graph.add_conditional_edges(
        "tasks",
        _should_continue_to_risks,
        {"risks": "risks", "end": END},
    )

    # After risks, end
    graph.add_edge("risks", END)

    # Set entry point
    graph.set_entry_point("summary")

    return graph


def orchestrate(
    input_text: str,
    provider: str,
    model: str,
    base_url: str,
    timeout_s: int = 120,
    max_tokens: int = 512,
    max_attempts: int = 2,
    allow_repair: bool = True,
) -> Dict[str, Any]:
    """Execute the workflow using LangGraph orchestration.

    Returns only the normalized output contract.
    """
    debug = orchestrate_debug(
        input_text=input_text,
        provider=provider,
        model=model,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
    )
    return debug["output"]


def orchestrate_debug(
    input_text: str,
    provider: str,
    model: str,
    base_url: str | None,
    timeout_s: int = 120,
    max_tokens: int = 512,
    max_attempts: int = 2,
    allow_repair: bool = True,
) -> Dict[str, Any]:
    """Execute the workflow and return output + debug metadata.

    This is intended for API/persistence/observability layers.
    """
    # Initialize state
    state = _initialize_state(
        input_text=input_text,
        provider=provider,
        model=model,
        base_url=base_url or "",
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
    )

    # Build and compile graph
    graph_def = _build_graph()
    graph = graph_def.compile()

    # Execute workflow
    final_state = graph.invoke(state)
    _trace(final_state, "workflow_end")

    output = normalize_partial(
        summary=final_state.get("summary", ""),
        tasks=final_state.get("tasks", []),
        risks=final_state.get("risks", []),
        followups=final_state.get("followups", []),
    )

    meta = final_state.get("metadata") or {}
    return {
        "run_id": meta.get("run_id", ""),
        "status": final_state.get("status", "unknown"),
        "errors": final_state.get("errors", []),
        "warnings": final_state.get("warnings", []),
        "trace": meta.get("trace", []),
        "output": output,
    }


# Optional: inspect graph structure for debugging
def visualize_graph_structure() -> str:
    """Return ASCII representation of graph structure (for debugging)."""
    return """
    Graph Structure (Phase 3):

    START
      ↓
    [Summary Node]
      ↓
    [Tasks Node]
      ↓
    [Conditional: Tasks Empty?]
      ├── YES → END
      └── NO
           ↓
         [Risks Node]
           ↓
         END
    """
