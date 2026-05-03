# PEAD Trading System

Autonomous Post-Earnings Announcement Drift (PEAD) trading system for the S&P 500, with a Reinforcement Learning agent optimised against FF5-adjusted alpha.

## Architecture

Four functional layers — data flows top to bottom, RL reward flows bottom to top:

| Layer | Module | Function |
|-------|--------|----------|
| L1 | `rl/reward.py` | FF5-adjusted alpha — the RL objective |
| L2 | `signals/` | Market-implied EPS gap + intangible / ROIC filters |
| L3 | `macro/` | Composite macro score gates position sizing |
| L4 | `rl/environment.py` | GICS sector conditioning in RL state space |

## Quick start

```bash
pip install -r requirements.txt

# Set your FRED API key (optional — synthetic data used if missing)
echo "FRED_API_KEY=your_key_here" > .env

# Run backtest (2010–2023 universe, synthetic data without Compustat)
python main.py backtest

# Show current macro regime
python main.py regime

# Show latest signals for a few tickers
python main.py signal --tickers AAPL MSFT NVDA

# Train RL agent (requires gymnasium + stable-baselines3)
python main.py train --algo PPO --timesteps 500000
```

## PRD success targets

| Metric | Target | Notes |
|--------|--------|-------|
| FF5-adjusted alpha | > 0.40%/month | Benchmark: USIF active 0.66%/mo |
| Sharpe (annualised) | > 1.0 | S&P 500 long-run ~0.5 |
| Max drawdown | < 15% | Hard constraint |
| RL vs. naive baseline | Positive improvement | Evaluated as information ratio |

## Production data requirements

Replace synthetic fallbacks with live feeds:

| Data | Source | Module |
|------|--------|--------|
| Earnings (actual EPS, non-recurring flags) | Compustat / FactSet | `data/earnings_data.py` |
| Daily adjusted prices | CRSP | `data/price_data.py` |
| FF5 factor returns | Ken French data library | `data/factor_data.py` |
| Macro series | FRED API | `data/fred_client.py` |
| R&D + SG&A, ROIC | Compustat quarterly | `data/earnings_data.py` |

Set `FRED_API_KEY` in `.env` — all other FRED series resolve automatically once the key is present.

## Signal logic

**Market-implied EPS gap** (L2 core signal):

```
implied_EPS = 5-day avg price / sector median forward P/E
std_surprise = (actual_EPS - implied_EPS) / rolling 4Q std dev
```

**Signal strength** (input to RL sizing):
```
signal_strength = std_surprise × intangible_multiplier × roic_multiplier
```

- `intangible_multiplier`: 1.0x / 1.15x / 1.3x by tercile of (R&D + SG&A) / revenue  
- `roic_multiplier`: 1.2x if ROIC > WACC by 200bps+, else 1.0x

## Macro regime

Six FRED signals scored -1 when adverse, plus a carry crash overlay:

```
T10Y2Y < -0.25%    → -1
Core PCE > 3.5%    → -1
Real GDP QoQ < 1%  → -1
HY spread > 500bps → -1
VIX > 30           → -1
Sahm Rule ≥ 0.5    → -1
Carry crash        → -1 (independent overlay)
```

Score → sizing multiplier: `0→1.0x`, `-1→0.85x`, `-2→0.65x`, `-3→0.35x`, `≤-4→halt`

## RL environment

- **Algorithm**: PPO (default), SAC optional  
- **Observation**: 18-dim — signal strength, macro score, holding day %, unrealised return, sector one-hot (11), cyclical flag  
- **Action**: continuous `[-1, 1]` position sizing (+ = long, − = short if enabled)  
- **Reward**: FF5 alpha at exit, computed with rolling 60-month OLS betas, recalibrated quarterly  
- **L4 sector init**: cyclical sectors start at 45-day hold, secular at 90-day — agent adapts from there

## Out of scope (v1.0)

- International equities  
- Options strategies  
- Intraday execution  
- Macro forecasting (regime module is observational only)  
- Small-cap universe (< $2B)
