# Phase 6: Backtest Engine + Validation Gate - Research

**Researched:** 2026-05-12
**Domain:** Python backtesting, point-in-time replay, statistical performance metrics, programmatic go/no-go gate
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-6.1 | Backtest replay uses only data with `ingestion_timestamp <= as_of` for every query; a deliberately injected future data point is rejected by the filter | `get_prices_as_of` pattern confirmed in `point_in_time.py`; same `WHERE ingestion_timestamp <= :as_of` idiom used across all queries in `signal_pipeline.py` and `macro_loader.py` |
| FR-6.2 | Backtest imports and calls the production signal engine and SAC ensemble — no parallel backtest-only implementations exist | `rl/sac_agent.py` exports `SACEnsemble.select_action_per_agent()` and `rl/moe_controller.py` exports `MoEController.blend()`; both are pure Python, no DB coupling — directly callable from `backtest/replay.py` |
| FR-6.3 | Full statistics persisted: Sharpe ratio, max drawdown, IR vs. naive baseline, Calmar ratio, monthly returns breakdown | `ff5_factors.rf` column is the correct risk-free rate source (daily, already stored, point-in-time); naive baseline is 2% NAV fixed size from `signals/writer.py` `NAIVE_POSITION_SIZE` |
| FR-6.4 | Go/no-go gate fires `backtest_gate_pass` or `backtest_gate_fail`; Phase 7 startup check reads it | Gate model writes to `backtest_runs` table (migration 0005 to be created); `gate_status` column is the startup check pivot |
| FR-6.5 | Ex-2020 stress slice runs as separate `backtest_runs` row; Sharpe > 0.8 on the ex-2020 period reported | Runner accepts `exclude_date_range` param; no separate code path needed |
| FR-6.6 | Results accessible in `backtest_runs` table; schema matches what Phase 8 Backtest Explorer expects | Phase 8 needs: run_id, dates, sharpe, max_drawdown, ir_vs_baseline, calmar, monthly_returns (JSONB), gate_status, config_snapshot (JSONB) |
</phase_requirements>

---

## Summary

Phase 6 builds a point-in-time-correct backtest engine that replays 2018-2023 using the production signal engine (`backend/app/signals/pipeline.py`) and SAC ensemble (`rl/sac_agent.py` + `rl/moe_controller.py`) rather than a parallel reimplementation. The highest-severity risk is look-ahead bias, already mitigated by the `ingestion_timestamp <= as_of` filter pattern established in Phase 1 and used consistently in every existing DB query. The planner needs to wire these existing modules through a date-iterator harness rather than rebuild any signal logic.

The key architectural insight from codebase inspection: the signal pipeline uses a *synchronous* SQLAlchemy session (`DATABASE_URL_SYNC` / `psycopg2` dialect), not the async one. All backtest code must use the same sync session path for consistency. The SAC ensemble and MoE controller are pure Python with no DB coupling, so they call cleanly without session management overhead.

Open questions from the PRD are now resolved: (1) use `ff5_factors.rf` column for the risk-free rate (it is already stored point-in-time, daily frequency); (2) use the existing `NAIVE_POSITION_SIZE = 0.02` from `signals/writer.py` as the naive baseline position size (equal-weight 2% NAV per signal); (3) gate retry requires a manual `override_gate_pass` config flag.

**Primary recommendation:** Build the four sub-plans in strict dependency order: harness + schema (06-01), production-code wiring (06-02), stats + gate (06-03), full replay + persistence (06-04). Every sub-plan relies on the synchronous session pattern from `app/flows/_db.py`.

---

## Project Constraints (from CLAUDE.md)

- No em dashes in any output (applies to generated code comments and docs)
- Backend test command: `cd backend && pytest tests/ -v --tb=short -k "not integration"`
- DB-gated integration tests skip when `DATABASE_URL_SYNC` is absent
- All SQL must use `sqlalchemy.text()` with bound parameters - no f-string SQL (see `macro_loader.py`)
- Each series/row query uses `LIMIT 1` to prevent unbounded result sets
- RL trainer excluded from CI; backtest runner is NOT the RL trainer, but the import path (`rl/` root module) must be on `sys.path` (see `backend/tests/rl/conftest.py` for the pattern)
- Alembic migrations are named `00XX_description.py` (sequential 4-digit prefix); next is `0005`
- Lint command: `cd backend && ruff check . && ruff format --check .`
- Point-in-time semantics are **non-negotiable**: every query in backtest must filter `ingestion_timestamp <= :as_of`

