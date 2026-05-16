"""Phase 2: multi-agent separation (Summary -> Tasks -> Risks/Followups)."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Dict

from pm_copilot.agents.runner import run_json_agent
from pm_copilot.prompts import RISKS_AGENT_PROMPT, SUMMARY_AGENT_PROMPT, TASKS_AGENT_PROMPT
from pm_copilot.schema import normalize_partial


def analyze_v2(
    *,
    update_text: str,
    provider: str,
    model: str,
    base_url: str,
    timeout_s: int,
    max_tokens: int,
    max_attempts: int,
    allow_repair: bool,
) -> Dict[str, Any]:
    if not update_text.strip():
        raise ValueError("No input text provided")

    summary_obj = run_json_agent(
        system_prompt=SUMMARY_AGENT_PROMPT,
        user_content=update_text,
        expected_contract='{"summary": string}',
        provider=provider,
        model=model,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
    )
    summary = summary_obj.get("summary", "")

    def _validate_tasks(obj: Dict[str, Any]) -> None:
        normalize_partial(tasks=obj.get("tasks", []))

    tasks_obj = run_json_agent(
        system_prompt=TASKS_AGENT_PROMPT,
        user_content=update_text,
        expected_contract=(
            '{"tasks": ['
            '{"title": string, "description": string, '
            '"owner": string|null, "due_date": string|null, '
            '"status": string|null, "priority": string|null, '
            '"dependencies": array}'
            ']}'
        ),
        provider=provider,
        model=model,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
        validate_fn=_validate_tasks,
    )
    tasks_norm = normalize_partial(tasks=tasks_obj.get("tasks", [])).get("tasks", [])

    risks_input = textwrap.dedent(
        f"""\
        Raw project update:
        ---
        {update_text.strip()}
        ---

        Context (from other agents):
        Summary: {summary}
        Extracted tasks (JSON): {json.dumps(tasks_norm, ensure_ascii=False)}
        """
    ).strip()

    def _validate_risks(obj: Dict[str, Any]) -> None:
        normalize_partial(risks=obj.get("risks", []), followups=obj.get("followups", []))

    risks_obj = run_json_agent(
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
        provider=provider,
        model=model,
        base_url=base_url,
        timeout_s=timeout_s,
        max_tokens=max_tokens,
        max_attempts=max_attempts,
        allow_repair=allow_repair,
        validate_fn=_validate_risks,
    )

    return normalize_partial(
        summary=summary,
        tasks=tasks_norm,
        risks=risks_obj.get("risks", []),
        followups=risks_obj.get("followups", []),
    )
