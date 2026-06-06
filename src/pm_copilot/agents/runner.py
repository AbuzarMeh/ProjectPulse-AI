"""Shared agent runner + prompt repair loop."""

from __future__ import annotations

import os
import textwrap
from typing import Any, Callable, Dict, List, Optional

from pm_copilot.json_extract import extract_json_object
from pm_copilot.llm import call_ollama_chat, call_openai_compat_chat


def build_messages_custom(system_prompt: str, user_content: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content.strip()},
    ]


def build_repair_messages_custom(
    *,
    system_prompt: str,
    expected_contract: str,
    context_text: str,
    bad_output: str,
    error: str,
) -> List[Dict[str, str]]:
    repair_prompt = textwrap.dedent(
        f"""\
        The previous output was invalid or did not match the contract.

        Error:
        {error}

        Context:
        ---
        {context_text.strip()}
        ---

        Invalid model output:
        ---
        {bad_output.strip()}
        ---

        Return ONLY valid JSON matching exactly:
        {expected_contract}
        """
    ).strip()

    return build_messages_custom(system_prompt, repair_prompt)


def run_json_agent(
    *,
    system_prompt: str,
    user_content: str,
    expected_contract: str,
    provider: str,
    model: str,
    base_url: str,
    timeout_s: int,
    max_tokens: int,
    max_attempts: int,
    allow_repair: bool,
    validate_fn: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    messages = build_messages_custom(system_prompt, user_content)

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
            if validate_fn is not None:
                validate_fn(parsed)
            return parsed
        except Exception as e:
            last_error = f"Attempt {attempt} failed: {e}"
            if not allow_repair or attempt >= max_attempts:
                break
            messages = build_repair_messages_custom(
                system_prompt=system_prompt,
                expected_contract=expected_contract,
                context_text=user_content,
                bad_output=bad_output,
                error=last_error,
            )

    if not bad_output:
        raise RuntimeError(last_error)

    snippet = bad_output.strip().replace("\r\n", "\n")
    snippet = " ".join(snippet.splitlines())
    max_chars = 600
    if len(snippet) > max_chars:
        snippet = snippet[:max_chars] + "…"

    raise RuntimeError(last_error + "\nLast model output (truncated):\n" + snippet)
