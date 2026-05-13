---
phase: "08"
plan: "02"
subsystem: "frontend-dashboard"
tags: ["nextjs", "react", "typescript", "sse", "tailwind"]
dependency_graph:
  requires: ["08-01-PLAN.md"]
  provides: ["dashboard-page", "signal-feed-page", "positions-page"]
  affects: ["frontend-dashboard"]
tech_stack:
  added: []
  patterns:
    - "Next.js App Router Server Component + Client Component split"
    - "SSE prepend-and-trim pattern for signals/alerts (max 20/5)"
    - "SSE in-place patch by symbol key for positions"
    - "setInterval 30s background refresh for dashboard KPIs"
key_files:
  created:
    - frontend/app/page.tsx
    - frontend/app/signals/page.tsx
    - frontend/app/positions/page.tsx
    - frontend/src/components/DashboardClient.tsx
    - frontend/src/components/LastAlertsPanel.tsx
    - frontend/src/components/SignalFeedClient.tsx
    - frontend/src/components/PositionsClient.tsx
    - frontend/src/components/PageHeader.tsx
    - frontend/src/components/SkeletonRect.tsx
    - frontend/src/components/SkeletonLine.tsx
    - frontend/src/lib/fetcher.ts
  modified:
    - frontend/src/types/api.ts
decisions:
  - "Adapted KPI grid to actual /api/v1/dashboard shape (position_count, total_unrealized_pnl, macro_gate_open) instead of plan-spec nav/daily_pnl fields"
  - "Added unrealized_pnl_pct and thesis_status fields to Position interface to match position manager requirements"
  - "Fourth KPI card shows System Status LIVE since backend does not expose a macro score numeric field"
  - "LastAlertsPanel uses alert.category for event-type badge since AlertRecord has no event_type field"
metrics:
  duration: "~20 min"
  completed: "2026-05-13"
  tasks: 2
  files: 12
---

# Phase 08 Plan 02: Dashboard + Signal Feed + Position Manager Views Summary

Three Next.js App Router pages with Server Components for initial data fetch, Client Components for live SSE subscription, and full-fidelity table layouts matching UI-SPEC design contracts.

## Tasks Completed

### Task 1: Dashboard View

- Replaced placeholder `app/page.tsx` with a Server Component that calls `fetcher<DashboardData>('/api/v1/dashboard')` and passes result to `DashboardClient`
- `DashboardClient` renders 4-column KPI grid: Unrealized P&L (color-coded positive/negative), Open Positions, Macro Gate (Inter 20px 600, OPEN=green/GATED=orange), System Status
- `LastAlertsPanel` shows up to 5 alerts with event-type badge, truncated message, and relative timestamp ("2m ago" format)
- SSE `alerts` channel prepends new `AlertRecord` and trims to 5
- SSE `positions` channel increments/decrements `position_count` on open/close events
- 30s `setInterval` refresh loop replaces full `DashboardData` from backend
- `DashboardSkeleton` shown via `<Suspense>` during server fetch; `<ErrorBoundary>` wraps the whole page
- Empty state: "No live data yet" heading + "Waiting for signals..." body when `initialData` is null

Also created missing infrastructure from plan dependencies (Rule 2):
- `src/lib/fetcher.ts` - `fetcher<T>(path)` using `NEXT_PUBLIC_API_URL` + no-store cache
- `src/components/PageHeader.tsx` - title + optional subtitle
- `src/components/SkeletonRect.tsx` - pulsing skeleton block with configurable height/radius
- `src/components/SkeletonLine.tsx` - pulsing skeleton text line

### Task 2: Signal Feed and Position Manager

**Signal Feed (`/signals`):**
- Server Component fetches `/api/v1/signals/recent?limit=20`
- `SignalFeedClient` renders `table-layout: fixed` with 8 columns: TIMESTAMP, SYMBOL, DIRECTION, EPS GAP, QUALITY, 3-AXIS, SIZE, STATUS
- SSE `signals` channel maps `SSESignalPayload` to `SignalRow`, prepends, trims to 20
- Direction badge variants: long=positive(green), short=negative(red), hold=muted
- All numeric cells use `.mono` class; EPS Gap color-coded positive/negative