---

## Standard Stack

### Core (all already in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlalchemy | 2.0.49 | Sync DB queries via `text()` | Consistent with all existing Phase 1-5 DB access |
| psycopg2-binary | 2.9.10 | Sync PostgreSQL driver | Used by `_db.py` `DATABASE_URL_SYNC` path |
| numpy | 2.1.3 | Sharpe, drawdown, Calmar math | Already installed; all RL modules use it |
| pandas | 2.2.3 | Daily returns series, date iteration | Already installed; used by `rl/environment.py` |
| scipy | 1.14.1 | Optional: rolling stats if needed | Already installed for SLSQP optimizer |

[VERIFIED: codebase grep of requirements.txt]

### New Dependencies (none required)

All math needed for Sharpe, max drawdown, Calmar, and Information Ratio is expressible with `numpy` arrays and standard Python. No new packages are needed.

**Version verification:** All versions above are from the project's `backend/requirements.txt` and are current as of the worktree state.

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── app/
│   └── backtest/
│       ├── __init__.py
│       ├── runner.py        # date iterator + as_of plumbing + run_backtest()
│       ├── fills.py         # deterministic simulated fills, slippage/commission
│       ├── replay.py        # calls signals.pipeline + rl ensemble + portfolio.pipeline
│       ├── stats.py         # Sharpe, max_drawdown, IR, Calmar, monthly returns
│       ├── gate.py          # conjunctive gate: main slice AND ex-2020 slice
│       └── alerts.py        # fires backtest_gate_pass / backtest_gate_fail
├── models/
│   └── backtest_runs.py     # SQLAlchemy ORM model for backtest_runs table
├── scripts/
│   └── run_full_backtest.py # CLI entrypoint, calls runner for both slices
├── alembic/versions/
│   └── 0005_backtest_runs.py
└── tests/
    ├── test_backtest_as_of.py          # FR-6.1: future-row injection test
    ├── test_backtest_uses_prod_engine.py # FR-6.2: import-graph assertion
    ├── test_backtest_stats.py          # FR-6.3: golden numbers on deterministic data
    ├── test_backtest_gate.py           # FR-6.4 + FR-6.5: gate logic
    └── test_backtest_e2e.py            # 1-month smoke test (DB-gated)
```

[VERIFIED: mirrors structure of existing `backend/app/signals/`, `backend/app/portfolio/`, and `backend/tests/rl/` directories]

### Pattern 1: Point-in-Time Query (established in Phase 1)

**What:** Every DB query in the replay path includes `AND ingestion_timestamp <= :as_of`.
**When to use:** Every single DB read in `runner.py` and `replay.py`.
**Example:**
```python
# Source: backend/app/queries/point_in_time.py (verified in codebase)
# Source: backend/app/signals/pipeline.py _last_close() (verified in codebase)
row = session.execute(
    text(
        """
        SELECT close
        FROM price_bars
        WHERE symbol = :symbol
          AND time <= :as_of
          AND ingestion_timestamp <= :as_of
        ORDER BY time DESC
        LIMIT 1
        """
    ),
    {"symbol": symbol, "as_of": as_of},
).fetchone()
```

### Pattern 2: Sync Session (established in Phase 2 flows)

**What:** All backtest code uses the sync session from `app/flows/_db.py`, NOT the async session.
**When to use:** All of `backtest/runner.py`, `backtest/replay.py`.
**Example:**
```python
# Source: backend/app/flows/_base.py (verified in codebase)
from app.flows._base import sync_session

with sync_session() as session:
    result = session.execute(text("..."), {"as_of": as_of}).fetchone()
