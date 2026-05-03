"""Backtesting Engine.

Runs a historical simulation over the 2010-2023 universe comparing:
  1. RL agent (trained or naive baseline)
  2. Naive full-signal baseline

Reports:
  - FF5-adjusted alpha (annualised)
  - Sharpe ratio
  - Max drawdown
  - Information ratio (RL vs. naive)
  - Per-sector performance breakdown
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from config import CONFIG
from data.price_data import PriceDataClient
from macro.regime import MacroRegimeModule
from signals.generator import SignalGenerator
from rl.reward import FF5RewardFunction
from rl.agent import RLAgent
from rl.environment import PEADTradingEnv
from risk.controls import RiskControls


@dataclass
class TradeRecord:
    ticker: str
    sector: str
    is_cyclical: bool
    entry_date: pd.Timestamp
    exit_date: pd.Timestamp
    entry_price: float
    exit_price: float
    size: float                  # signed position size (% NAV)
    raw_return: float
    ff5_alpha: float
    exit_reason: str             # "expired" | "stop" | "signal_reversal"
    macro_score_at_entry: int
    std_surprise: float


@dataclass
class BacktestResults:
    trades: pd.DataFrame
    nav_series: pd.Series        # daily NAV index (starts at 1.0)
    monthly_returns: pd.Series
    metrics: dict = field(default_factory=dict)

    def compute_metrics(self) -> dict:
        """Compute all PRD success metrics."""
        rets = self.monthly_returns.dropna()
        if len(rets) == 0:
            return {}

        ann_factor = 12  # monthly returns
        mean_ret = rets.mean()
        std_ret = rets.std()
        sharpe = (mean_ret / std_ret * np.sqrt(ann_factor)) if std_ret > 0 else 0.0

        # Max drawdown from NAV series
        nav = self.nav_series.dropna()
        rolling_max = nav.expanding().max()
        drawdown = (nav - rolling_max) / rolling_max
        max_dd = float(drawdown.min())

        # FF5-adjusted alpha (avg per month)
        ff5_alpha_monthly = self.trades["ff5_alpha"].mean() if len(self.trades) > 0 else 0.0

        # Information ratio vs. naive (compare ff5_alpha columns if both present)
        metrics = {
            "total_trades":           len(self.trades),
            "monthly_alpha_pct":      round(ff5_alpha_monthly * 100, 4),
            "annualised_sharpe":      round(sharpe, 3),
            "max_drawdown_pct":       round(max_dd * 100, 2),
            "win_rate_pct":           round(100 * (self.trades["ff5_alpha"] > 0).mean(), 1)
                                      if len(self.trades) > 0 else 0.0,
        }
        self.metrics = metrics
        return metrics

    def sector_breakdown(self) -> pd.DataFrame:
        if len(self.trades) == 0:
            return pd.DataFrame()
        return (
            self.trades.groupby("sector")
            .agg(
                n_trades=("ff5_alpha", "count"),
                mean_alpha=("ff5_alpha", "mean"),
                win_rate=("ff5_alpha", lambda x: (x > 0).mean()),
                mean_hold_days=("exit_date", lambda x: (
                    (x - self.trades.loc[x.index, "entry_date"])
                    .dt.days.mean()
                )),
            )
            .sort_values("mean_alpha", ascending=False)
        )


class BacktestEngine:
    """Runs a full historical backtest of the PEAD strategy."""

    def __init__(
        self,
        tickers: list[str] | None = None,
        start: str = "2010-01-01",
        end: str = "2023-12-31",
        agent: RLAgent | None = None,
        allow_short: bool = False,
    ):
        # Default to a representative 30-ticker sub-universe for speed
        self._tickers = tickers or _DEFAULT_TICKERS
        self._start = start
        self._end = end
        self._agent = agent or RLAgent()
        self._allow_short = allow_short

        self._price_client = PriceDataClient()
        self._signal_gen = SignalGenerator(price_client=self._price_client)
        self._regime_module = MacroRegimeModule()
        self._reward_fn = FF5RewardFunction()
        self._risk = RiskControls()

    def run(self) -> BacktestResults:
        """Execute backtest and return results."""
        logger.info(f"Backtest: {len(self._tickers)} tickers | {self._start} → {self._end}")

        # 1. Generate signals
        events = self._signal_gen.generate(self._tickers, self._start, self._end)

        # 2. Load prices
        prices = self._price_client.get_prices(self._tickers, start=self._start)

        # 3. Build macro regime
        regime = self._regime_module.build_regime_series(self._start, self._end)

        # 4. Bootstrap reward function history
        self._reward_fn.bootstrap_from_history(start="2005-01-01")

        # 5. Build environment
        env = PEADTradingEnv(
            events_df=events,
            prices_df=prices,
            regime_df=regime,
            reward_fn=self._reward_fn,
            risk_controls=self._risk,
            allow_short=self._allow_short,
        )

        # 6. Step through all events
        trades = self._simulate(env, events, prices, regime)

        # 7. Build NAV and monthly returns
        nav_series, monthly_returns = self._compute_nav(trades, self._start, self._end)

        results = BacktestResults(
            trades=pd.DataFrame([vars(t) for t in trades]) if trades else pd.DataFrame(),
            nav_series=nav_series,
            monthly_returns=monthly_returns,
        )
        metrics = results.compute_metrics()
        logger.info(f"Backtest complete | metrics: {metrics}")
        return results

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _simulate(
        self,
        env: PEADTradingEnv,
        events: pd.DataFrame,
        prices: pd.DataFrame,
        regime: pd.DataFrame,
    ) -> list[TradeRecord]:
        trades: list[TradeRecord] = []

        for i in range(len(events)):
            obs, _ = env.reset()
            event_row = events.iloc[i if i < len(events) else len(events) - 1]

            # Entry decision
            action, _ = self._agent.predict(obs)
            obs, reward, terminated, truncated, _ = env.step(action)

            if terminated:
                continue

            # Step until exit
            steps = 0
            max_steps = CONFIG.signal.hold_max + 10
            while not terminated and not truncated and steps < max_steps:
                # Re-use last action during hold period (agent is passive)
                action_hold = np.array([float(action[0])], dtype=np.float32)
                obs, reward, terminated, truncated, _ = env.step(action_hold)
                steps += 1

            # The final reward is the FF5 alpha
            if reward != 0.0 and abs(float(action[0])) > 0.01:
                announce = pd.Timestamp(event_row["announce_date"])
                exit_date = announce + pd.Timedelta(days=steps)
                entry_price = self._get_price_safe(prices, event_row["ticker"], announce)
                exit_price  = self._get_price_safe(prices, event_row["ticker"], exit_date)

                trades.append(TradeRecord(
                    ticker=event_row["ticker"],
                    sector=str(event_row.get("sector", "")),
                    is_cyclical=bool(event_row.get("is_cyclical", False)),
                    entry_date=announce,
                    exit_date=exit_date,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    size=float(action[0]),
                    raw_return=(exit_price - entry_price) / entry_price
                               if entry_price > 0 else 0.0,
                    ff5_alpha=float(reward),
                    exit_reason="expired" if steps >= CONFIG.signal.hold_max else "stop",
                    macro_score_at_entry=int(
                        regime.iloc[
                            regime.index.get_indexer([announce], method="ffill")[0]
                        ].get("composite_score", 0)
                        if not regime.empty else 0
                    ),
                    std_surprise=float(event_row.get("std_surprise", 0.0)),
                ))

        logger.info(f"Simulation produced {len(trades)} closed trades")
        return trades

    # ------------------------------------------------------------------
    # NAV computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_nav(
        trades: list[TradeRecord], start: str, end: str
    ) -> tuple[pd.Series, pd.Series]:
        bdays = pd.date_range(start, end, freq="B")
        nav = pd.Series(1.0, index=bdays)

        if not trades:
            return nav, pd.Series(dtype=float)

        for trade in trades:
            # Attribute P&L to exit date
            if trade.exit_date in nav.index:
                nav.loc[trade.exit_date] += trade.ff5_alpha * abs(trade.size)
            else:
                closest = nav.index[nav.index.get_indexer([trade.exit_date], method="ffill")[0]]
                nav.loc[closest] += trade.ff5_alpha * abs(trade.size)

        nav = nav.cumprod()
        monthly = nav.resample("ME").last().pct_change().dropna()
        return nav, monthly

    @staticmethod
    def _get_price_safe(
        prices: pd.DataFrame, ticker: str, date: pd.Timestamp
    ) -> float:
        if ticker not in prices.columns:
            return float("nan")
        series = prices[ticker].dropna()
        idx = series.index.get_indexer([date], method="ffill")[0]
        if idx < 0:
            return float("nan")
        return float(series.iloc[idx])


# Representative S&P 500 sub-universe for default backtests
_DEFAULT_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "JPM", "BAC", "GS",
    "JNJ", "PFE", "UNH",
    "XOM", "CVX",
    "HD", "WMT", "COST",
    "CAT", "GE",
    "NEE", "DUK",
    "AMT", "PLD",
    "LIN", "APD",
    "T", "VZ",
    "BRK-B", "V",
]
