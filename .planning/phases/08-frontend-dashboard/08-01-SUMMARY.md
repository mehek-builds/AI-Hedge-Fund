---
phase: "08"
plan: "01"
subsystem: "frontend-dashboard"
tags: ["fastapi", "rest-api", "sse", "react", "nextjs", "typescript"]
dependency_graph:
  requires: ["01-infrastructure-data-foundation", "02-data-pipelines", "03-signal-engine", "04-portfolio-architecture"]
  provides: ["backend-api-layer", "frontend-components", "sse-hook"]
  affects: ["frontend-dashboard"]
tech_stack:
  added: ["recharts@2.12.7", "lucide-react@0.475.0"]
  patterns: ["FastAPI APIRouter", "SQLAlchemy text() bound params", "React SSE EventSource hook", "exponential backoff reconnect"]
key_files:
  created:
    - backend/app/models/alerts.py
    - backend/app/models/backtest_runs.py
    - backend/app/routers/dashboard.py
    - backend/app/routers/positions_router.py
    - backend/app/routers/signals_router.py
    - backend/app/routers/alerts_router.py
    - backend/app/routers/backtest_router.py
    - backend/app/routers/settings_router.py
    - backend/app/routers/macro_router.py
    - backend/app/routers/rl_router.py
    - frontend/src/types/api.ts
    - frontend/src/hooks/useSSE.ts
    - frontend/src/components/NavSidebar.tsx
    - frontend/src/components/KPICard.tsx
    - frontend/src/components/LoadingSkeleton.tsx
    - frontend/src/components/ErrorBoundary.tsx
    - frontend/src/components/Badge.tsx
    - frontend/.gitignore
  modified:
    - backend/app/config.py
    - backend/app/main.py
    - frontend/app/globals.css
    - frontend/app/layout.tsx
    - frontend/package.json
decisions:
  - "Used `sqlalchemy.text()` with named bound parameters for all raw SQL queries - no f-string SQL anywhere"
  - "SSE stream router prefix changed from /stream to /api/v1 so endpoint is /api/v1/events"
  - "Alert and BacktestRun ORM models created from scratch since they were referenced in plan but absent from codebase"
  - "Settings PATCH mutates the singleton `settings` object in-memory - no restart required for flag changes"
  - "useSSE hook uses exponential backoff (1s, 2s, 4s...) capped at 30s for reconnect"
  - "NavSidebar uses 'use client' directive to access usePathname for active route highlighting"
metrics:
  duration: "~25 min"
  completed: "2026-05-13"
  tasks: 2
  files: 22
---

# Phase 08 Plan 01: Backend REST Endpoints + Frontend Infrastructure Summary

9 FastAPI routers providing REST API layer for dashboard, plus React component library and SSE hook for real-time data.

## Tasks Completed

### Task 1: Backend REST Endpoints

Fixed `main.py` to mount stream router at `/api/v1` (SSE now at `/api/v1/events`). Created and registered 8 new routers all under `/api/v1` prefix:

- `GET /api/v1/dashboard` - aggregated KPIs: open position count, total unrealized P&L, macro gate status, last 5 alerts
- `GET /api/v1/positions` - latest snapshot per symbol via `DISTINCT ON (symbol)`
- `GET /api/v1/signals/recent?limit=20` - most recent signals rows
- `GET /api/v1/alerts?limit=50&offset=0` - paginated alerts with total count
- `GET /api/v1/backtest/runs` and `GET /api/v1/backtest/runs/{run_id}` - backtest run list and detail
- `GET /api/v1/settings` / `PATCH /api/v1/settings` - runtime flag read/write (no restart)
- `GET /api/v1/macro` - latest value per macro series + composite gate status
- `GET /api/v1/rl/state` - RL ensemble stub (empty agents/regime_weights, Phase 5 will populate)

Added `ENABLE_SHORT_SIDE`, `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT` to `Settings` in `config.py`.