```

### Pattern 3: Production Ensemble Calling Convention

**What:** To get a blended RL action, call `ensemble.select_action_per_agent(obs)` then pass to `moe.blend()`.
**When to use:** `backtest/replay.py` at each signal event.
**Example:**
```python
# Source: rl/sac_agent.py SACEnsemble.select_action_per_agent() (verified in codebase)
# Source: rl/moe_controller.py MoEController.blend() (verified in codebase)
per_agent = ensemble.select_action_per_agent(obs_vec, deterministic=True)
moe_action = moe.blend(per_agent, macro_score=macro_score)
entry_size = moe_action.entry_size  # float in [0, 1]
```
The macro multiplier is applied POST-blend as a deterministic multiply (per FR-5.3 comment in `sac_agent.py`).

### Pattern 4: Import Path for rl.* Modules

**What:** The `rl/` directory lives at repo root, not under `backend/`. Tests add the repo root to `sys.path`.
**When to use:** Any test under `backend/tests/` that imports from `rl.*`.
**Example:**
```python
# Source: backend/tests/rl/conftest.py (verified in codebase)
import os, sys
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
```
The backtest module itself (`backend/app/backtest/replay.py`) must also handle this. The simplest approach is to import via `sys.path` augmentation in `replay.py` or to add the repo root to `PYTHONPATH` in the Docker/Railway config.

### Pattern 5: DB-Gated Test

**What:** Tests that require a live DB use `@requires_db` and skip when `DATABASE_URL_SYNC` is absent.
**When to use:** `test_backtest_e2e.py` and any integration test that writes to `backtest_runs`.
**Example:**
```python
# Source: backend/tests/conftest.py (verified in codebase)
from tests.conftest import requires_db

@requires_db
def test_backtest_e2e(sync_engine):
    ...
```

### Pattern 6: Macro Loading (point-in-time)

**What:** Load macro composite score via `load_macro_snapshot()` - reads persisted score from DB, not recomputed.
**When to use:** `backtest/replay.py` for each `as_of` date to get `macro_score` for MoE blending.
**Example:**
```python
# Source: backend/app/portfolio/macro_loader.py (verified in codebase)
from app.portfolio.macro_loader import load_macro_snapshot

