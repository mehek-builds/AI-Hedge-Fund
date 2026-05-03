# Domain Pitfalls: PEAD Trading System

**Domain:** Autonomous paper trading platform — PEAD signal + SAC ensemble RL + completion portfolio
**Researched:** 2026-05-02
**Confidence note:** WebSearch and WebFetch were unavailable during this session. All findings are from training data (cutoff August 2025). Items marked LOW confidence require live verification before build.

---

## 1. Data Quality Pitfalls

### CRITICAL: Point-in-Time Data Contamination (Look-Ahead Bias)

**What goes wrong:** The backtest uses financial ratios or macro data that were not available on the simulated trade date. For example, FRED revises GDP and CPI data retroactively — the "2022-Q1 GDP" value visible in your database today is not what was published in April 2022. FMP earnings actuals also get restated. Any feature built from a non-point-in-time source will cause the backtest Sharpe to be systematically overstated and the live system to underperform.

**Why it happens:** APIs like FRED and FMP return current values by default, not as-of-date values. Ken French factor data is similarly posted with a delay but treated as instantly available. yfinance historical data is post-split, post-adjustment — the adjusted close for 2019 was not the number visible in 2019.

**Consequences:** You hit Sharpe > 1.0 in backtest, deploy to paper trading, and the live system immediately reverts to near-zero or negative Sharpe. The RL agents were trained on a fantasy dataset. You cannot diagnose this from live PnL alone without a clean point-in-time reconstruction.

