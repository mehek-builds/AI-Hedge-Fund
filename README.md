# PEAD RL Trader

An autonomous, end-to-end trading system that harvests **Post-Earnings-Announcement Drift (PEAD)** across the S&P 500, sizing every position with a **reinforcement-learning agent trained to maximise risk-adjusted (Fama-French 5-factor) alpha** rather than raw return.

This is not a backtest notebook. It is a full production stack: a point-in-time data layer, a factor-and-quality-adjusted signal engine, an RL sizing agent (PPO and SAC, with a mixture-of-experts controller, prioritized experience replay, and a transformer state encoder), a macro-regime risk gate, an Alpaca paper-trading execution path, a Celery + Prefect orchestration layer, and a live Next.js operator dashboard, all wired together over FastAPI, PostgreSQL/TimescaleDB, and Redis.

---

## The problem this solves

When a company reports earnings, the market does not fully price the surprise on day one. Prices keep drifting in the direction of the surprise for **weeks** afterward. This is **Post-Earnings-Announcement Drift**, one of the most durable and heavily documented anomalies in empirical finance (Ball & Brown 1968, Bernard & Thomas 1989, and roughly five decades of replication since). It exists because human investors underreact to new information: they anchor on stale expectations and update too slowly.

Knowing the anomaly exists is easy. **Trading it profitably and safely is hard**, for reasons that have nothing to do with the idea and everything to do with engineering:

1. **Measuring the surprise correctly.** A naive "beat vs. miss" flag is noise. The real signal is *how large the surprise is relative to what price was already implying*, normalised by the stock's own historical surprise volatility.
2. **Point-in-time data integrity.** Almost every public backtest of PEAD is silently contaminated by lookahead bias: restated earnings, survivorship in the universe, factor loadings computed with future data. If your data is not *as-of* correct to the day, your alpha is imaginary.
3. **Position sizing under uncertainty.** The edge is real but small and noisy. Sizing every trade the same is how you blow up. The hard question is *how much* to hold, given signal strength, how long you have held, and where you are in the macro cycle.
4. **Separating skill from beta.** A strategy that returns 12% in a year the market returned 11% has almost no alpha. Judging the system on raw P&L is self-deception; it has to be judged on **factor-adjusted** alpha (excess return after neutralising market, size, value, profitability, and investment exposure).
5. **Regime risk.** PEAD, like most cross-sectional anomalies, degrades or inverts in liquidity crises and carry unwinds. A system that does not *watch the macro* and cut exposure will give back a year of edge in one bad month.

**PEAD RL Trader is an attempt to solve all five as one integrated system** rather than a script that solves the first and ignores the rest.

## Why you should care (even if you do not trade)

If you are reading this to understand what I can build, here is the short version: this repository takes an academic finance anomaly and turns it into a **working, observable, autonomous software system**. It touches reinforcement learning, factor econometrics, real-time data engineering, async web services, job orchestration, and frontend dashboarding, and it holds them together with the kind of correctness discipline (point-in-time queries, `as-of` tests, factor-adjusted evaluation) that separates a real quant system from a curve-fit toy. The interesting part is not any single technology; it is that they are *composed* into something that runs on a schedule, makes decisions, executes them, and shows its work.

---

## System architecture

Data flows top to bottom; the RL reward signal flows bottom to top.

```
                       ┌─────────────────────────────────────────────┐
   Next.js dashboard   │  signals · positions · macro · RL · backtest │  live via SSE
   (React 19, Recharts)│  alerts · paper-trading · settings           │
                       └───────────────────▲─────────────────────────┘
                                           │  REST + Server-Sent Events
                       ┌───────────────────┴─────────────────────────┐
   FastAPI service     │  auth · market · signals · macro · orders    │
   (async SQLAlchemy)  │  positions · portfolio · rl · backtest · sse │
                       └───────────────────▲─────────────────────────┘
                                           │
   Orchestration       │  Celery workers + Prefect flows:             │
   (Redis broker)      │  daily_market · earnings_monitor ·           │
                       │  position_monitor · ingest · signal · rl     │
                       └───────────────────▲─────────────────────────┘
                                           │
   ┌───────────────┐  ┌───────────────┐  ┌─┴─────────────┐  ┌──────────────┐
   │ Signal engine │  │ Macro regime  │  │ RL sizing     │  │ Risk controls│
   │ signals/      │→ │ macro/regime  │→ │ rl/           │→ │ risk/controls│
   │ eps_gap,      │  │ 6-factor score│  │ PPO/SAC, MoE, │  │ drawdown,    │
   │ quality, roic │  │ + carry crash │  │ PER, xformer  │  │ exposure cap │
   └───────▲───────┘  └───────────────┘  └───────────────┘  └──────┬───────┘
           │                                                        │
   ┌───────┴──────────────────────────────────────────────────────▼───────┐
   │ Point-in-time data layer: earnings, prices, FF5 factors, macro (FRED) │
   │ data/  ·  backend/app/queries/point_in_time.py  ·  Alpaca execution   │
   └───────────────────────────────────────────────────────────────────────┘
                     Storage: PostgreSQL / TimescaleDB  ·  Redis
```