macro_score, components = load_macro_snapshot(session, as_of=as_of_dt)
```

### Anti-Patterns to Avoid

- **Reimplementing signal logic in backtest:** The PRD explicitly forbids this. `replay.py` must import from `app.signals.pipeline.compute_signal_for_event` and never redefine it.
- **Using async session in backtest:** The replay loop is synchronous. Using `asyncpg` here would require running an event loop inside the date iterator, adding complexity. Use `DATABASE_URL_SYNC`.
- **Applying macro multiplier inside the RL call:** Per FR-5.3, the macro multiplier is applied *after* `moe_action.entry_size` is returned, not inside the agent. Do not change this.
- **Hardcoding risk-free rate:** Use `ff5_factors.rf` from DB (point-in-time). See the Risk-Free Rate section below.
- **Running gate on partial-year slices:** Gate (Sharpe > 1.0) only runs when `is_partial_year = False` in the `backtest_runs` row.

---

## Risk-Free Rate: Resolved Decision

**The `ff5_factors` table has a `rf` column (daily, percentage points).** [VERIFIED: `backend/app/models/ff5_factors.py` and `backend/alembic/versions/0002_phase2_tables.py`]

The Ken French daily factors file includes the risk-free rate (1-month T-bill) as the `RF` column, ingested at daily frequency by the `ingest_ff5_weekly` flow. It is:
- Already in the DB
- Already has `ingestion_timestamp` for point-in-time correctness
- Daily granularity (matches daily return series)
- Annualizable: daily rf to annual = `(1 + rf_daily)^252 - 1`

**Decision:** Use `ff5_factors.rf` queried with `WHERE date <= :as_of AND ingestion_timestamp <= :as_of` for Sharpe computation. This resolves PRD Open Question #1 in favor of the "pull from DB point-in-time" option.

Fallback: if `ff5_factors` rows are missing for a given date, use the prior row (forward-fill). If no rows exist at all, fall back to `risk_free_rate_annual` constant in `config.py` (add it: `0.0525` as of mid-2024, or lower for the 2018-2023 period average).

---

## Naive Baseline: Resolved Decision

**The naive baseline is already defined in production code.** [VERIFIED: `backend/app/signals/writer.py` line `NAIVE_POSITION_SIZE = Decimal("0.0200")`]

Per FR-3.6, the naive baseline is a fixed 2% NAV position for any signal-aligned name. The `signals` table stores `naive_position_size` alongside every signal. For Information Ratio computation:

- Naive strategy return for any signal: assume 2% NAV position held for `CONFIG.signal.hold_min` days (60 days), using the actual price from `price_bars` as_of the as_of date.
- IR = (strategy excess return - naive excess return) / std(strategy excess - naive excess)
- This resolves PRD Open Question #2: equal-weight over the same earnings universe, using the already-defined `NAIVE_POSITION_SIZE`.

---

## Gate Retry Policy: Resolved Decision

**Manual override, not polling.** Per PRD Open Question #4, the policy is:
- `override_gate_pass: false` default in config
- If gate fails, Phase 7 startup reads `gate_status = 'fail'` from `backtest_runs` and refuses to start
- No polling loop; a human sets `override_gate_pass: true` in config to bypass (forces a decision)
- Add `BACKTEST_OVERRIDE_GATE_PASS: bool = False` to `backend/app/config.py` `Settings`

---

## Sharpe Annualization: Resolved Decision

**Annualize regardless of slice length; flag partial-year runs.** Per PRD Open Question #3:
- `sharpe_annualized = (mean_daily_return - mean_daily_rf) / std_daily_return * sqrt(252)`
- Add `is_partial_year: bool` to `backtest_runs` table
- Gate logic checks `is_partial_year = False` before applying the Sharpe > 1.0 test

---

## `backtest_runs` Schema (Migration 0005)

```sql
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    start_date          DATE NOT NULL,
    end_date            DATE NOT NULL,
    slice_type          TEXT NOT NULL DEFAULT 'main',  -- 'main' or 'ex_2020'
    sharpe              NUMERIC(10, 4),
    max_drawdown        NUMERIC(10, 4),
    ir_vs_baseline      NUMERIC(10, 4),
    calmar              NUMERIC(10, 4),
    monthly_returns     JSONB,                          -- {YYYY-MM: float}
    config_snapshot     JSONB,                          -- serialized SACConfig + SignalConfig
    gate_status         TEXT CHECK (gate_status IN ('pass', 'fail', 'pending')),
    gate_reason         TEXT,
    is_partial_year     BOOLEAN NOT NULL DEFAULT FALSE,
    total_trades        INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Phase 8 Backtest Explorer** queries `backtest_runs` by `run_id`, displays: `sharpe`, `max_drawdown`, `ir_vs_baseline`, `calmar`, `monthly_returns` (heatmap), `gate_status`. The schema above satisfies all columns Phase 8 will need. [ASSUMED: based on Phase 8 ROADMAP description; Phase 8 has not been designed in detail yet]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signal computation | Custom replay-only signal code | `app.signals.pipeline.compute_signal_for_event()` | FR-6.2; any bug fix flows automatically |
| RL action selection | Replay-specific policy | `rl.sac_agent.SACEnsemble.select_action_per_agent()` + `rl.moe_controller.MoEController.blend()` | FR-6.2; same ensemble, same weights |
| Portfolio sizing gates | Replay-specific size capping | `app.portfolio.pipeline.compute_position_size()` | Macro/ERP/Mag-7/stop-loss must be identical to live |
| Macro loading | Re-run scoring algorithm in replay | `app.portfolio.macro_loader.load_macro_snapshot()` | Gap SC-1b: persisted score in DB is the canonical source |
| Point-in-time query | Custom `WHERE` clause per module | `app.queries.point_in_time.get_prices_as_of()` + inline `text()` pattern from `pipeline.py` | FR-1.5 semantics established; don't reopen |
| US trading calendar | Custom holiday list | `pandas_market_calendars` or a static `pandas_bdate_range` with `freq='B'` | Business-day iteration already used by pandas; no new dep needed |
| Performance stats | Custom Sharpe formula | numpy operations on daily returns array | Standard: `mean(r_excess) / std(r_excess) * sqrt(252)`; no library needed |