**Prevention:**
- FRED: Use the vintage series API (`/vintage_dates`, `/observations?vintage_dates=`) or the ALFRED (Archival FRED) endpoint for every macro feature. Never use the default observations endpoint for backtest features.
- FMP: Store earnings actuals at the timestamp they were first reported (the earnings release datetime, not the filing date). Build a `data_vintage` column into every feature table.
- Ken French: Factors are posted monthly with ~2-4 week delay. Assume factors for month M are unavailable until M+35 days in backtest.
- Alpaca adjusted prices: Use the unadjusted close for live trading signal computation (so it matches what you'll see live). Use adjusted close only for return attribution. Never mix the two in the same model.

**Detection:** Run a "future information test": for each feature, check whether it has any predictive power when you deliberately lag it by 1 day beyond its supposed availability. If lag-1 significantly degrades performance versus lag-0, you have look-ahead contamination.

**Confidence:** HIGH — this is the most documented failure mode in quantitative backtesting.

---

### CRITICAL: Survivorship Bias in S&P 500 Universe

**What goes wrong:** The system pulls current S&P 500 constituents and runs the backtest on that list back to 2018. This excludes every company that was in the S&P 500 from 2018–2023 but was later removed (delisted, bankrupt, acquired, or demoted). The backtest universe is retroactively filtered to survivors, which inflates returns.

**Why it happens:** Alpaca's screener and most stock APIs return current constituents. There is no free "as-of-date S&P 500 constituent" list from the major data vendors without a Bloomberg or Compustat subscription.

**Consequences:** Backtest overstates Sharpe by an estimated 0.2–0.5 for a universe-based momentum strategy. PEAD specifically over-inflates because removed companies often had negative earnings surprises before removal. Your validation gate (Sharpe > 1.0) may be clearing on a biased benchmark.

**Prevention:**
- Use the S&P 500 constituent history from Wikipedia's monthly snapshots (public), or the Kaggle S&P 500 constituent history dataset. Both are free and go back to ~2000.
- Build a `universe_membership` table with `(ticker, entry_date, exit_date)`. Only include a stock in the backtest universe for dates within its membership window.
- If WRDS/Compustat access is available (mentioned in PROJECT.md), the `crsp.msp500list` table has exact constituent dates.

**Detection:** Compare the list of stocks in your backtest universe for 2018 vs. the actual 2018 S&P 500 constituent list. If there are >20 discrepancies, survivorship bias is material.

**Confidence:** HIGH.

---

### Earnings Restatements and FMP Reliability

**What goes wrong:** FMP's earnings actuals are occasionally wrong at initial ingestion — they pull from SEC EDGAR but sometimes pick up preliminary or amended figures. A company may report EPS of $1.20, which FMP initially records correctly, but then FMP's database gets updated when a restatement is filed, retroactively changing the historical record. Your Celery pipeline ingests the restated number and now has a historical EPS surprise that never existed.

**Specific FMP failure modes (MEDIUM confidence — from community reports, not verified with FMP directly):**
- Small-cap and micro-cap earnings (below S&P 500) are less reliable — not relevant here since the universe is S&P 500, but boundary cases at index entry/exit are at risk.
- Earnings dates are sometimes wrong by 1 business day (AMC vs. BMO misclassification), which creates a ~1-day signal timing error.
- FMP rate limits on the `$25/mo` Starter plan: 250 API calls/day on some endpoints, 750 on others. A full S&P 500 earnings refresh (~500 companies) will hit limits if run naively in one Prefect flow.

**Prevention:**
- Store raw API responses with `ingestion_timestamp`. Never overwrite — append with a new record if data changes. This lets you detect restatements.
- FMP earnings calendar endpoint: pull at T-7 days for upcoming earnings, then again at T+1 hour after market close to get actuals. Rate-limit your Prefect flow to 50 calls/minute.
- Cross-validate EPS actuals against yfinance for a random 10% sample weekly.

**Confidence:** MEDIUM (FMP-specific behavior based on community reports through early 2025).

---

### FRED Data Revisions

**What goes wrong:** FRED macroeconomic series are revised. The ISM Manufacturing PMI, unemployment rate, and CPI all get revised in subsequent releases. If your macro composite score feature uses the current (revised) value rather than the first-published value, you have a subtle look-ahead bias in the macro regime signal.

**Which series matter most for this system:**
- ISM PMI: Revised but minor revisions, usually < 0.5 points.
- Nonfarm Payrolls: Revised significantly (often +/- 50-100k). The first print vs. final can flip regime classification.
- CPI: Not revised after initial release — safe to use as-is for regime signals.
- 10Y Treasury yield (DGS10): Not revised — safe.
- Credit spreads (BAMLH0A0HYM2): Not revised — safe.

**Prevention:** Use ALFRED vintage dates for payrolls and ISM in backtest. For live system, these are first-print values anyway so no action needed.

**Confidence:** HIGH.

---

## 2. RL Training Pitfalls

### CRITICAL: Overfitting in Financial RL (Non-Stationarity + Small Sample)

**What goes wrong:** The SAC ensemble trains on 2018–2023 data (roughly 1,250 trading days × ~500 stocks). This sounds large but for an RL agent learning regime-conditional position sizing, the number of distinct earnings events with full outcome windows is small: ~500 companies × ~4 quarters × 6 years = ~12,000 events, minus data gaps. The agents will overfit to the specific macro regimes and market dynamics of 2018–2023, which included zero-rate policy, COVID shock, and rapid rate hike. None of these regimes may repeat.

**Why it happens:** Financial time series are non-stationary. The reward distribution the agent optimizes on during training does not match live deployment. SAC with PER specifically will over-prioritize the high-TD-error transitions, which in finance are often the market dislocations — exactly the regime least likely to repeat.

**Consequences:** Agents achieve high training-set IR but degrade rapidly in paper trading. The Mixture-of-Experts meta-controller may confidently assign a regime that existed in 2020 but isn't present in 2026.

**Prevention:**
- Walk-forward validation is mandatory: train on 2018–2021, validate on 2022, test on 2023. Never use 2023 for any hyperparameter tuning.
- Implement explicit out-of-distribution detection in the MoE regime conditioner. If the current macro state is outside the convex hull of training regimes, flag and reduce position sizing.
- Use low-capacity models deliberately. A Transformer state encoder with 2 layers and 64-dim hidden is better than 4 layers and 256-dim for this dataset size. Pre-train frozen (already planned) and resist the urge to unfreeze.
- Monitor the coefficient of variation across the 5 ensemble agents' action outputs. High agreement → ensemble is collapsing (see Ensemble Collapse below).

**Confidence:** HIGH — well-documented in financial RL literature.

---

### CRITICAL: Ensemble Collapse (Agents Converging to Same Policy)

**What goes wrong:** All 5 SAC agents converge to nearly identical policies, eliminating the diversity benefit of the ensemble. The ensemble IR is then no better than a single agent, but with 5x the compute and maintenance overhead. The system ships with an apparent ensemble but is effectively a single-agent system.

**Why it happens:** Shared replay buffer (PER is shared in the standard multi-agent setup), shared network initialization seeds, and similar hyperparameters cause the agents to learn the same TD updates. The financial reward signal has low variance relative to the noise, so all agents converge to a similar safe policy (small positions, high cash allocation).

**Consequences:** The MoE meta-controller has nothing to aggregate. Position sizing uncertainty estimates collapse toward zero. The ensemble fails its own justification.

**Prevention:**
- Different random seeds AND different hyperparameter perturbations per agent (recommended range: ±30% on learning rate, entropy coefficient, and discount factor across the 5 agents).
- Per-agent experience buffers, not a single shared PER buffer. Agents should receive different mini-batches even on the same underlying events.
- Add a diversity regularization term to the policy loss: penalize cosine similarity between agent action distributions above a threshold.
- Track per-agent IR separately in the RL Console dashboard. Alert if any two agents have IR correlation > 0.9 over a 30-day rolling window.

**Confidence:** HIGH — documented failure mode in multi-agent RL.

---

### SAC Instability with Financial Reward Signal

**What goes wrong:** The standard SAC entropy coefficient (alpha) tuning assumes dense, stationary rewards. Financial returns are sparse (positions held for 2–20 days), skewed (rare large gains/losses), and non-stationary. Automatic alpha tuning in SAC can cause the agent to either explore too aggressively (high alpha → nearly random trading, transaction costs destroy PnL) or collapse entropy entirely (low alpha → deterministic policy that gets stuck in a few learned patterns).

**Specific failure modes:**
- Alpha decays to near-zero in the first 500 training steps if early earnings events happen to have strongly positive outcomes — the agent learns a confident policy too early on a small sample.
- The discount factor (gamma) has outsized sensitivity. Gamma = 0.99 over a 2-day holding period at minute frequency collapses value estimates. Use gamma appropriate to the holding period: for a 2–10 day hold at daily steps, gamma = 0.95–0.97 is appropriate.
- PER beta annealing schedule: if beta reaches 1.0 too quickly (< 10k steps), the high-weight transitions from early anomalous events dominate updates indefinitely.

**Prevention:**
- Set a floor on alpha: `alpha_min = 0.01`. Do not allow automatic tuning below this.
- Use daily time steps in the RL environment, not intraday. This makes the reward signal denser and the discount factor intuitive.
- PER beta: start at 0.4, anneal to 1.0 over the full training run (not first 10k steps). Set `beta_increment = (1.0 - 0.4) / total_training_steps`.
- Clip rewards at ±3 sigma of historical return distribution before feeding to agents. Extreme earnings gap events should not dominate replay.

**Confidence:** HIGH.

---

### Reward Hacking via Transaction Cost Blindness

**What goes wrong:** The agent discovers that it can inflate the reward signal by holding positions without trading (capturing the PEAD drift passively) while the signal engine would recommend closing. If transaction costs are underweighted in the reward function, the agent over-trades. If overweighted, it under-trades. The pathological case is an agent that learns to never trade — technically earns the drift but never actually executes the PEAD entry.

**Prevention:**
- Use Alpaca paper trading's actual fill prices (including spread) as the transaction cost in the RL environment, not a fixed basis-point assumption.
- Add a position inertia penalty: if the signal scores a position as "close" but the agent holds for more than N days, reduce the reward by the expected opportunity cost.
- Monitor average holding period per agent separately. If any agent has average hold > 3x the expected PEAD drift window, it is likely exploiting the reward function.

**Confidence:** MEDIUM.

---

## 3. Alpaca Paper Trading Pitfalls

### Paper vs. Live Behavioral Differences

**What goes wrong:** Alpaca paper trading fills orders at the NBBO midpoint or last trade price, not at the actual market impact price. For S&P 500 stocks with normal liquidity this is fine, but the paper system will show better fills than live trading on:
- Earnings day gap opens (large bid/ask spreads in first 5 minutes)
- Any position size that would be > 0.5% of typical daily volume
- Extended hours trading if enabled

**Consequence:** Your paper Sharpe will be structurally higher than live Sharpe by a fill-quality margin. Budget approximately 5–15 bps per trade as a fill-quality haircut when projecting live performance.

**Prevention:**
- Implement a "realistic fill" adjustment layer that adds a configurable fill haircut (default 10 bps) to all paper fills before logging to the backtest/performance tables.
- Never use limit orders in paper trading to benchmark execution — they will fill at the limit price every time, which is unrealistic.

**Confidence:** MEDIUM (Alpaca behavior as of early 2025; verify current paper trading fill simulation in Alpaca docs).

---

### Bracket Order Edge Cases

**What goes wrong:** Alpaca bracket orders (entry + take-profit + stop-loss as a single order) have the following documented edge cases:
- If the entry leg partially fills, the take-profit and stop-loss legs are created for the full original quantity, not the filled quantity. This creates an over-hedged position.
- Bracket orders cannot be modified after submission — you must cancel the entire order and resubmit. If the entry has already partially filled, the cancelled legs leave an unhedged position.
- Market orders as the entry leg of a bracket can result in the take-profit/stop-loss legs being created before the fill confirmation arrives, causing brief phantom positions.

**Prevention:**
- Use limit orders as bracket entry legs, not market orders. Accept the slippage risk of non-fills over the position sync risk.
- On reconnect/restart: always reconcile open orders before processing new signals. The position sync routine must query both `/positions` and `/orders?status=open` and resolve any mismatches before submitting new brackets.
- Build a bracket orphan detector: any open take-profit or stop-loss order that has no corresponding position should trigger an immediate cancel and alert.

**Confidence:** MEDIUM (Alpaca bracket behavior documented in their API reference through 2024; verify against current API version).

---

### Alpaca Rate Limits

**What goes wrong:** The Alpaca paper trading API has rate limits that are lower than the live API on some endpoints. The specific limits (as of 2024) are approximately:
- Trading API: 200 requests/minute
- Market data API (historical): 200 requests/minute for the free tier; higher for paid data subscriptions
- Streaming: up to 30 concurrent symbol subscriptions on free tier

**Consequence:** A Celery task that refreshes all 500 S&P 500 positions or prices in a tight loop will hit rate limits within seconds. The task fails silently if the HTTP 429 is not caught, leaving stale data.

**Prevention:**
- All Alpaca API calls must implement exponential backoff with jitter on HTTP 429.
- Batch position queries: use `/positions` (returns all positions in one call) rather than `/positions/{symbol}` per position.
- Market data bulk quote endpoint reduces per-symbol calls dramatically — use `/v2/stocks/quotes/latest?symbols=AAPL,MSFT,...` with up to 100 symbols per request.

**Confidence:** MEDIUM (rate limit values from 2024 documentation; verify exact limits for current paper account tier).

---

### Position Sync on Reconnect

**What goes wrong:** When the FastAPI service or Celery workers restart, the in-memory position state diverges from Alpaca's actual positions. If the system crashed while an order was in-flight, the restart may attempt to re-enter a position that was already filled, doubling the exposure.

**Prevention:**
- The PositionManager service must treat Alpaca as the source of truth on startup. On every service restart: (1) query `/positions`, (2) query `/orders?status=open`, (3) reconcile against the PostgreSQL positions table, (4) resolve discrepancies before accepting new signals.
- Add a `position_reconciled_at` timestamp to the positions table. Refuse to process new signals until this is populated post-restart.

**Confidence:** HIGH.

---

## 4. Infrastructure Pitfalls

### CRITICAL: Railway Auto-Deploy Killing RL Training Jobs

**What goes wrong:** Railway's default behavior on a new GitHub push is to rebuild and redeploy all services. A SAC training run takes hours to days. An auto-deploy triggered by a frontend or API commit will kill the training job mid-run, losing all progress if checkpointing is not implemented.

**Prevention:**
- Separate the RL trainer into a Railway service that is NOT connected to auto-deploy. Use Railway's "manual deploy" option or a separate branch/environment.
- Implement checkpoint saves every N training steps (recommended: every 1,000 steps, approximately every 5–10 minutes). Save to a Railway volume or external object store (Railway persistent volumes or an S3-compatible store).
- Add a pre-deploy health check that refuses deployment if a training job is active (poll a Redis key `rl_training_active`).

**Confidence:** HIGH (Railway auto-deploy behavior is well-documented).

---

### Railway Memory Limits and TimescaleDB

**What goes wrong:** Railway's free tier provides 512MB RAM per service. TimescaleDB with a 5-year price history for 500 stocks plus continuous aggregates will require significantly more. The database service will be OOM-killed regularly, causing data corruption if a write is in progress.

**Specific memory consumption estimates:**
- PostgreSQL with TimescaleDB baseline: ~150–200MB for shared_buffers at default settings.
- 500 stocks × 5 years × daily OHLCV + earnings events: approximately 2–5GB of data, but this lives on disk. The in-memory pressure comes from continuous aggregate computation and query working memory.
- A complex analytics query (full backtest replay across all 500 stocks) can consume 500MB–1GB of working memory per query.

**Prevention:**
- Railway Hobby plan ($5/mo) provides 8GB RAM. This is necessary for TimescaleDB. Do not use free tier for the database service.
- Set `shared_buffers = 256MB` and `work_mem = 16MB` in TimescaleDB config. Do not use defaults (which auto-scale to 25% of system RAM and will OOM on Railway's constrained environment).
- Run expensive analytics queries (backtest replays) during off-hours only. Do not allow concurrent analytics + live signal computation on the same PostgreSQL instance.
- Store the TimescaleDB data on a Railway persistent volume. The default ephemeral filesystem will lose all data on service restart.

**Confidence:** MEDIUM (Railway pricing/tier limits verified as of early 2025; confirm current Hobby plan specs).

---

### Redis Memory for PER Replay Buffer

**What goes wrong:** A PER replay buffer with 100,000 transitions at a state dimension of, say, 128 features × float32 = 512 bytes per state, plus action (float32) + reward (float32) + next_state (512 bytes) + priority (float32) = approximately 1,030 bytes per transition. At 100k transitions: ~103MB. This is manageable.

However: if the state dimension includes a Transformer-encoded embedding (768 or 1024 dim), the per-transition size grows to ~6–8KB. At 100k transitions: ~600–800MB. Redis on Railway's free tier is limited to 30MB. Railway Hobby gives more but Redis memory is shared with other uses.

**Prevention:**
- Store PER buffers in PostgreSQL (with TimescaleDB) or on-disk (pickle/numpy) rather than Redis. Redis should only be used for Celery task queuing and ephemeral caches, not for the replay buffer.
- Cap the Transformer embedding before storing to the replay buffer. Project to 64-dim before storage. Full 768-dim embeddings should only live in GPU memory during training.
- Use Redis `maxmemory-policy allkeys-lru` so that under memory pressure, Redis evicts Celery task results rather than active queue entries.

**Confidence:** HIGH (Redis memory behavior; Railway tier limits MEDIUM).

---

### Celery Task Leaks

**What goes wrong:** Long-running Celery tasks (RL training coordination, bulk data ingestion) that crash without cleanup leave orphaned tasks in Redis. On restart, Celery may try to re-execute these tasks, causing duplicate data ingestion or conflicting RL training runs.

**Specific failure modes:**
- A Prefect flow triggers a Celery task to fetch earnings data. The Celery worker crashes. The task stays in the `PENDING` state in Redis indefinitely. On worker restart, the task is not automatically re-queued (Celery's visibility timeout behavior).
- Two concurrent RL training tasks get triggered (once from a manual trigger, once from a Prefect schedule). They both write to the same model checkpoint file, corrupting it.

**Prevention:**
- Set `CELERY_TASK_ACKS_LATE = True` so tasks are only acknowledged after completion, not on receipt. Combined with `worker_prefetch_multiplier = 1`, this prevents task accumulation on crashed workers.
- Use Celery task IDs as idempotency keys. Before starting any data ingestion task, check if a task with the same ID (derived from the symbol + date) is already running or completed.
- Add a Redis lock with TTL for RL training tasks: only one training task may hold the lock at a time.

**Confidence:** HIGH.

---

### Docker Compose Service Startup Order

**What goes wrong:** FastAPI starts before TimescaleDB is ready to accept connections. The FastAPI health check passes (the Python process is running), but all database operations fail. If the health check only checks process liveness (not database connectivity), Celery workers register as healthy but all tasks that touch the database fail immediately.

**Prevention:**
- Use `depends_on` with `condition: service_healthy` for all services that depend on PostgreSQL, not just `condition: service_started`.
- Add a proper health check for TimescaleDB: `pg_isready -U postgres -d pead_trading` with a 30-second start period and 5-second interval.
- FastAPI startup: wrap all database initialization in a retry loop with exponential backoff (up to 60 seconds). Do not fail hard on first connection error.

**Confidence:** HIGH.

---

### Prefect 2.0 Scheduler Drift

**What goes wrong:** Prefect 2.0 schedules are defined relative to deployment creation time, not wall clock. After a Railway redeploy, Prefect deployments are recreated with a new creation timestamp, potentially causing double-runs (if the new schedule fires before the old deployment times out) or missed runs (if the gap between deploys spans a scheduled interval).

**Also:** Prefect 2.0's default server (Prefect Cloud free tier or self-hosted on Railway) has a polling interval for the scheduler. If the self-hosted server is on Railway with limited resources, the scheduler can lag by 5–15 minutes under load. For an earnings calendar that fires 30 minutes after market close, a 15-minute scheduler lag could compress the processing window significantly.

**Prevention:**
- Use cron-based schedules (not interval-based) for all time-sensitive flows. `0 16 * * 1-5` (4pm ET weekdays) is deterministic regardless of deployment creation time.
- Self-host Prefect server as a dedicated Railway service. Do not use the Prefect Cloud free tier (execution limits and latency). Alternatively, trigger Prefect flows directly via FastAPI endpoint rather than relying on the scheduler for critical paths.
- Add a "missed run" detector: on each flow run, check if the previous run completed within the expected window. If not, send an alert and run immediately.

**Confidence:** MEDIUM (Prefect 2.0 scheduler behavior as of 2024; scheduler drift is a known community issue but may have been addressed in recent releases).

---

## 5. Signal Engine Pitfalls

### CRITICAL: PEAD Decay Post-2020

**What goes wrong:** Academic evidence (multiple papers 2020–2024) shows PEAD has significantly attenuated for large-cap liquid stocks since roughly 2015, with further attenuation post-2020. The mechanism: HFT and stat-arb firms have largely arbitraged the 0–3 day component of PEAD. The remaining edge (if any) is concentrated in:
- Day 2–10 post-earnings (not day 0–1)
- Small and mid-cap stocks (not S&P 500)
- Earnings with ambiguous market reaction (not clean beats/misses)
- Times of high cross-sectional dispersion (not trending markets)

**Consequence for this system:** The S&P 500 universe is exactly the set of stocks where PEAD is most arbitraged. A backtest on 2018–2023 may show residual Sharpe > 1.0 largely from the COVID volatility regime (2020), which inflated all momentum signals. Removing 2020 from the backtest is a useful stress test.

**What still works (MEDIUM confidence):**
- **Earnings quality decomposition** — this system's differentiator (revenue vs. margin vs. share count vs. guidance) may capture a quality-of-earnings signal that persists post-HFT, since it requires semantic interpretation of filings, not just price reaction.
- **Regime conditioning** — PEAD works better in specific macro environments. The MoE conditioner adds genuine value here.
- **Post-event 5–20 day window** — less competed than 0–2 days.

**Prevention:**
- Stress-test backtest with 2020 excluded. If Sharpe drops below 0.6, the PEAD signal is predominantly COVID-regime alpha, not structural.
- Decompose backtest returns by holding period (0–2 days, 3–10 days, 11–20 days). If all alpha is in days 0–2, HFT has arbitraged the remaining signal and live performance will be materially worse.
- Consider widening entry window from T+0 to T+2 (enter 2 days post-earnings, not on earnings day open) to avoid the HFT-dominated initial reaction period.

**Confidence:** MEDIUM-HIGH (PEAD attenuation is well-documented; exact magnitude for this specific signal design is uncertain).

---

### Stale Sector P/E Medians

**What goes wrong:** The market-implied EPS signal uses sector median forward P/E as a divisor. If this median is computed monthly (or less frequently), it will be stale during periods of rapid sector rotation. In Q4 2022, technology sector forward P/E compressed from ~35x to ~20x in two months. A stale P/E median would significantly mis-calibrate EPS surprise signals for the entire tech sector during this period.

**Prevention:**
- Update sector P/E medians weekly at minimum. Daily is better.
- Use the ETF P/E from yfinance (`XLK.PE`, `XLV.PE`, etc.) as a real-time check on the FMP-derived sector P/E. If they diverge by > 15%, flag and use the ETF value.
- Store sector P/E history. Allow the backtest engine to use the historical median value, not the current value, for each simulation date.

**Confidence:** HIGH.

---

### Earnings Calendar Gaps (FMP Small-Cap Coverage)

**What goes wrong:** FMP's earnings calendar is excellent for S&P 500 but has gaps for newly added constituents, foreign private issuers listed on US exchanges (some S&P 500 components), and companies that file on non-standard schedules. If a company's earnings event is missing from the calendar, the Prefect flow will never trigger signal computation for it. This creates a systematic blind spot — the strategy misses the earnings events it cannot see.

**Prevention:**
- Cross-validate FMP earnings calendar against yfinance's earnings calendar API (free, less accurate but good for gap detection) weekly.
- Build a "missing earnings" detector: for each S&P 500 constituent, if no earnings event has been logged in the last 5 months, trigger an alert.
- For any company where FMP has no upcoming earnings date within 90 days of the typical seasonal cycle, manually verify via SEC EDGAR filing calendar.

**Confidence:** MEDIUM.

---

### Momentum Crashes

**What goes wrong:** Momentum strategies (of which PEAD is a form) experience severe drawdowns during momentum crashes — periods when recent losers sharply outperform recent winners. Historical crash events: September 2009, August 2015, March 2020, November 2020 (vaccine announcement). These events are characterized by: rapid VIX spike, short-covering in beaten-down stocks, and rotation from high-momentum to low-momentum names.

**Consequence:** A PEAD strategy with no crash protection can experience drawdowns of 20–40% in a single month during a momentum crash, even with perfect signal quality.

**Prevention:**
- VIX gate: if VIX > 30 AND VIX has increased > 50% in 5 days, reduce all position sizes by 50%. If VIX > 40, go to cash on all PEAD positions.
- Monitor the book's beta to momentum factor (UMD). If the portfolio has UMD beta > 0.5, the completion portfolio needs to hedge this exposure.
- The macro composite score should have explicit momentum-crash regime detection as one of its dimensions.

**Confidence:** HIGH.

---

## 6. Deployment Pitfalls

### Secrets Management in Railway

**What goes wrong:** Railway environment variables (where Alpaca keys will live) are visible to all Railway team members by default. More critically: if Railway environment variables are pulled into the Docker build process (via `ARG` or `--build-arg`), they become embedded in the Docker image layer history and are visible to anyone with image pull access.

**Prevention:**
- Use Railway's "shared variable" feature, not plain environment variables, for secrets.
- Never pass secrets as Docker build arguments. Pass them at container runtime via environment variable injection.
- Rotate paper trading API keys every 90 days. Paper trading keys have no financial risk but rotating establishes good hygiene before v2.0 live.
- Add `alpaca_paper_key` and `alpaca_paper_secret` to `.gitignore` and the Railway environment directly. Verify they are not in any committed `.env` file.

**Confidence:** HIGH.

---

### TimescaleDB Persistent Storage on Railway

**What goes wrong:** Railway services have ephemeral filesystem by default. If the TimescaleDB service is restarted (crash, deploy, manual restart), all data is lost without a persistent volume. This is the single most catastrophic infrastructure failure mode: a 5-year price history and earnings database evaporating on a routine restart.

**Prevention:**
- Attach a Railway persistent volume to `/var/lib/postgresql/data` before any data is ingested. This is a Railway-specific configuration step that must happen before the database is first initialized.
- Schedule a daily `pg_dump` to an external store (S3, Cloudflare R2, or even a scheduled GitHub Action writing to a private repository) as a secondary backup.
- Test the restore process before going live. A backup that has never been restored is not a backup.

**Confidence:** HIGH.

---

## 7. Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Database setup (Phase 1) | Ephemeral volume — all data lost on restart | Attach persistent volume FIRST, before any schema creation |
| Data pipelines (Phase 2) | FRED/FMP using current values in backtest features | Build vintage/point-in-time tables before building any features |
| Signal engine (Phase 3) | S&P 500 survivorship bias in universe | Load constituent history table before running any backtest |
| RL training (Phase 4) | Ensemble collapse, all 5 agents same policy | Assign per-agent seeds and perturbed hyperparameters at initialization |
| RL training (Phase 4) | Replay buffer in Redis, OOM on Railway | Move replay buffer to PostgreSQL or on-disk, not Redis |
| Backtest validation (Phase 5) | Sharpe > 1.0 clearing due to 2020 COVID spike | Mandatory backtest run excluding 2020; require Sharpe > 0.8 on ex-2020 sample |
| Paper trading go-live (Phase 6) | Auto-deploy killing running RL jobs | Separate RL trainer service, manual deploy only |
| Paper trading go-live (Phase 6) | Bracket order partial fill → over-hedged position | Implement bracket orphan detector before first live order |
| Monitoring (Phase 7) | Ensemble collapse not detected | Track per-agent IR correlation, alert if > 0.9 on 30-day rolling |
| Production (Phase 8) | Fill quality overstates paper Sharpe vs. live | Apply 10 bps fill-quality haircut in all paper performance metrics |

---

## Sources and Confidence Summary

| Area | Confidence | Basis |
|------|------------|-------|
| Look-ahead bias / point-in-time | HIGH | Extensively documented in quant finance; ALFRED API behavior well-known |
| Survivorship bias | HIGH | Classic backtesting literature; S&P constituent history problem well-known |
| PEAD decay post-2020 | MEDIUM-HIGH | Multiple academic papers through ~2024 in training data; exact magnitude uncertain |
| SAC ensemble collapse | HIGH | Multi-agent RL literature; financial RL papers through 2024 |
| SAC hyperparameter sensitivity | HIGH | SAC paper (Haarnoja et al.) + financial RL adaptation literature |
| Alpaca paper vs. live differences | MEDIUM | Alpaca documentation through early 2025; verify current fill simulation behavior |
| Alpaca bracket order edge cases | MEDIUM | Alpaca community reports and API docs through 2024; verify with current API |
| Alpaca rate limits | MEDIUM | Documented as of 2024; current tier limits need verification |
| Railway auto-deploy behavior | HIGH | Railway documentation and behavior are stable and well-documented |
| Railway memory limits / pricing | MEDIUM | Pricing as of early 2025; verify current Hobby plan specs |
| Redis PER buffer sizing | HIGH | Arithmetic; Redis behavior well-known |
| Celery task acks_late behavior | HIGH | Celery documentation; stable behavior |
| Docker Compose startup ordering | HIGH | Docker documentation; stable behavior |
| Prefect 2.0 scheduler drift | MEDIUM | Community reports through 2024; may have been fixed in recent Prefect releases |
| FMP reliability/rate limits | MEDIUM | Community reports through early 2025; verify current plan limits with FMP |
| Momentum crashes | HIGH | Well-documented in factor investing literature |

**Items requiring live verification before build:**
1. Alpaca paper trading fill simulation behavior (current API docs)
2. Alpaca rate limits for current paper account tier
3. Railway Hobby plan memory/CPU specs and current pricing
4. FMP Starter plan rate limits and coverage quality for current S&P 500
5. Prefect 2.0 scheduler drift — check release notes for recent fixes