Created `Alert` and `BacktestRun` SQLAlchemy ORM models (these were referenced in the plan but missing from the codebase).

### Task 2: Frontend Infrastructure

- Added `recharts@2.12.7` and `lucide-react@0.475.0` to `package.json`
- Extended `globals.css` with 7 CSS custom properties (`--color-bg`, `--color-surface`, etc.), JetBrains Mono Google Font import, `.mono` class, and `@keyframes skeleton-pulse`
- Created `frontend/src/types/api.ts` with 16 TypeScript interfaces covering all REST responses and 4 SSE payload types
- Created `useSSE` hook connecting to `/api/v1/events`, listening on 4 named channels, with exponential backoff auto-reconnect (max 30s)
- Created 5 shared components: `NavSidebar` (240px fixed, 8 routes with lucide icons, active state highlighting), `KPICard` (numeric KPI display with JetBrains Mono value), `LoadingSkeleton` (pulsing `#1A3050` rects), `ErrorBoundary` (class component with inline retry), `Badge` (6 color variants)
- Updated `layout.tsx` to render `NavSidebar` in a flex row alongside page content
- Added `frontend/.gitignore` (node_modules, .next, tsbuildinfo)

## Verification

```
Backend: 240 passed, 26 skipped, 9 deselected, 2 pre-existing failures (Celery task registration, unrelated)
Frontend type-check: 0 errors (tsc --noEmit clean)
```

## Deviations from Plan

### Auto-added Missing Models (Rule 2)

**Alert ORM model created**
- Found during: Task 1 (dashboard router references `alerts` table)
- Issue: `backend/app/models/alerts.py` and `backtest_runs.py` referenced by plan but absent from codebase
- Fix: Created both ORM models following existing conventions (ingestion_timestamp, Base, etc.)
- Files: `backend/app/models/alerts.py`, `backend/app/models/backtest_runs.py`
- Commit: 4d66f5cf

### Frontend .gitignore Added (Rule 2)

**Missing .gitignore for frontend directory**
- Found during: Task 2 (git status showed node_modules as untracked)
- Issue: Root .gitignore covered `web/node_modules/` but not `frontend/node_modules/`
- Fix: Created `frontend/.gitignore` covering node_modules, .next, tsbuildinfo
- Commit: 4d66f5cf

## Known Stubs

- `GET /api/v1/rl/state` returns `{ agents: [], regime_weights: {} }` - intentional stub. Phase 5 (SAC Ensemble RL) will populate real agent state.
- `total_unrealized_pnl` in `/api/v1/dashboard` is computed from DB - functional but will return 0 on empty tables.

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: unauthenticated-write | backend/app/routers/settings_router.py | PATCH /api/v1/settings modifies runtime config with no auth - any caller can change ENABLE_SHORT_SIDE, STOP_LOSS_PCT, TAKE_PROFIT_PCT |

## Self-Check: PASSED

- `backend/app/models/alerts.py` - FOUND
- `backend/app/models/backtest_runs.py` - FOUND
- `backend/app/routers/dashboard.py` - FOUND
- `backend/app/routers/positions_router.py` - FOUND
- `backend/app/routers/signals_router.py` - FOUND
- `backend/app/routers/alerts_router.py` - FOUND
- `backend/app/routers/backtest_router.py` - FOUND
- `backend/app/routers/settings_router.py` - FOUND
- `backend/app/routers/macro_router.py` - FOUND
- `backend/app/routers/rl_router.py` - FOUND
- `frontend/src/types/api.ts` - FOUND
- `frontend/src/hooks/useSSE.ts` - FOUND
- `frontend/src/components/NavSidebar.tsx` - FOUND
- `frontend/src/components/KPICard.tsx` - FOUND
- `frontend/src/components/LoadingSkeleton.tsx` - FOUND
- `frontend/src/components/ErrorBoundary.tsx` - FOUND
- `frontend/src/components/Badge.tsx` - FOUND
- Commit 4d66f5cf - FOUND