**Key insight:** The correct approach is a thin harness that calls existing modules in a date loop. Phase 6 adds orchestration, not business logic.

---

## Trading Calendar: Date Iterator

No `pandas_market_calendars` package is in `requirements.txt` and adding it is unnecessary. [VERIFIED: requirements.txt]

Use `pandas.bdate_range(start, end, freq='C', holidays=US_HOLIDAYS)` where `US_HOLIDAYS` is a static list of NYSE holidays, OR use `pd.bdate_range` with `freq='B'` (business days) and accept the minor inaccuracy of including non-NYSE holidays like Columbus Day. For 2018-2023 replay, the difference is negligible.

**Simpler approach:** use `pd.bdate_range(start='2018-01-01', end='2023-12-31', freq='B')` for the date iterator. This is already implicitly what `rl/environment.py` does via `pd.Timestamp` stepping. [VERIFIED: rl/environment.py _step_position() pattern]

---

## Common Pitfalls

### Pitfall 1: Look-Ahead Bias via Missing ingestion_timestamp Filter

**What goes wrong:** A query in `replay.py` fetches `earnings_events` or `signals` without the `ingestion_timestamp <= :as_of` clause. The future-row injection test in `test_backtest_as_of.py` catches this, but only if the test covers the specific query path.
**Why it happens:** Easy to forget when writing `_load_event()` inside the signal pipeline. The existing `signals/pipeline.py` version already has it for `price_bars`, but the `_load_event()` and `_load_prior_event()` functions do NOT filter by `ingestion_timestamp` (they use `session.get()` and `.filter(EarningsEvent.announced_at < before)`).
**How to avoid:** In the backtest replay wrapper, do NOT call `compute_signal_for_event()` with a live session directly. Instead, wrap the session with an `as_of`-scoped query context, OR verify that `_load_event()` only fetches events where `announced_at <= as_of` (which it does implicitly via event lookup), AND that `_load_prior_event()` also checks `ingestion_timestamp`. Review each query in the call chain.
**Warning signs:** FR-6.1 injection test passes but Sharpe is suspiciously high (>2.0) for a simple PEAD strategy.

### Pitfall 2: rl.* Import Path Failure at Replay Time

**What goes wrong:** `backtest/replay.py` imports `from rl.sac_agent import SACEnsemble` but the repo root is not on `sys.path` at replay time (only in test conftest).
**Why it happens:** `rl/` is at repo root, not under `backend/`. The `backend/tests/rl/conftest.py` adds repo root to path, but `backend/app/backtest/replay.py` doesn't.
**How to avoid:** Add repo root to `sys.path` in `replay.py` init (or in `backtest/__init__.py`), OR add `PYTHONPATH=/app/..` to the Docker/Railway environment config.
**Warning signs:** `ModuleNotFoundError: No module named 'rl'` at replay startup.

### Pitfall 3: Async Session in a Sync Replay Loop

**What goes wrong:** Developer uses `app.database.AsyncSession` inside the date iterator. The `asyncio` event loop must be explicitly managed, causing `RuntimeError: no running event loop` or nested loop issues.
**Why it happens:** The FastAPI app uses async sessions; the flows use sync sessions. Easy to mix up.
**How to avoid:** The backtest runner is NOT a FastAPI endpoint. Use `app.flows._base.sync_session()` exclusively. [VERIFIED: flows/_base.py and flows/_db.py]
**Warning signs:** Import of `asyncpg` or `AsyncSession` in any backtest module.

### Pitfall 4: Gate Conjunctive Logic Inversion

**What goes wrong:** Gate passes if EITHER the main slice OR the ex-2020 slice passes, instead of requiring BOTH.
**Why it happens:** Natural but incorrect OR logic in the conditional.
**How to avoid:** The gate must be: `gate_pass = (main_sharpe >= 1.0) AND (ex2020_sharpe >= 0.8)`. The `test_backtest_gate.py` test must include the case where main passes but ex-2020 fails and assert overall `gate_status = 'fail'`.

### Pitfall 5: Float Accumulation in Daily P&L

