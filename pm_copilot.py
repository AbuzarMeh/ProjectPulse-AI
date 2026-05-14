#!/usr/bin/env python3
"""AI Project Manager Copilot — Phase 1 MVP (Single-LLM Intelligence)

This is intentionally NOT a chatbot. It is a small CLI that:
- accepts raw project update text
- asks an LLM to produce structured JSON
- validates/coerces the result into a stable contract

Default provider is Ollama running locally.

Examples:
  # Analyze from a file
  python pm_copilot.py analyze --input updates.txt --provider ollama --model llama3.1

  # Analyze from stdin
  type updates.txt | python pm_copilot.py analyze --provider ollama --model llama3.1

  # Groq (OpenAI-compatible). Set GROQ_API_KEY in your env.
  python pm_copilot.py analyze --provider groq --model llama-3.3-70b-versatile

  # Print the JSON schema/contract
  python pm_copilot.py schema
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import textwrap
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple


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


SYSTEM_PROMPT = textwrap.dedent(
    """\
    You are a Project Analyst LLM inside an AI Project Management Copilot.

    Goal: convert the user's raw project update text into a STRICT JSON object.

    HARD REQUIREMENTS:
    - Output MUST be valid JSON.
    - Output MUST be ONLY the JSON (no markdown fences, no commentary).
    - Output MUST match this top-level contract exactly:
      {
        "summary": string,
        "tasks": array,
        "risks": array,
        "followups": array
      }

    Content guidelines:
    - summary: 3–7 bullet-like sentences merged into a single string (no markdown bullets).
    - tasks: actionable items implied or explicitly stated. Each task requires title + description.
      Use null when owner/due_date/status/priority is unknown.
    - risks: blockers, ambiguities, dependencies, delays. Each requires description.
    - followups: messages/reminders that a PM would send. Each requires message.

    Dates: if present, normalize to YYYY-MM-DD. Otherwise null.

    If the input lacks information, keep lists empty and be honest in summary.
    """
).strip()


def _http_json(
    url: str,
    payload: Dict[str, Any],
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 120,
) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, data=data, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} calling {url}: {body or e.reason}") from e
    except (TimeoutError, socket.timeout) as e:
        raise RuntimeError(
            f"Timeout calling {url}. Try increasing --timeout (e.g., 600) or use a smaller/faster model."
        ) from e
    except urllib.error.URLError as e:
        msg = str(e)
        if "timed out" in msg.lower():
            raise RuntimeError(
                f"Timeout calling {url}. Try increasing --timeout (e.g., 600) or use a smaller/faster model."
            ) from e
        raise RuntimeError(f"Network error calling {url}: {e}") from e


def _http_get_json(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout_s: int = 60,
) -> Dict[str, Any]:
    req_headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url=url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {e.code} calling {url}: {body or e.reason}") from e
    except (TimeoutError, socket.timeout) as e:
        raise RuntimeError(
            f"Timeout calling {url}. Try increasing --timeout (e.g., 60) and ensure Ollama is running."
        ) from e
    except urllib.error.URLError as e:
        msg = str(e)
        if "timed out" in msg.lower():
            raise RuntimeError(
                f"Timeout calling {url}. Try increasing --timeout (e.g., 60) and ensure Ollama is running."
            ) from e
        raise RuntimeError(f"Network error calling {url}: {e}") from e


def list_ollama_models(*, base_url: str, timeout_s: int) -> List[str]:
    url = base_url.rstrip("/") + "/api/tags"
    resp = _http_get_json(url, timeout_s=timeout_s)
    models = resp.get("models", [])
    names: List[str] = []
    if isinstance(models, list):
        for m in models:
            if isinstance(m, dict) and isinstance(m.get("name"), str):
                names.append(m["name"])
    return sorted(set(names))


def resolve_ollama_model(*, base_url: str, requested: str, timeout_s: int) -> str:
    """Resolve a shorthand model name to an installed Ollama tag when possible.

    Example: 'llama3.1' -> 'llama3.1:latest' (if present)
    """

    requested = requested.strip()
    if not requested:
        return requested

    try:
        available = list_ollama_models(base_url=base_url, timeout_s=timeout_s)
    except Exception:
        return requested

    if requested in available:
        return requested

    # If user already provided a tag (model:tag), do not guess further.
    if ":" in requested:
        return requested

    candidates = [m for m in available if m == requested or m.startswith(requested + ":")]
    if not candidates:
        return requested

    # Prefer common tags
    for preferred in (requested + ":latest", requested + ":8b", requested + ":7b"):
        if preferred in candidates:
            return preferred

    return candidates[0]


def call_ollama_chat(
    *,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_s: int,
    max_tokens: int,
) -> str:
    url = base_url.rstrip("/") + "/api/chat"
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": int(max_tokens),
        },
    }
    resp = _http_json(url, payload, timeout_s=timeout_s)
    try:
        return resp["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Ollama response shape: {resp}") from e


def call_openai_compat_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout_s: int,
    max_tokens: int,
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": int(max_tokens),
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = _http_json(url, payload, headers=headers, timeout_s=timeout_s)
    try:
        return resp["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI-compatible response shape: {resp}") from e


def list_openai_compat_models(*, base_url: str, api_key: str, timeout_s: int) -> List[str]:
    url = base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = _http_get_json(url, headers=headers, timeout_s=timeout_s)

    data = resp.get("data", [])
    names: List[str] = []
    if isinstance(data, list):
        for m in data:
            if isinstance(m, dict) and isinstance(m.get("id"), str):
                names.append(m["id"])

    return sorted(set(names))


def strip_code_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # Remove first fence line
        first_nl = t.find("\n")
        if first_nl != -1:
            t = t[first_nl + 1 :]
        # Remove trailing fence
        if t.strip().endswith("```"):
            t = t.strip()[: -3]
    return t.strip()


def extract_json_object(text: str) -> Tuple[Dict[str, Any], str]:
    """Parse a JSON object from the model response.

    Returns: (obj, parse_strategy)
    """
    t = strip_code_fences(text)

    # Strategy 1: full parse
    try:
        obj = json.loads(t)
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON must be an object")
        return obj, "full"
    except Exception:
        pass

    # Strategy 2: best-effort slice between first { and last }
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        sliced = t[start : end + 1]
        obj = json.loads(sliced)
        if not isinstance(obj, dict):
            raise ValueError("Top-level JSON must be an object")
        return obj, "sliced"

    raise ValueError("Could not locate a JSON object in model output")


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

    # Enforce top-level keys only
    return out


def build_messages(update_text: str) -> List[Dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": update_text.strip()},
    ]


def build_repair_messages(update_text: str, bad_output: str, error: str) -> List[Dict[str, str]]:
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

    messages = build_messages(update_text)

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
            normalized = normalize_and_validate(parsed)
            return normalized
        except Exception as e:
            last_error = f"Attempt {attempt} failed: {e}"
            if not allow_repair or attempt >= max_attempts:
                break
            messages = build_repair_messages(update_text, bad_output, last_error)

    raise RuntimeError(last_error + ("" if not bad_output else "\nLast model output:\n" + bad_output[:2000]))


def _read_text_from_input(path: Optional[str]) -> str:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def cmd_analyze(args: argparse.Namespace) -> int:
    try:
        update_text = _read_text_from_input(args.input)
    except FileNotFoundError:
        cwd = os.getcwd()
        sys.stderr.write(
            "ERROR: Input file not found: "
            + str(args.input)
            + "\nCurrent working directory: "
            + cwd
            + "\nTip: create the file, pass the correct path, or omit --input to read from stdin.\n"
            + "Example (stdin): type updates.txt | python pm_copilot.py analyze --provider ollama --model llama3.1 --pretty\n"
        )
        return 2

    provider = args.provider
    model = args.model
    timeout_s = args.timeout
    max_tokens = args.max_tokens

    if provider == "ollama" and not args.base_url:
        base_url = "http://localhost:11434"
    elif provider == "groq" and not args.base_url:
        base_url = "https://api.groq.com/openai/v1"
    else:
        base_url = args.base_url

    if provider == "ollama":
        resolved = resolve_ollama_model(base_url=base_url, requested=model, timeout_s=min(30, timeout_s))
        if resolved != model:
            sys.stderr.write(f"INFO: Resolved Ollama model '{model}' -> '{resolved}'\n")
            model = resolved

    max_attempts = args.max_attempts
    allow_repair = not args.no_repair

    try:
        result = analyze(
            update_text=update_text,
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
            max_attempts=max_attempts,
            allow_repair=allow_repair,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    if args.pretty:
        sys.stdout.write(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(json.dumps(result, separators=(",", ":"), ensure_ascii=False) + "\n")

    return 0


def cmd_ollama_models(args: argparse.Namespace) -> int:
    base_url = args.base_url or "http://localhost:11434"
    try:
        models = list_ollama_models(base_url=base_url, timeout_s=args.timeout)
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    if not models:
        sys.stderr.write("No Ollama models found. Try: ollama pull phi3:latest (or another model)\n")
        return 1

    for m in models:
        sys.stdout.write(m + "\n")
    return 0


def cmd_groq_models(args: argparse.Namespace) -> int:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        sys.stderr.write("ERROR: GROQ_API_KEY environment variable is required for groq-models\n")
        return 2

    base_url = args.base_url or "https://api.groq.com/openai/v1"
    try:
        models = list_openai_compat_models(base_url=base_url, api_key=api_key, timeout_s=args.timeout)
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    if not models:
        sys.stderr.write("No models returned by the API.\n")
        return 1

    for m in models:
        sys.stdout.write(m + "\n")
    return 0


def cmd_schema(_: argparse.Namespace) -> int:
    sys.stdout.write(json.dumps(CONTRACT_SCHEMA, indent=2, ensure_ascii=False) + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pm_copilot",
        description="AI Project Manager Copilot (Phase 1 MVP): summarize + tasks + risks + followups as strict JSON.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("analyze", help="Analyze raw project updates into structured JSON")
    pa.add_argument("--input", "-i", help="Path to a text file, or '-' to read stdin explicitly. If omitted, reads from stdin.")
    pa.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    pa.add_argument("--model", required=True, help="Model name (e.g., llama3.1 for Ollama)")
    pa.add_argument("--base-url", help="Override API base URL")
    pa.add_argument("--timeout", type=int, default=120, help="HTTP timeout in seconds")
    pa.add_argument("--max-tokens", type=int, default=512, help="Max tokens to generate (Ollama: num_predict)")
    pa.add_argument("--max-attempts", type=int, default=2, help="Total attempts (includes optional repair)")
    pa.add_argument("--no-repair", action="store_true", help="Disable JSON repair retry")
    pa.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    pa.set_defaults(func=cmd_analyze)

    pm = sub.add_parser("ollama-models", help="List locally available Ollama model names")
    pm.add_argument("--base-url", help="Override Ollama base URL (default: http://localhost:11434)")
    pm.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    pm.set_defaults(func=cmd_ollama_models)

    pg = sub.add_parser("groq-models", help="List available Groq model IDs (requires GROQ_API_KEY)")
    pg.add_argument("--base-url", help="Override Groq base URL (default: https://api.groq.com/openai/v1)")
    pg.add_argument("--timeout", type=int, default=30, help="HTTP timeout in seconds")
    pg.set_defaults(func=cmd_groq_models)

    ps = sub.add_parser("schema", help="Print the output JSON schema/contract")
    ps.set_defaults(func=cmd_schema)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
