"""Phase 1: single-agent analyzer."""

from __future__ import annotations

import os
import textwrap
from typing import Any, Dict, List

from pm_copilot.json_extract import extract_json_object
from pm_copilot.llm import call_ollama_chat, call_openai_compat_chat
from pm_copilot.prompts import SYSTEM_PROMPT
from pm_copilot.schema import normalize_and_validate


def _build_messages(update_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": update_text.strip()},
    ]


def _build_repair_messages(update_text: str, bad_output: str, error: str) -> List[Dict[str, str]]:
    repair_prompt = textwrap.dedent(
        f"""\
        The previous output was invalid or did not match the contract.

        Error:
        {error}

        Original update text:
        ---
        {update_text.strip()}
        ---

        Invalid model output:
        ---
        {bad_output.strip()}
        ---

        Return ONLY valid JSON matching the required top-level contract:
        {{"summary": string, "tasks": array, "risks": array, "followups": array}}
        """
    ).strip()

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": repair_prompt},
    ]


def analyze(
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

    messages = _build_messages(update_text)

    last_error = ""
    bad_output = ""
    for attempt in range(1, max_attempts + 1):
        if provider == "ollama":
            raw = call_ollama_chat(
                base_url=base_url,
                model=model,
                messages=messages,
                timeout_s=timeout_s,
                max_tokens=max_tokens,
            )
        elif provider == "groq":
            api_key = os.environ.get("GROQ_API_KEY", "").strip()
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is required for provider=groq")
            raw = call_openai_compat_chat(
                base_url=base_url,
                api_key=api_key,
                model=model,
                messages=messages,
                timeout_s=timeout_s,
                max_tokens=max_tokens,
            )
        else:
            raise ValueError("provider must be 'ollama' or 'groq'")

        bad_output = raw
        try:
            parsed, _strategy = extract_json_object(raw)
            return normalize_and_validate(parsed)
        except Exception as e:
            last_error = f"Attempt {attempt} failed: {e}"
            if not allow_repair or attempt >= max_attempts:
                break
            messages = _build_repair_messages(update_text, bad_output, last_error)

    raise RuntimeError(last_error + ("" if not bad_output else "\nLast model output:\n" + bad_output[:2000]))
