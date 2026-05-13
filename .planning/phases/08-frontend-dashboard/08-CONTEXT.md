# Phase 8: Frontend Dashboard - Context

**Gathered:** 2026-05-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 delivers a real-time dark-theme dashboard in Next.js 14+ with 8 named views. Server-Sent Events (SSE) from the FastAPI backend stream live updates from Redis pub/sub into the UI. All 8 views must render without errors. SSE latency from event to dashboard update must be under 500ms. The dashboard is a read-mostly operational UI with one read-write surface (Settings view). Phase 9 (hardening) depends on Phase 8 being complete.

</domain>

<decisions>
## Implementation Decisions

### Design System (locked by ROADMAP)
- Background: `#0A1628`
- Primary/accent: `#2471A3`
- Font: Inter (already installed via Google Fonts in layout.tsx)
- Monospace/numeric: JetBrains Mono (for P&L, prices, Sharpe, timestamps)
- Tailwind CSS 4.x already installed; use it for layout/spacing
- Dark theme declared on `<html className="dark">` in layout.tsx (already done)

### The 8 Views
1. **Dashboard** (route: `/`) - current NAV, daily P&L, active position count, macro gate status, last 5 alerts. Overview homepage.
2. **Signal Feed** (route: `/signals`) - most recent 20 earnings events: ticker, EPS gap, quality score, three-axis composite, direction, timestamp
3. **Position Manager** (route: `/positions`) - open positions: symbol, entry price, stop level, target price, unrealized P&L, thesis status (INTACT / MONITOR / BROKEN)
4. **RL Console** (route: `/rl`) - per-agent reward curves (5 SAC agents), current MoE regime weights (bar chart by regime)
5. **Backtest Explorer** (route: `/backtest`) - select a backtest run, display Sharpe/max drawdown/IR/Calmar stats + monthly returns heatmap
6. **Alerting** (route: `/alerts`) - paginated list of alerts from the `alerts` table: event_type, payload summary, delivered status, timestamp
7. **Settings** (route: `/settings`) - read-write: ENABLE_SHORT_SIDE toggle, STOP_LOSS_PCT, TAKE_PROFIT_PCT, alert thresholds. Changes persist via API and take effect without restart.
8. **Macro Monitor** (route: `/macro`) - current macro indicator values (yield curve slope, Sahm rule, LEI, ISM, HYG/LQD spread, JPY/AUD) and composite gate status

### SSE Architecture
- SSE endpoint: `GET /api/v1/events` (already implemented in backend/app/routers/stream.py)
- Channels subscribed: `signals`, `positions`, `rl_state`, `alerts`
- Client: `useEffect` hook with `EventSource` in a shared `useSSE` hook
- Auto-reconnect: yes (EventSource reconnects automatically; log disconnects)
- Heartbeat: 25s (already implemented in stream.py)

### Data Fetching Strategy
- Initial page load: REST API calls (`fetch` with Next.js `cache: 'no-store'`) for current state
- Live updates: SSE events patch the in-memory state (React useState/useReducer)
- No SWR or React Query (keep dependencies minimal)
- Backend REST endpoints to add (if not existing): `/api/v1/positions`, `/api/v1/signals/recent`, `/api/v1/alerts`, `/api/v1/backtest/runs`, `/api/v1/settings`, `/api/v1/macro`

### Component Architecture
- App Router (Next.js App Router - already using in Phase 1 scaffold)
- Shared nav sidebar with links to all 8 views
- Server Components for initial data fetching; Client Components (marked 'use client') for SSE subscription and interactive state
- No external UI library (Tailwind + custom components only)
- Charts: use a lightweight lib — `recharts` (wide Next.js community use) for reward curves and monthly heatmap

### Claude's Discretion
- Exact chart styling and color palette for recharts components
- Sidebar layout (collapsible vs fixed)
- API endpoint structure for the new backend routes
- Error boundary and loading skeleton implementation details
- Exact monthly returns heatmap color scale

</decisions>

<code_context>
## Existing Code Insights

### Frontend (already exists)
- `frontend/app/layout.tsx` — dark layout with Inter, `#0A1628` bg, `className="dark"`
- `frontend/app/page.tsx` — skeleton homepage
- `frontend/app/globals.css` — global styles
- `frontend/package.json` — Next.js 16.2.4, React 19, Tailwind 4.2.4, TypeScript 6.0.3
- `frontend/next.config.ts` — Next.js config
- No recharts installed yet — needs adding

### Backend (already exists)
- `backend/app/routers/stream.py` — SSE endpoint at `GET /events`, subscribes to `["signals", "positions", "rl_state", "alerts"]`
- `backend/app/routers/orders.py` — POST /api/v1/orders (Phase 7)
- `backend/app/routers/health.py` — GET /api/v1/health
- `backend/app/models/portfolio_positions.py` — PortfolioPosition ORM
- `backend/app/models/alerts.py` — Alert ORM with VALID_EVENT_TYPES (Phase 7)
- `backend/app/models/backtest_runs.py` — BacktestRun ORM
- `backend/app/config.py` — Settings with ENABLE_SHORT_SIDE, STOP_LOSS_PCT, TAKE_PROFIT_PCT
- `backend/app/main.py` — FastAPI app with lifespan

### Integration Points
- SSE stream path: `GET /api/v1/events` (stream router prefix `/api/v1`)
- New REST endpoints needed: positions, signals/recent, alerts, backtest/runs, settings (GET + PATCH), macro
- Settings PATCH must update runtime values (not require restart) — use Settings mutation or a separate config store
- Alerts table already has event_type, payload, created_at, delivered_sendgrid, delivered_slack, rate_limited

</code_context>

<specifics>
## Specific Requirements

- FR-9.1: All 8 views render in Next.js App Router dark theme
- FR-9.2: SSE connection delivers live updates under 500ms latency
- FR-9.3: Dashboard view shows NAV, P&L, active positions, macro gate, last 5 alerts from live data
- FR-9.4: Signal Feed shows 20 most recent earnings events; Position Manager shows open positions with thesis status; RL Console shows reward curves and MoE weights; Backtest Explorer with run selector and heatmap; Alerting view; Settings view; Macro Monitor view

</specifics>

<deferred>
## Deferred Ideas

- Complex charting (D3, custom canvas animations)
- Authentication/auth guard (all views public in Phase 8)
- Mobile responsive layout (desktop-first for Phase 8)
- Historical signal replay / backtesting UI beyond what backtest_runs provides
- WebSocket (SSE is sufficient per Phase 8 requirements)
- Dark/light theme toggle (always dark)

</deferred>
