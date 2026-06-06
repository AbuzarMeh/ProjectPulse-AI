# AI Project Manager Copilot

AI Project Manager Copilot turns messy project updates into clean, reviewable project-management output: summaries, tasks, risks, and follow-ups.

It is built as a human-in-the-loop copilot, not a chatbot. The goal is to help project managers quickly extract signal from standups, Slack-style updates, Discord messages, text files, and raw notes while keeping the final decision with a human reviewer.

## What It Produces

Given raw update text, the system returns a strict JSON contract:

```json
{
  "summary": "Concise project status summary",
  "tasks": [
    {
      "title": "Action item",
      "description": "Why it matters",
      "owner": "Optional owner",
      "due_date": "Optional due date",
      "status": "Optional status",
      "priority": "Optional priority",
      "dependencies": []
    }
  ],
  "risks": [
    {
      "description": "Risk or blocker",
      "severity": "Optional severity",
      "likelihood": "Optional likelihood",
      "impact": "Optional impact",
      "mitigation": "Optional mitigation",
      "owner": "Optional owner"
    }
  ],
  "followups": [
    {
      "message": "Suggested follow-up message",
      "to": "Optional recipient",
      "channel": "Optional channel",
      "due_date": "Optional due date"
    }
  ]
}
```

## Highlights

- LangGraph-powered Phase 3 orchestration with state, trace events, retries, and fallbacks
- Multi-agent extraction flow for summaries, tasks, risks, and follow-ups
- Streamlit demo UI for live analysis and run history
- FastAPI service for automation workflows and integrations
- SQLite persistence for updates, runs, debug traces, and idempotent API requests
- Groq and local Ollama provider support through OpenAI-compatible patterns
- Slack, Discord, and text-file ingestion normalizers
- Strict structured output for downstream automation tools such as n8n

## Quick Demo

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the Streamlit UI:

```powershell
streamlit run .\ui\app.py
```

Open the local Streamlit URL, paste a project update, choose a provider/model, and click **Analyze**. Runs can be persisted to SQLite and reviewed later from the **Runs** page.

## CLI Usage

Phase 3 is the recommended path:

```powershell
python .\pm_copilot.py analyze-v3 --provider groq --model "llama-3.3-70b-versatile" --input .\updates.txt --pretty
```

Use a local Ollama model:

```powershell
python .\pm_copilot.py analyze-v3 --provider ollama --model phi3 --input .\updates.txt --pretty
```

Read from stdin:

```powershell
Get-Content .\updates.txt | python .\pm_copilot.py analyze-v3 --provider ollama --model phi3 --input - --pretty
```

Print the output schema:

```powershell
python .\pm_copilot.py schema
```

Persist a text update before analysis:

```powershell
python .\pm_copilot.py ingest-file --input .\updates.txt --project-key alpha
```

## API Usage

Start the FastAPI service:

```powershell
uvicorn pm_copilot.api:app --app-dir src --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Analyze text:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/analyze `
  -ContentType "application/json" `
  -Body '{
    "text": "Backend finished auth API. Frontend blocked on token refresh. Need QA by Friday.",
    "provider": "ollama",
    "model": "phi3:latest",
    "persist": true
  }'
```

Useful endpoints:

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Service health |
| `POST /analyze` | Analyze text or a stored update |
| `POST /analyze/debug` | Analyze and return trace metadata |
| `POST /ingest/slack/webhook` | Normalize and persist Slack-style payloads |
| `POST /ingest/discord/webhook` | Normalize and persist Discord-style payloads |
| `GET /runs` | List recent analysis runs |
| `GET /runs/{run_id}` | Inspect one run |
| `GET /updates` | List stored updates |
| `GET /updates/{update_id}` | Inspect one stored update |

## Providers

### Groq

Set your API key:

```powershell
$env:GROQ_API_KEY = "your-key"
```

List available Groq models:

```powershell
python .\pm_copilot.py groq-models
```

Example:

```powershell
python .\pm_copilot.py analyze-v3 --provider groq --model "llama-3.3-70b-versatile" --input .\updates.txt --pretty
```

### Ollama

Make sure Ollama is running locally, then list models:

```powershell
python .\pm_copilot.py ollama-models
```

Example:

```powershell
python .\pm_copilot.py analyze-v3 --provider ollama --model phi3 --input .\updates.txt --pretty
```

## How It Works

```text
Raw update text
      |
      v
Summary node
      |
      v
Task extraction node
      |
      v
Conditional routing
      |
      +-- no tasks --> normalized output
      |
      v
Risk and follow-up node
      |
      v
Validated PM-ready JSON
```

The Phase 3 workflow keeps a shared state object across nodes. Each run includes status, warnings, errors, and trace events so the system is easier to debug during demos and automation runs.

When the LLM returns incomplete output or fails in selected nodes, deterministic fallbacks can extract obvious task and risk bullets from structured text sections.

## Project Structure

```text
.
|-- pm_copilot.py                  # Thin CLI entrypoint
|-- requirements.txt               # Runtime dependencies
|-- ui/
|   `-- app.py                     # Streamlit demo UI
|-- src/
|   `-- pm_copilot/
|       |-- api.py                 # FastAPI app
|       |-- cli.py                 # CLI commands
|       |-- llm.py                 # Provider clients/helpers
|       |-- schema.py              # Output contract normalization
|       |-- store_sqlite.py        # SQLite persistence
|       |-- agents/
|       |   |-- phase1.py          # Single-agent analyzer
|       |   |-- phase2.py          # Multi-agent analyzer
|       |   `-- runner.py          # JSON agent runner
|       |-- integrations/
|       |   |-- file_ingest.py     # Text-file normalization
|       |   |-- slack.py           # Slack payload normalization
|       |   `-- discord.py         # Discord payload normalization
|       `-- orchestration/
|           `-- langgraph_flow.py  # Phase 3 stateful workflow
`-- tests/
    |-- test_refactor.py
    `-- test_integrations.py
```

## Validation

Fast checks:

```powershell
python test_imports_quick.py
python -m pytest tests
python -m compileall src
```

Phase 3 validation scripts:

```powershell
python validate_phase3.py
python test_integration_phase3.py
python test_uat_phase3.py
python check_production_readiness.py
```

Existing validation artifacts:

- `phase3_deployment_validation.json`
- `phase3_integration_test_results.json`
- `phase3_uat_results.json`

## Configuration

| Variable | Purpose | Default |
| --- | --- | --- |
| `GROQ_API_KEY` | Required for Groq model calls | none |
| `PM_COPILOT_DB_PATH` | SQLite database path for runs and updates | `pm_copilot.sqlite3` |

Local secrets, keys, databases, caches, and demo media are excluded through `.gitignore`.

## Notes

- LLM output should be reviewed by a human project manager before being treated as final.
- The system is designed for structured PM assistance, not open-ended conversation.
- The JSON contract is intentionally stable so automation tools can consume it reliably.