**Position Manager (`/positions`):**
- Server Component fetches `/api/v1/positions`
- `PositionsClient` renders `table-layout: fixed` with 9 columns: SYMBOL, QTY, ENTRY, STOP, TARGET, CURRENT, UNREAL. P&L, THESIS, UPDATED
- SSE `positions` channel: patches in-place by symbol key; removes row when `status === "closed"`
- Stop column color: #E74C3C; Target column: #27AE60; Unrealized P&L: JetBrains Mono 16px 500, color-coded
- Thesis badge: INTACT=positive(green), MONITOR=warning(orange), BROKEN=negative(red)

## Verification

```
npm run type-check: 0 errors (tsc --noEmit clean)
npm run build: success — / (dynamic), /signals (dynamic), /positions (dynamic)
```

## Deviations from Plan

### Auto-added Missing Infrastructure (Rule 2)

**fetcher.ts, PageHeader, SkeletonRect, SkeletonLine not created in 08-01**
- Found during: Task 1 (plan references these as context from 08-01 but they were absent)
- Issue: 4 files referenced in `<context>` block were not in the 08-01 SUMMARY created files list
- Fix: Created all 4 missing files inline before building page components
- Files: `frontend/src/lib/fetcher.ts`, `frontend/src/components/PageHeader.tsx`, `frontend/src/components/SkeletonRect.tsx`, `frontend/src/components/SkeletonLine.tsx`
- Commit: 7f621d4f

### API Shape Mismatch Adaptation (Rule 1)

**DashboardData fields differ from plan spec**
- Found during: Task 1 (plan spec says `nav`, `daily_pnl`, `daily_pnl_pct`, `macro_score` but actual `api.ts` has `position_count`, `total_unrealized_pnl`, `macro_gate_open: boolean|null`)
- Issue: Plan was written against a projected API shape; actual backend from 08-01 uses different field names
- Fix: Adapted KPI grid to use actual fields. "Portfolio NAV" card replaced with "Unrealized P&L" using `total_unrealized_pnl`. "Daily P&L" card replaced with "Open Positions". Macro Gate uses `macro_gate_open: boolean` with OPEN/GATED text. Fourth card shows "System Status: LIVE"
- Files: `frontend/src/components/DashboardClient.tsx`
- Commit: 7f621d4f

### Position Type Extended (Rule 2)

**Position interface missing unrealized_pnl_pct and thesis_status**
- Found during: Task 2 (PositionsClient requires these fields per UI-SPEC)
- Issue: `api.ts` Position interface lacked `unrealized_pnl_pct` and `thesis_status` fields
- Fix: Added both fields to the interface with correct types
- Files: `frontend/src/types/api.ts`
- Commit: 7f621d4f

### AlertRecord field mapping in LastAlertsPanel (Rule 1)

**AlertRecord has no event_type field**
- Found during: Task 1 (plan says use `alert.event_type` for badge but `AlertRecord` only has `category` and `level`)
- Fix: Use `alert.category ?? alert.level ?? "alert"` for the event-type badge label and color lookup
- Files: `frontend/src/components/LastAlertsPanel.tsx`
- Commit: 7f621d4f

## Known Stubs

- "System Status: LIVE" fourth KPI card is a visual stub. The backend `/api/v1/dashboard` does not expose a system health field. A future plan should add a `/api/v1/health` endpoint and wire it here.
- `unrealized_pnl_pct` added to `Position` interface but the backend `/api/v1/positions` router (from 08-01) does not currently return this field. The column will show "-" until the backend is updated. File: `frontend/src/components/PositionsClient.tsx` line 64.
- `thesis_status` added to `Position` interface but the backend `portfolio_positions` table has a `status` column (string) not `thesis_status`. The Thesis badge will show "-" until the backend router maps `status` to `thesis_status`. File: `frontend/src/components/PositionsClient.tsx`.

## Self-Check: PASSED

- `frontend/app/page.tsx` - FOUND
- `frontend/app/signals/page.tsx` - FOUND
- `frontend/app/positions/page.tsx` - FOUND
- `frontend/src/components/DashboardClient.tsx` - FOUND
- `frontend/src/components/LastAlertsPanel.tsx` - FOUND
- `frontend/src/components/SignalFeedClient.tsx` - FOUND
- `frontend/src/components/PositionsClient.tsx` - FOUND
- `frontend/src/components/PageHeader.tsx` - FOUND
- `frontend/src/components/SkeletonRect.tsx` - FOUND
- `frontend/src/components/SkeletonLine.tsx` - FOUND
- `frontend/src/lib/fetcher.ts` - FOUND
- Commit 7f621d4f - FOUND
- Commit 8ec28bba - FOUND
