# AI Project Manager Copilot

Agentic AI system that assists human project managers by turning raw project updates into structured JSON:

```json
{
  "summary": "...",
  "tasks": [],
  "risks": [],
  "followups": []
}
```

## What this is / isn't

- This is **not a chatbot**.
- This is a **human-in-the-loop copilot** that produces structured outputs for PM review.
- It supports local Ollama models and Groq through an OpenAI-compatible API.

## Current Status

Phase 3 is implemented.

- Phase 1: single-agent analyzer (`analyze`)
- Phase 2: multi-agent analyzer (`analyze-v2`) with separate summary, task, risk, and follow-up extraction
- Phase 3: LangGraph stateful orchestration (`analyze-v3`) with workflow state, tracing, fallbacks, and debug metadata

Recent validation artifacts show passing deployment, integration, and UAT checks:

- `phase3_deployment_validation.json`
- `phase3_integration_test_results.json`
- `phase3_uat_results.json`

## Usage

### Phase 3 (recommended)

```powershell
python .\pm_copilot.py analyze-v3 --provider groq --model "llama-3.3-70b-versatile" --input .\updates.txt --pretty
```

### Phase 2

```powershell
python .\pm_copilot.py analyze-v2 --provider groq --model "llama-3.3-70b-versatile" --input .\updates.txt --pretty
```

### Phase 1

```powershell
python .\pm_copilot.py analyze --provider groq --model "llama-3.3-70b-versatile" --input .\updates.txt --pretty
```

### Print the JSON schema

```powershell
python .\pm_copilot.py schema
```

## Web UI (recommended for demos)

This repo includes a Streamlit frontend that runs Phase 3 orchestration and shows results + run history.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the UI:

```powershell
streamlit run .\ui\app.py
```

Notes:

- For Groq, set `GROQ_API_KEY` first.
- Runs are persisted to SQLite at `PM_COPILOT_DB_PATH` (default: `pm_copilot.sqlite3`).

## Providers

### Groq (API)

Set env var:

```powershell
$env:GROQ_API_KEY = "..."
```

List available Groq models:

```powershell
python .\pm_copilot.py groq-models
```

### Ollama (local)

Ensure Ollama is running, then:

```powershell
python .\pm_copilot.py analyze-v3 --provider ollama --model phi3 --input .\updates.txt --pretty
```

List local Ollama models:

```powershell
python .\pm_copilot.py ollama-models
```

## Repo Layout

```text
src\pm_copilot\
  __init__.py
  api.py
  cli.py
  json_extract.py
  llm.py
  prompts.py
  schema.py
  store_sqlite.py
  agents\
    phase1.py
    phase2.py
    runner.py
  orchestration\
    langgraph_flow.py

pm_copilot.py  # thin CLI entrypoint
```

## Validation

Fast local checks:

```powershell
python test_imports_quick.py
python tests\test_refactor.py
python -m compileall src
```

Phase 3 validation scripts:

```powershell
python validate_phase3.py
python test_integration_phase3.py
python test_uat_phase3.py
python check_production_readiness.py
```

## Notes

- Secrets must stay out of git; `keys\` is ignored.
- LLM outputs are suggestions for a human project manager to review.