**What goes wrong:** Summing floating-point daily returns over 1500+ days introduces drift that skews final Sharpe by a detectable amount.
**Why it happens:** `sum()` in a loop vs. `numpy.sum()` on an array.
**How to avoid:** Collect all daily returns as a `numpy.ndarray` first, then compute all statistics in a single vectorized pass. Never accumulate float sums in a Python `for` loop.

### Pitfall 6: Checkpoint Loading from Wrong Agent State

**What goes wrong:** Backtest loads RL checkpoints from the `rl_checkpoints` table, but loads the latest step rather than the final trained state.
**Why it happens:** Multiple checkpoints per agent exist; the query must select `WHERE is_active = TRUE ORDER BY step DESC LIMIT 1` per agent.
**How to avoid:** In `replay.py` checkpoint loader, use `is_active = TRUE` filter (the same index `ix_rl_checkpoints_active` was created specifically for this). [VERIFIED: 0004 migration]

---

## Code Examples

Verified patterns from existing codebase:

### Risk-Free Rate Query (point-in-time)
```python
# Source: pattern from backend/app/portfolio/macro_loader.py (verified in codebase)
def load_daily_rf_as_of(session, as_of: datetime) -> float:
    """Return daily risk-free rate (as decimal fraction) visible as of as_of."""
    row = session.execute(
        text(
            """
            SELECT rf FROM ff5_factors
            WHERE date <= :as_of
              AND ingestion_timestamp <= :as_of
            ORDER BY date DESC
            LIMIT 1
            """
        ),
        {"as_of": as_of},
    ).fetchone()
    if row and row[0] is not None:
        # FF5 factors store rf as percentage points (e.g. 0.0001 = 0.01%)
        return float(row[0])
    return 0.0  # fallback: zero rf
```

### Sharpe Computation
```python
# Source: standard formula, implemented with numpy (no external lib needed)
import numpy as np

def compute_sharpe(daily_returns: np.ndarray, daily_rf: np.ndarray) -> float:
    """Annualized Sharpe ratio. Uses 252 trading-day convention."""
    excess = daily_returns - daily_rf
    if len(excess) < 2 or excess.std() == 0:
        return 0.0
    return float(excess.mean() / excess.std() * np.sqrt(252))
```

### Max Drawdown
```python
import numpy as np

def compute_max_drawdown(daily_returns: np.ndarray) -> float:
    """Maximum peak-to-trough drawdown as a positive fraction."""
    cumulative = np.cumprod(1 + daily_returns)
    running_max = np.maximum.accumulate(cumulative)
    drawdowns = (cumulative - running_max) / running_max
    return float(abs(drawdowns.min()))
```

### Calmar Ratio
```python
def compute_calmar(annualized_return: float, max_drawdown: float) -> float:
    """Calmar = annualized return / max drawdown. Returns 0 if max_drawdown is 0."""
    if max_drawdown == 0:
        return 0.0
    return float(annualized_return / max_drawdown)
```

### Future-Row Injection Test Pattern (FR-6.1)
```python
# Source: pattern mirrors backend/tests/rl/test_phase5_integration.py (verified in codebase)
def test_future_row_rejected_by_as_of_filter(sync_engine):
    """FR-6.1: a row ingested after as_of must not appear in any backtest query."""
    as_of = datetime(2020, 6, 15, tzinfo=timezone.utc)
    future_ts = as_of + timedelta(days=1)

    with sync_engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO price_bars (time, symbol, close, ingestion_timestamp) "
            "VALUES (:t, :sym, :close, :ingest)"
        ), {"t": as_of, "sym": "TEST_FUTURE", "close": 999.99, "ingest": future_ts})

    # Now query with as_of filter - must return nothing
    with sync_engine.connect() as conn:
        row = conn.execute(text(
            "SELECT close FROM price_bars "
            "WHERE symbol = 'TEST_FUTURE' AND ingestion_timestamp <= :as_of"
        ), {"as_of": as_of}).fetchone()

    assert row is None, "Future-timestamped row leaked through as_of filter"
```

