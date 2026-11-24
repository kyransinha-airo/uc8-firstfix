# UC8 POC — FirstFix

Field service dispatch and triage for commercial refrigeration. Four agents follow Shubham's
flow: **A1 Intake & SLA → A2 Fault analysis → A3 Dispatch → dispatcher → visit + note upload →
A4 Verification → dispatcher**. Agents decide what to read and judge it; every number on screen
comes from deterministic tools.

The design is [`docs/architecture.md`](docs/architecture.md) (v0.2). Items marked **[to confirm]**
still need Shubham's sign-off.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 18 + Vite + Tailwind 4, deployed to Azure Static Web Apps |
| Backend | FastAPI (Python 3.13) in an Azure Container App |
| Orchestration | LangGraph: fixed edges between four agent subgraphs; deterministic tools |
| LLM | Azure OpenAI (Foundry), built lazily in `backend/app/core/llm.py` |
| Database | PostgreSQL (local Docker for dev), plain SQL migrations |
| Files | Local `data/` for dev |

## Ports

| Service | Port | Why |
| --- | --- | --- |
| Backend | 8008 | 8000 = Overturn, 8001 = ClaimGuard, 8002 = Sentinel, 8003 = Verity; 8008 = UC8 |
| Frontend (Vite) | 3008 | Proxies `/api` to 8008 |
| PostgreSQL | 5438 | `docker-compose.postgres.yml` (avoids Verity's 5433 and a local 5432) |

## Run it

```bash
# Mock data check (no database needed)
python3 -m venv .venv && source .venv/bin/activate && pip install pyyaml
python data/mock-data/validate.py            # expect 42/42 figures match

# Database
docker compose -f docker-compose.postgres.yml up -d
```

Backend and frontend commands land with the skeleton (W-001).

## Layout

```
backend/             FastAPI app (W-001): api, core, graphs, services, tools, schemas, db, scripts; tests/
frontend/            React app (W-001)
data/mock-data/      fictional mock data + answer key (the reference for expected results)
  01_reports/        raw fault reports per channel
  02_documents/      agreements, manual extracts, bulletins, history notes (read by agents)
  03_structured/     reference tables, roster, stock, travel, telemetry (read by tools)
  04_config/         parameters.yaml: every rule value
  05_answer_key/     expected results; never loaded by the app, never shown to a model
data/replay/         pinned agent trajectories for replay
data/uploads/        local uploads (gitignored)
contracts/           API contracts shared with the frontend
docs/                design docs
doc-internal/        BRD, one-pager, WBS, standup notes (local only, gitignored)
```

## Conventions

- Every number or verdict the UI shows comes from deterministic code or a pinned, reviewed
  agent trajectory. Never from an unchecked model call.
- Tools and services never call an LLM. Agents live in graph nodes.
- Same input, same output: no clock or randomness inside a service; `now` is passed in.
- Mock data is fictional, and its answer key is what tests check against.
- One change per PR, branched from the branch it depends on. Reference WBS IDs in commits.
- Never commit `.env`, `doc-internal/`, `CLAUDE.md`, `.claude/` or the WBS.
