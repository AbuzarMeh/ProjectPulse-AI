"""CLI entrypoints.

Root pm_copilot.py should be a thin shim that calls pm_copilot.cli.main().
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, List, Optional

from pm_copilot.agents.phase1 import analyze
from pm_copilot.agents.phase2 import analyze_v2
from pm_copilot.integrations import normalize_file_text
from pm_copilot.llm import (
    list_ollama_models,
    list_openai_compat_models,
    resolve_ollama_model,
)
from pm_copilot.orchestration.langgraph_flow import orchestrate
from pm_copilot.schema import CONTRACT_SCHEMA
from pm_copilot.store_sqlite import SQLiteRunStore


def _read_text_from_input(path: Optional[str]) -> str:
    if path and path != "-":
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _default_base_url(provider: str, override: Optional[str]) -> str:
    if override:
        return override
    if provider == "ollama":
        return "http://localhost:11434"
    if provider == "groq":
        return "https://api.groq.com/openai/v1"
    raise ValueError("provider must be 'ollama' or 'groq'")


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
        )
        return 2

    provider = args.provider
    model = args.model
    timeout_s = args.timeout
    max_tokens = args.max_tokens
    base_url = _default_base_url(provider, args.base_url)

    if provider == "ollama":
        resolved = resolve_ollama_model(base_url=base_url, requested=model, timeout_s=min(30, timeout_s))
        if resolved != model:
            sys.stderr.write(f"INFO: Resolved Ollama model '{model}' -> '{resolved}'\n")
            model = resolved

    try:
        result = analyze(
            update_text=update_text,
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
            max_attempts=args.max_attempts,
            allow_repair=not args.no_repair,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    sys.stdout.write(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False) + "\n")
    return 0


def cmd_analyze_v2(args: argparse.Namespace) -> int:
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
        )
        return 2

    provider = args.provider
    model = args.model
    timeout_s = args.timeout
    max_tokens = args.max_tokens
    base_url = _default_base_url(provider, args.base_url)

    if provider == "ollama":
        resolved = resolve_ollama_model(base_url=base_url, requested=model, timeout_s=min(30, timeout_s))
        if resolved != model:
            sys.stderr.write(f"INFO: Resolved Ollama model '{model}' -> '{resolved}'\n")
            model = resolved

    try:
        result = analyze_v2(
            update_text=update_text,
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
            max_attempts=args.max_attempts,
            allow_repair=not args.no_repair,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    sys.stdout.write(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False) + "\n")
    return 0


def cmd_analyze_v3(args: argparse.Namespace) -> int:
    """Phase 3: LangGraph orchestration."""
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
        )
        return 2

    provider = args.provider
    model = args.model
    timeout_s = args.timeout
    max_tokens = args.max_tokens
    base_url = _default_base_url(provider, args.base_url)

    if provider == "ollama":
        resolved = resolve_ollama_model(base_url=base_url, requested=model, timeout_s=min(30, timeout_s))
        if resolved != model:
            sys.stderr.write(f"INFO: Resolved Ollama model '{model}' -> '{resolved}'\n")
            model = resolved

    try:
        result = orchestrate(
            input_text=update_text,
            provider=provider,
            model=model,
            base_url=base_url,
            timeout_s=timeout_s,
            max_tokens=max_tokens,
            max_attempts=args.max_attempts,
            allow_repair=not args.no_repair,
        )
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    sys.stdout.write(json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False) + "\n")
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


def cmd_ingest_file(args: argparse.Namespace) -> int:
    try:
        text = _read_text_from_input(args.input)
    except FileNotFoundError:
        cwd = os.getcwd()
        sys.stderr.write(
            "ERROR: Input file not found: "
            + str(args.input)
            + "\nCurrent working directory: "
            + cwd
            + "\n"
        )
        return 2

    try:
        normalized = normalize_file_text(text, file_name=args.input, project_key=args.project_key)
    except Exception as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2

    db_path = os.environ.get("PM_COPILOT_DB_PATH", "pm_copilot.sqlite3")
    store = SQLiteRunStore(db_path=db_path)
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
        sys.stderr.write(f"ERROR: Persistence failed: {e}\n")
        return 2

    sys.stdout.write(update_id + "\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pm_copilot",
        description="AI Project Manager Copilot: summarize + tasks + risks + followups as strict JSON.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("analyze", help="Phase 1: single agent")
    pa.add_argument("--input", "-i", help="Path to a text file, or '-' for stdin. If omitted, reads stdin.")
    pa.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    pa.add_argument("--model", required=True)
    pa.add_argument("--base-url")
    pa.add_argument("--timeout", type=int, default=120)
    pa.add_argument("--max-tokens", type=int, default=512)
    pa.add_argument("--max-attempts", type=int, default=2)
    pa.add_argument("--no-repair", action="store_true")
    pa.add_argument("--pretty", action="store_true")
    pa.set_defaults(func=cmd_analyze)

    pb = sub.add_parser("analyze-v2", help="Phase 2: multi-agent")
    pb.add_argument("--input", "-i", help="Path to a text file, or '-' for stdin. If omitted, reads stdin.")
    pb.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    pb.add_argument("--model", required=True)
    pb.add_argument("--base-url")
    pb.add_argument("--timeout", type=int, default=120)
    pb.add_argument("--max-tokens", type=int, default=512)
    pb.add_argument("--max-attempts", type=int, default=2)
    pb.add_argument("--no-repair", action="store_true")
    pb.add_argument("--pretty", action="store_true")
    pb.set_defaults(func=cmd_analyze_v2)

    pc = sub.add_parser("analyze-v3", help="Phase 3: LangGraph orchestration")
    pc.add_argument("--input", "-i", help="Path to a text file, or '-' for stdin. If omitted, reads stdin.")
    pc.add_argument("--provider", choices=["ollama", "groq"], default="ollama")
    pc.add_argument("--model", required=True)
    pc.add_argument("--base-url")
    pc.add_argument("--timeout", type=int, default=120)
    pc.add_argument("--max-tokens", type=int, default=512)
    pc.add_argument("--max-attempts", type=int, default=2)
    pc.add_argument("--no-repair", action="store_true")
    pc.add_argument("--pretty", action="store_true")
    pc.set_defaults(func=cmd_analyze_v3)

    pd = sub.add_parser("ingest-file", help="Persist a text file as a normalized update in SQLite")
    pd.add_argument("--input", "-i", required=True, help="Path to a text file")
    pd.add_argument("--project-key", help="Optional grouping key for longitudinal tracking")
    pd.set_defaults(func=cmd_ingest_file)

    pm = sub.add_parser("ollama-models", help="List locally available Ollama models")
    pm.add_argument("--base-url")
    pm.add_argument("--timeout", type=int, default=30)
    pm.set_defaults(func=cmd_ollama_models)

    pg = sub.add_parser("groq-models", help="List Groq model IDs (requires GROQ_API_KEY)")
    pg.add_argument("--base-url")
    pg.add_argument("--timeout", type=int, default=30)
    pg.set_defaults(func=cmd_groq_models)

    ps = sub.add_parser("schema", help="Print the output JSON schema/contract")
    ps.set_defaults(func=cmd_schema)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))