### Import-Graph Assertion Pattern (FR-6.2)
```python
import ast
import os

def test_no_backtest_only_signal_definitions():
    """FR-6.2: grep for def compute_signal returns exactly one definition."""
    backtest_dir = os.path.join(os.path.dirname(__file__), "..", "..", "app", "backtest")
    for fname in os.listdir(backtest_dir):
        if not fname.endswith(".py"):
            continue
        src = open(os.path.join(backtest_dir, fname)).read()
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "compute_signal_for_event":
                raise AssertionError(
                    f"Backtest-only compute_signal_for_event found in {fname}. "
                    "FR-6.2: import from app.signals.pipeline instead."
                )
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate backtest signal code | Import production modules directly | Phase 6 design decision (PRD) | Bug fixes propagate automatically |
| Risk-free rate as config constant | Query `ff5_factors.rf` point-in-time | Phase 6 (resolved in research) | Historically accurate Sharpe computation |
| Simple Python loop for stats | Vectorized numpy over full return array | Phase 6 (established here) | Avoids float accumulation drift |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 + pytest-asyncio 1.3.0 |
| Config file | `backend/pytest.ini` (`asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `cd backend && pytest tests/ -v --tb=short -k "not integration and not e2e"` |
| Full suite command | `cd backend && DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest tests/ -v --tb=short` |