Each stage is independently testable and independently deployable. The research core (`signals/`, `rl/`, `macro/`, `risk/`, `backtest/`) runs standalone via a CLI; the service layer (`api/`, `backend/`), workers (`worker/`), and dashboard (`frontend/`, `web/`) layer a live operating surface on top of it.

---

## The full stack

| Layer | Technologies |
|-------|--------------|
| **RL / ML** | PyTorch, Stable-Baselines3 (PPO, SAC), Gymnasium custom environment, a mixture-of-experts controller, prioritized experience replay, a transformer state encoder |
| **Quant / econometrics** | NumPy, pandas, SciPy, statsmodels (rolling FF5 OLS betas), scikit-learn |
| **Market & macro data** | Alpaca (`alpaca-py`), yfinance, pandas-datareader, FRED (`fredapi`), Ken French factor library; a point-in-time `as-of` query layer |
| **Backend / API** | FastAPI, Uvicorn, async SQLAlchemy 2.0, asyncpg, Pydantic v2 / pydantic-settings, JWT auth (python-jose, passlib/bcrypt), httpx, Server-Sent Events |
| **Orchestration** | Celery (Redis broker, routed `signals` / `ml` queues), Prefect flows, task-level retries and late-ack |
| **Storage** | PostgreSQL / TimescaleDB (hypertables for price bars), Redis (broker, result backend, pub/sub for SSE), Alembic migrations |
| **Frontend** | Next.js 16, React 19, TypeScript, TanStack Query, Recharts, Tailwind CSS v4, NextAuth, lucide-react |
| **Infra / deploy** | Docker + docker-compose (db, redis, fastapi, celery, prefect), Fly.io (`pead-api`), Railway, Vercel (dashboard) |
| **Quality** | pytest / pytest-asyncio, a `test_as_of` point-in-time correctness suite, ruff, loguru structured logging |

---

## The alpha model (`signals/`)

The system does not trade "beats." It trades a **factor- and quality-adjusted, volatility-normalised earnings surprise.**

**Market-implied EPS gap** (the core signal, `signals/eps_gap.py`):

```
implied_EPS   = 5-day average price / sector-median forward P/E
std_surprise  = (actual_EPS - implied_EPS) / rolling 4-quarter std dev of surprises
```

This asks a sharper question than "did they beat?": *did they beat relative to what the tape was already pricing in, measured in units of this stock's own surprise volatility?*

**Signal strength** (the sizing input handed to the RL agent, `signals/generator.py`):

```
signal_strength = std_surprise × intangible_multiplier × roic_multiplier
```

- **`intangible_multiplier`** (`signals/intangible_filter.py`): 1.0x / 1.15x / 1.3x by tercile of `(R&D + SG&A) / revenue`. Intangible-heavy firms are systematically mispriced by accounting that expenses their real investment, so their drift is stronger.
- **`roic_multiplier`** (`signals/roic_filter.py`, `signals/quality.py`, `signals/hurdle_rates.py`): 1.2x when ROIC clears WACC by 200bps+, else 1.0x. Quality compounders drift more cleanly than low-return businesses.

## Macro regime engine (`macro/regime.py`)

Six FRED series are each scored `-1` when adverse, plus an independent carry-crash overlay:

```
T10Y2Y  < -0.25%     → -1     (yield-curve inversion)
Core PCE > 3.5%      → -1     (inflation)
Real GDP QoQ < 1%    → -1     (growth)
HY spread > 500bps   → -1     (credit stress)
VIX     > 30         → -1     (volatility)
Sahm Rule ≥ 0.5      → -1     (recession trigger)
Carry crash          → -1     (independent overlay)
```

The composite score maps to a portfolio-wide **exposure multiplier**, so risk is dialled down automatically as the regime deteriorates:

```
score  0 → 1.00x     -2 → 0.65x     ≤ -4 → HALT
      -1 → 0.85x     -3 → 0.35x
```

The macro module is **observational only**: it never forecasts, it only measures the present regime and gates sizing. That boundary is deliberate and part of the design.

## The reinforcement-learning agent (`rl/`)

Position sizing is not a formula here; it is a learned policy.

