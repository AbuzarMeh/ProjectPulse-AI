"""Streamlit frontend for pm_copilot.

Goal: production-presentable demo UI for Phase 3 (LangGraph orchestration).

Run:
  pip install -r requirements.txt
  streamlit run ./ui/app.py

Notes:
- For Groq, set GROQ_API_KEY in the environment.
- Uses local SQLite persistence (PM_COPILOT_DB_PATH, default: pm_copilot.sqlite3).
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import streamlit as st


def _ensure_src_on_path() -> None:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(repo_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


_ensure_src_on_path()

# Keep the console clean for demos by suppressing known, non-actionable warnings.
warnings.filterwarnings(
    "ignore",
    message=r"The default value of `allowed_objects` will change in a future version\..*",
    category=Warning,
)

try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning

    warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)
except Exception:
    pass
warnings.filterwarnings(
    "ignore",
    message=r"Pandas requires version '2\.10\.2' or newer of 'numexpr'.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=r"Pandas requires version '1\.4\.2' or newer of 'bottleneck'.*",
    category=UserWarning,
)

from pm_copilot.orchestration.langgraph_flow import orchestrate_debug  # noqa: E402
from pm_copilot.store_sqlite import SQLiteRunStore  # noqa: E402


@dataclass(frozen=True)
class RunSummaryRow:
    run_id: str
    created_at_unix: float
    provider: str
    model: str
    status: str


def _fmt_ts(unix_ts: float) -> str:
    dt = datetime.fromtimestamp(float(unix_ts), tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _get_store() -> SQLiteRunStore:
    db_path = os.environ.get("PM_COPILOT_DB_PATH", "pm_copilot.sqlite3")
    return SQLiteRunStore(db_path=db_path)


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _render_contract(output: Dict[str, Any]) -> None:
    summary = output.get("summary", "") if isinstance(output.get("summary"), str) else ""
    tasks = _safe_list(output.get("tasks"))
    risks = _safe_list(output.get("risks"))
    followups = _safe_list(output.get("followups"))

    st.subheader("Summary")
    st.write(summary or "(empty)")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Tasks")
        st.dataframe(tasks, width="stretch", hide_index=True)

    with col2:
        st.subheader("Risks")
        st.dataframe(risks, width="stretch", hide_index=True)

    st.subheader("Followups")
    st.dataframe(followups, width="stretch", hide_index=True)


def _render_run_details(run: Dict[str, Any]) -> None:
    st.markdown(f"**Run ID:** {run.get('run_id', '')}")
    created = run.get("created_at_unix")
    if isinstance(created, (int, float)):
        st.markdown(f"**Created:** {_fmt_ts(float(created))}")

    st.markdown(
        f"**Provider/Model:** {run.get('provider', '')} / {run.get('model', '')}"
        f"  \\  **Status:** {run.get('status', '')}"
    )

    with st.expander("Input text", expanded=False):
        st.text(run.get("input_text", "") or "")

    output = _safe_dict(run.get("output"))
    _render_contract(output)

    errors = _safe_list(run.get("errors"))
    warnings = _safe_list(run.get("warnings"))

    if errors or warnings:
        with st.expander("Errors / Warnings", expanded=False):
            if errors:
                st.error("\n".join([str(e) for e in errors]))
            if warnings:
                st.warning("\n".join([str(w) for w in warnings]))

    trace = _safe_list(run.get("trace"))
    if trace:
        with st.expander("Trace", expanded=False):
            st.dataframe(trace, width="stretch", hide_index=True)

    with st.expander("Raw output JSON", expanded=False):
        st.json(output)


def page_analyze() -> None:
    st.title("AI Project Manager Copilot")
    st.caption("Turn raw updates into structured PM-ready output (Phase 3 orchestration).")

    store = _get_store()

    with st.sidebar:
        st.header("Run settings")
        provider = st.selectbox("Provider", options=["ollama", "groq"], index=0)
        model = st.text_input("Model", value="phi3:latest" if provider == "ollama" else "llama-3.3-70b-versatile")

        base_url_default = "http://localhost:11434" if provider == "ollama" else "https://api.groq.com/openai/v1"
        base_url = st.text_input("Base URL", value=base_url_default)

        timeout_s = st.number_input("Timeout (seconds)", min_value=10, max_value=600, value=120, step=10)
        max_tokens = st.number_input("Max tokens", min_value=64, max_value=4096, value=512, step=64)
        max_attempts = st.number_input("Max attempts", min_value=1, max_value=5, value=2, step=1)
        allow_repair = st.checkbox("Allow repair", value=True)
        persist = st.checkbox("Persist run to SQLite", value=True)

        st.divider()
        st.caption("SQLite DB path")
        st.code(os.environ.get("PM_COPILOT_DB_PATH", "pm_copilot.sqlite3"), language="text")

    st.subheader("Input")
    uploaded = st.file_uploader("Optional: upload a .txt file", type=["txt"], accept_multiple_files=False)

    default_text = ""  # keep it empty by default for privacy
    if uploaded is not None:
        try:
            default_text = uploaded.getvalue().decode("utf-8", errors="replace")
        except Exception:
            default_text = ""

    input_text = st.text_area("Paste project update text", value=default_text, height=240)

    col_run, col_clear = st.columns([1, 1])
    run_clicked = col_run.button("Analyze", type="primary", width="stretch")
    clear_clicked = col_clear.button("Clear", width="stretch")

    if clear_clicked:
        st.session_state.pop("last_result", None)
        st.rerun()

    if run_clicked:
        if not input_text.strip():
            st.error("Please provide some input text.")
            return

        with st.spinner("Running orchestration..."):
            try:
                result = orchestrate_debug(
                    input_text=input_text,
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    timeout_s=int(timeout_s),
                    max_tokens=int(max_tokens),
                    max_attempts=int(max_attempts),
                    allow_repair=bool(allow_repair),
                )
            except Exception as e:
                st.exception(e)
                return

        if persist:
            try:
                store.save_run(
                    run_id=result.get("run_id", ""),
                    provider=provider,
                    model=model,
                    base_url=base_url,
                    status=str(result.get("status", "unknown")),
                    input_text=input_text,
                    output=_safe_dict(result.get("output")),
                    errors=[str(e) for e in _safe_list(result.get("errors"))],
                    warnings=[str(w) for w in _safe_list(result.get("warnings"))],
                    trace=[_safe_dict(x) for x in _safe_list(result.get("trace"))],
                )
            except Exception as e:
                st.warning(f"Persistence failed: {e}")

        st.session_state["last_result"] = result

    last = st.session_state.get("last_result")
    if last:
        st.divider()
        st.subheader("Result")
        st.markdown(f"**Run ID:** {last.get('run_id', '')}  \\  **Status:** {last.get('status', '')}")

        output = _safe_dict(last.get("output"))
        _render_contract(output)

        errors = _safe_list(last.get("errors"))
        warnings = _safe_list(last.get("warnings"))

        if errors or warnings:
            with st.expander("Errors / Warnings", expanded=False):
                if errors:
                    st.error("\n".join([str(e) for e in errors]))
                if warnings:
                    st.warning("\n".join([str(w) for w in warnings]))

        trace = _safe_list(last.get("trace"))
        if trace:
            with st.expander("Trace", expanded=False):
                st.dataframe(trace, width="stretch", hide_index=True)

        with st.expander("Raw result JSON", expanded=False):
            st.code(json.dumps(last, ensure_ascii=False, indent=2), language="json")


def page_runs() -> None:
    st.title("Runs")
    store = _get_store()

    limit = st.number_input("Max runs", min_value=5, max_value=500, value=50, step=5)

    runs_raw = store.list_runs(limit=int(limit))
    rows = [
        RunSummaryRow(
            run_id=str(r.get("run_id", "")),
            created_at_unix=float(r.get("created_at_unix", 0.0)),
            provider=str(r.get("provider", "")),
            model=str(r.get("model", "")),
            status=str(r.get("status", "")),
        )
        for r in runs_raw
        if r.get("run_id")
    ]

    if not rows:
        st.info("No runs found yet. Run an analysis first.")
        return

    st.subheader("Recent runs")
    st.dataframe(
        [
            {
                "created": _fmt_ts(r.created_at_unix),
                "run_id": r.run_id,
                "provider": r.provider,
                "model": r.model,
                "status": r.status,
            }
            for r in rows
        ],
        width="stretch",
        hide_index=True,
    )

    st.subheader("Run details")
    run_id = st.selectbox("Select a run", options=[r.run_id for r in rows])
    rec = store.get_run(run_id)
    if rec is None:
        st.error("Run not found.")
        return

    _render_run_details(
        {
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
    )


def main() -> None:
    st.set_page_config(page_title="PM Copilot", page_icon="✅", layout="wide")

    page = st.sidebar.radio("Navigation", options=["Analyze", "Runs"], index=0)

    if page == "Analyze":
        page_analyze()
    else:
        page_runs()


if __name__ == "__main__":
    main()