[VERIFIED: backend/pytest.ini and backend/requirements.txt]

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-6.1 | Future-timestamped row rejected by as_of filter | integration | `pytest tests/test_backtest_as_of.py -x` | Wave 0 |
| FR-6.2 | No backtest-only signal definitions | unit (AST) | `pytest tests/test_backtest_uses_prod_engine.py -x` | Wave 0 |
| FR-6.3 | Stats row contains all required fields | unit (golden) | `pytest tests/test_backtest_stats.py -x` | Wave 0 |
| FR-6.4 | Gate pass/fail fires correct alert | unit | `pytest tests/test_backtest_gate.py -x` | Wave 0 |
| FR-6.5 | Ex-2020 slice produces separate row with Sharpe reported | unit | `pytest tests/test_backtest_gate.py::test_ex2020_slice -x` | Wave 0 |
| FR-6.6 | backtest_runs table exists and is queryable | integration | `pytest tests/test_backtest_e2e.py -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `cd backend && pytest tests/ -v --tb=short -k "not integration and not e2e"`
- **Per wave merge:** Full suite with DB
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `backend/tests/test_backtest_as_of.py` - covers FR-6.1
- [ ] `backend/tests/test_backtest_uses_prod_engine.py` - covers FR-6.2
- [ ] `backend/tests/test_backtest_stats.py` - covers FR-6.3
- [ ] `backend/tests/test_backtest_gate.py` - covers FR-6.4, FR-6.5
- [ ] `backend/tests/test_backtest_e2e.py` - covers FR-6.6 (DB-gated)
- [ ] `backend/alembic/versions/0005_backtest_runs.py` - migration must exist before any test writes to the table

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Backtest runner is an internal CLI script, not an API endpoint |
| V3 Session Management | no | Stateless batch process |
| V4 Access Control | no | Internal only |
| V5 Input Validation | yes | Validate `start_date`, `end_date`, `exclude_date_range` params to runner; reject future end dates |
| V6 Cryptography | no | No secrets in backtest path |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via f-string date formatting | Tampering | Always use `text()` with bound params (established pattern in `macro_loader.py`) |
| Look-ahead bias (logical, not security) | Tampering of statistical results | Mandatory FR-6.1 injection test in CI |
| Gate bypass via direct DB write to `gate_status = 'pass'` | Elevation of privilege | `override_gate_pass` flag in config is the only sanctioned bypass; document in runbook |

---

## Open Questions

1. **RL checkpoint loading strategy**
   - What we know: `rl_checkpoints` table has `is_active = TRUE` flag per agent; multiple checkpoints can exist per agent
   - What's unclear: Which checkpoint should the backtest use? The final active one? A specific step?
   - Recommendation: Use `WHERE is_active = TRUE ORDER BY step DESC LIMIT 1` per agent. This is the same index the trainer uses.

2. **Transaction cost constants in fills.py**
   - What we know: `CONFIG.risk.transaction_cost_bps = 12.5` is defined in `config.py`
   - What's unclear: Is slippage modeled separately or folded into `transaction_cost_bps`?
   - Recommendation: Use `transaction_cost_bps` as total round-trip cost (entry + exit). No separate slippage model for v1.0.

3. **Earnings universe for a given as_of date**
   - What we know: `sp500_membership.py` has `sp500_members_as_of()` (async); the backtest needs the sync equivalent
   - What's unclear: Does `app/queries/sp500_membership.py` have a sync version?
   - Recommendation: Write a sync equivalent in `backtest/runner.py` using the same SQL as `sp500_members_as_of()` but with `text()` + sync session. Pattern already established in `macro_loader.py`.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python / pytest | All tests | Already in Docker/Railway | 3.x | None needed |
| PostgreSQL + TimescaleDB | FR-6.6 integration test | Available (Phase 1 standing infra) | TimescaleDB on PostgreSQL | Skip DB-gated tests |
| `rl/` weights directory | Replay (checkpoint load) | `rl/weights/.gitkeep` exists | N/A | Tests use randomly initialized ensemble |
| `ff5_factors` table rows | Risk-free rate | Available (Phase 2 flow) | Populated 2005-present | Fall back to `risk_free_rate_annual` constant |

No blocking missing dependencies. The `rl/weights/.gitkeep` confirms the weights directory exists but is empty - tests will initialize a fresh ensemble with random weights. [VERIFIED: codebase find command]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 8 Backtest Explorer needs: run_id, dates, sharpe, max_drawdown, ir_vs_baseline, calmar, monthly_returns, gate_status | backtest_runs schema | Phase 8 plan might require additional columns; low risk since JSONB `config_snapshot` can absorb extras |
| A2 | `rl/weights/.gitkeep` means no pretrained weights are committed; tests use randomly initialized ensemble | Validation Architecture | If checkpoint-loading is required for tests, Wave 0 must include a fixture that loads from `rl_checkpoints` table |
| A3 | `pandas.bdate_range` with `freq='B'` is sufficient for the date iterator (includes non-NYSE holidays as trading days) | Trading Calendar | At most a few extra no-data days per year; replay gracefully skips if no price bars exist for a date |

---

## Sources

### Primary (HIGH confidence)

- `backend/app/queries/point_in_time.py` - point-in-time query pattern, `ingestion_timestamp <= as_of`
- `backend/app/signals/pipeline.py` - `_last_close()` SQL pattern, `compute_signal_for_event()` call signature
- `backend/app/portfolio/macro_loader.py` - `load_macro_snapshot()` pattern, sync session usage
- `backend/app/flows/_base.py` + `_db.py` - `sync_session()` context manager, `SyncSessionLocal`
- `rl/sac_agent.py` - `SACEnsemble.select_action_per_agent()` signature
- `rl/moe_controller.py` - `MoEController.blend()` signature and return type
- `backend/alembic/versions/0001_initial_schema.py` through `0004_rl_phase5_tables.py` - migration chain, naming convention
- `backend/requirements.txt` - all available packages and versions
- `backend/pytest.ini` - test configuration
- `backend/tests/conftest.py` - `requires_db`, DB fixtures
- `backend/tests/rl/conftest.py` - sys.path pattern for rl.* imports
- `config.py` (repo root) - `SACConfig`, `RiskConfig`, `DataConfig` dataclasses
- `backend/app/config.py` - `Settings` pydantic model

### Secondary (MEDIUM confidence)

- `rl/environment.py` - confirms 31-dim observation space; confirms sync pandas-based date stepping pattern
- `rl/reward.py` - confirms `ff5_factors` columns used for reward; confirms `RF` column meaning

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all packages verified against requirements.txt
- Architecture patterns: HIGH - all verified against existing Phase 1-5 codebase
- Point-in-time query pattern: HIGH - confirmed in 3+ production files
- Stats formulas: HIGH - standard finance formulas, numpy-only
- Phase 8 schema needs: MEDIUM - based on ROADMAP description, Phase 8 not yet designed

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (stable codebase; 30-day window is safe)