- **Environment** (`rl/environment.py`): a custom Gymnasium environment. The **observation** is an 18-dimensional vector: signal strength, macro score, holding-day fraction, unrealised return, an 11-way GICS sector one-hot, and a cyclical/secular flag. The **action** is continuous in `[-1, 1]` (position size; negative permits shorting when enabled).
- **Reward** (`rl/reward.py`): the **FF5-adjusted alpha realised at exit**, computed with rolling 60-month OLS factor betas that are recalibrated quarterly. The agent is rewarded for *skill*, not for accidentally holding beta.
- **Algorithms**: PPO by default (`rl/agent.py`), SAC available (`rl/sac_agent.py`).
- **Advanced components**: a **mixture-of-experts controller** (`rl/moe_controller.py`) to route between sub-policies, **prioritized experience replay** (`rl/per_buffer.py`) so rare high-surprise episodes are learned from efficiently, and a **transformer state encoder** (`rl/transformer_encoder.py`) for sequence-aware representation of the holding trajectory.
- **Sector-aware initialisation** (the L4 prior): cyclical sectors start at a 45-day hold assumption, secular sectors at 90 days, and the agent adapts from there.

## Risk controls (`risk/controls.py`)

Independent of the RL policy, hard portfolio constraints enforce maximum drawdown and exposure caps, so a mis-trained agent cannot exceed the mandate. Risk is a separate layer from return by design.

## Backtesting and point-in-time correctness (`backtest/`, `backend/app/queries/point_in_time.py`)

The backtest engine (`backtest/engine.py`) replays the 2010-2023 universe. Critically, the data access is **as-of correct**: the `point_in_time` query layer and its dedicated `test_as_of` suite exist specifically to guarantee that no signal, factor loading, or fundamental is ever computed with data that would not have been available on the decision date. This is the single most common way PEAD backtests lie, and it is tested here as a first-class invariant.

## The operator platform (`api/`, `backend/`, `worker/`)

Around the research core sits a live operating system:

- A **FastAPI** service exposes the full surface: `auth`, `market`, `signals`, `macro`, `orders`, `positions`, `portfolio`, `rl`, `backtest`, `alerts`, `architecture`, and `dashboard`, plus a **Server-Sent Events** channel (`sse`) that streams state to the dashboard in real time.
- **Alpaca** integration (`api/services/alpaca.py`) executes paper trades.
- A **Celery + Prefect** worker layer runs the recurring flows: `daily_market`, `earnings_monitor`, `position_monitor`, and the `ingest`, `signal`, `rl`, `alerts`, and `execution` tasks, on routed Redis queues.
- **PostgreSQL / TimescaleDB** stores price bars, earnings events, macro indicators, portfolio positions, RL transitions, and signals, managed with **Alembic** migrations.

## The dashboard (`frontend/`, `web/`)

A **Next.js 16 / React 19** operator console renders the system's live state: current signals, open positions, macro regime, RL policy behaviour, backtest results, and alerts, with **Recharts** equity curves, **TanStack Query** data fetching, **NextAuth** login, and **Tailwind v4** styling. It consumes the API over REST and subscribes to the SSE stream for live updates.

---

## Running it

**Research core (no infrastructure required):**

```bash
pip install -r requirements.txt

# FRED key is optional; synthetic macro data is used if absent
echo "FRED_API_KEY=your_key_here" > .env

python main.py backtest                      # backtest the 2010-2023 universe
python main.py regime                        # print the current macro regime
python main.py signal --tickers AAPL MSFT NVDA
python main.py train --algo PPO --timesteps 500000
```

**Full stack (API + worker + Prefect + Postgres + Redis):**

```bash
docker-compose up --build
# FastAPI on :8000, TimescaleDB on :5432, Redis on :6379, Prefect UI included
```

The API deploys to **Fly.io** (`fly.toml`, app `pead-api`) and **Railway** (`railway.toml`); the dashboard deploys to **Vercel** (`frontend/vercel.json`).

## Testing

```bash
pytest                       # research core: test_signal, test_reward, test_macro, test_risk
cd backend && pytest         # service layer: test_as_of (point-in-time), test_health, test_schema
```

---

## PRD success targets

| Metric | Target | Notes |
|--------|--------|-------|
| FF5-adjusted alpha | > 0.40% / month | Benchmark: USIF active 0.66%/mo |
| Sharpe (annualised) | > 1.0 | S&P 500 long-run ≈ 0.5 |
| Max drawdown | < 15% | Hard constraint |
| RL vs. naive baseline | Positive improvement | Measured as information ratio |

## Production data requirements

The system runs today on free/synthetic fallbacks; these are the swap-ins for live capital:

| Data | Production source | Module |
|------|-------------------|--------|
| Earnings (actual EPS, non-recurring flags) | Compustat / FactSet | `data/earnings_data.py`, `data/real_earnings_client.py` |
| Daily adjusted prices | CRSP | `data/price_data.py` |
| FF5 factor returns | Ken French data library | `data/factor_data.py` |
| Macro series | FRED API | `data/fred_client.py` |
| R&D + SG&A, ROIC | Compustat quarterly | `data/earnings_data.py` |

## Scope (v1.0)

**In:** S&P 500 (large-cap, > $2B), US equities, daily rebalancing, paper execution.
**Out (deliberately):** international equities, options, intraday execution, macro *forecasting* (the regime module is observational only), and the small-cap universe.
