# PEAD Trading System

Autonomous S&P 500 paper trading platform. Signal engine generates PEAD-based trade signals from earnings events; a SAC Ensemble RL (5 agents, MoE meta-controller) sizes positions; macro composite gate and portfolio controls (ERP cap, Mag-7 cap, stop-loss) gate every order before it hits Alpaca paper trading.

## Stack

- **Backend** — FastAPI + SQLAlchemy + TimescaleDB (PostgreSQL), Alembic migrations
- **Workers** — Celery + Redis for signal/portfolio Celery tasks; Prefect for data ingestion flows
- **RL Trainer** — SAC Ensemble (5 agents, PER, MoE meta-controller, Transformer encoder); Docker Compose profile `training`, manual Railway deploy only
- **Frontend** — Next.js 14 + TypeScript, dark theme (`#0A1628`), 8 views, SSE real-time updates
- **Data** — Alpaca (prices), FRED (macro), FMP (earnings), Ken French (FF5 factors), Wikipedia (S&P 500 constituents)
- **Infra** — Docker Compose (local), Railway (prod), GitHub Actions CI/CD

## Project layout

```
building/
├── backend/          ← FastAPI app + Prefect flows + Celery tasks + Alembic
│   ├── app/
│   │   ├── api/      ← FastAPI routers (alerts, market, orders, positions, rl, stream)
│   │   ├── flows/    ← Prefect ingestion flows (prices, macro, ff5, earnings, constituents, hyg_lqd)
│   │   ├── models/   ← SQLAlchemy ORM models
│   │   ├── portfolio/← Macro scorer, ERP/Mag-7 caps, stop-loss, SLSQP completion, pipeline
│   │   ├── signals/  ← Implied EPS, quality, momentum, composite, filters, pipeline, writer
│   │   └── tasks/    ← Celery tasks (signals, portfolio)
│   ├── alembic/      ← migrations (0001 schema, 0002 phase-2 tables, 0003 macro composite)
│   └── tests/        ← pytest suite (unit + DB-gated integration tests)
├── frontend/         ← Next.js 14 frontend
├── api/              ← standalone API service (FastAPI, auth)
├── worker/           ← Celery + Prefect worker image
├── rl/               ← SAC ensemble, PER buffer, MoE controller, Transformer encoder
├── data/             ← Data clients (price, factor, FRED, earnings)
├── signals/          ← Legacy signal modules (superseded by backend/app/signals/)
├── macro/            ← Legacy macro modules
└── docker-compose.yml
```

## Commands

### Test

```bash
# Unit tests (no DB required)
cd backend && pytest tests/ -v --tb=short -k "not integration"

# All tests including DB-gated integration (requires DATABASE_URL_SYNC)
cd backend && DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v --tb=short

# Frontend
cd frontend && npm test

# Lint
cd backend && ruff check .
cd backend && ruff format --check .
cd frontend && npm run lint && npm run type-check
```

### Build & run locally

```bash
docker compose up -d          # start all services (web, api, worker, db, redis)
docker compose up -d --build  # rebuild first

# Apply migrations
cd backend && alembic upgrade head

# Run RL trainer (manual only — never auto-deploy)
docker compose --profile training up rl-trainer
```

### Deploy

- **Prod**: push to `main` → GitHub Actions CI triggers → Railway auto-deploy
- **RL trainer**: Railway manual deploy only (never triggered by CI)
- `railway.toml` defines service config; `RAILWAY_SERVICE_NAME` env var selects the target

### Prefect flows

```bash
cd backend && python -m app.flows.deploy_all_flows   # register all 6 flows
cd backend && python -m app.flows.prices             # run price ingestion now
cd backend && python -m app.flows.macro              # run macro ingestion now
```

## Key architecture decisions

- **Point-in-time semantics (FR-1.5)**: every DB query filters `ingestion_timestamp <= :as_of` — zero look-ahead bias. All historical records include `ingestion_timestamp`.
- **Macro composite persisted (gap SC-1b)**: `composite_score + score_components` stored in `macro_indicators` alongside raw readings in the same upsert. RL state builder reads from DB — never recomputed on the fly — so sizing decisions are replayable even if the scoring algorithm changes.
- **RL trainer excluded from CI**: `ci.yml` explicitly skips `rl/` and the `rl-trainer` Docker profile. Manual deploy only.
- **Signal pipeline**: earnings event → implied EPS gap → quality scorer → momentum → 3-axis composite → sector hurdle → ROIC/WACC filter → macro gate → ERP cap → Mag-7 cap → SLSQP completion → stop-loss → Alpaca bracket order.

## Testing philosophy

- DB-gated tests skip automatically when `DATABASE_URL_SYNC` is absent (CI runs unit-only by default)
- Integration tests in `backend/tests/` use `db_engine` fixture from `conftest.py`
- Performance benchmark: signal pipeline must complete in < 5s (FR-3.7)
- No mocking the DB in integration tests — real TimescaleDB only

## gstack

This project uses [gstack](https://github.com/garrytan/gstack) for AI-assisted development workflows.

| Workflow | When to use |
|----------|-------------|
| `/review` | Before merging any branch — code audit |
| `/qa` | After implementing a frontend view — browser testing |
| `/ship` | When ready to create a PR and deploy |
| `/plan-eng-review` | Before starting a new phase — architecture review |
| `/investigate` | Debugging production issues or test failures |
| `/retro` | After each phase completes |
| `/careful` | When touching Railway config, migrations, or the Alpaca execution layer |

### Project-specific gstack config

- **Test command**: `cd backend && pytest tests/ -v --tb=short -k "not integration"`
- **Lint command**: `cd backend && ruff check . && cd ../frontend && npm run lint`
- **Build command**: `docker compose build`
- **Deploy command**: push to `main` (Railway auto-deploy via GitHub Actions)
- **Integration test command**: `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead cd backend && pytest tests/ -v`
- **Frontend test**: `cd frontend && npm run lint && npm run type-check`
