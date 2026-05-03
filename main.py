"""PEAD Trading System — main entrypoint.

Usage:
  python main.py backtest               # Run backtest on 2010-2023 universe
  python main.py train                  # Train RL agent
  python main.py regime                 # Print current macro regime snapshot
  python main.py signal --tickers AAPL MSFT   # Print latest signals

Set FRED_API_KEY in .env for live macro data.
"""

from __future__ import annotations

import argparse
import sys
from loguru import logger

from config import CONFIG


def cmd_backtest(args) -> None:
    from backtest.engine import BacktestEngine
    engine = BacktestEngine(
        start=args.start,
        end=args.end,
        allow_short=args.short,
    )
    results = engine.run()
    metrics = results.compute_metrics()

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    for k, v in metrics.items():
        print(f"  {k:<30} {v}")
    print()
    print("SECTOR BREAKDOWN")
    print("-" * 60)
    sector_df = results.sector_breakdown()
    if not sector_df.empty:
        print(sector_df.to_string())
    print()

    # PRD target checks
    print("PRD TARGET CHECKS")
    print("-" * 60)
    alpha_ok = metrics.get("monthly_alpha_pct", 0) > 0.40
    sharpe_ok = metrics.get("annualised_sharpe", 0) > 1.0
    dd_ok = abs(metrics.get("max_drawdown_pct", -100)) < 15.0
    print(f"  FF5 alpha > 0.40%/mo : {'✓' if alpha_ok else '✗'} ({metrics.get('monthly_alpha_pct')}%)")
    print(f"  Sharpe > 1.0         : {'✓' if sharpe_ok else '✗'} ({metrics.get('annualised_sharpe')})")
    print(f"  Max DD < 15%         : {'✓' if dd_ok else '✗'} ({metrics.get('max_drawdown_pct')}%)")


def cmd_train(args) -> None:
    from data.price_data import PriceDataClient
    from signals.generator import SignalGenerator
    from macro.regime import MacroRegimeModule
    from rl.reward import FF5RewardFunction
    from rl.environment import PEADTradingEnv
    from rl.agent import RLAgent
    from risk.controls import RiskControls
    from backtest.engine import _DEFAULT_TICKERS

    logger.info("Preparing training environment...")
    tickers = args.tickers or _DEFAULT_TICKERS

    prices = PriceDataClient().get_prices(tickers, start=CONFIG.data.backtest_start)
    events = SignalGenerator(price_client=PriceDataClient()).generate(
        tickers, CONFIG.data.backtest_start, CONFIG.data.backtest_end
    )
    regime = MacroRegimeModule().build_regime_series(
        CONFIG.data.backtest_start, CONFIG.data.backtest_end
    )
    reward_fn = FF5RewardFunction()
    reward_fn.bootstrap_from_history()

    # 80/20 train/eval split by time
    split = int(len(events) * 0.8)
    train_events = events.iloc[:split].reset_index(drop=True)
    eval_events  = events.iloc[split:].reset_index(drop=True)

    train_env = PEADTradingEnv(
        events_df=train_events, prices_df=prices, regime_df=regime,
        reward_fn=reward_fn, risk_controls=RiskControls(),
    )
    eval_env = PEADTradingEnv(
        events_df=eval_events, prices_df=prices, regime_df=regime,
        reward_fn=reward_fn, risk_controls=RiskControls(),
    )

    agent = RLAgent(algorithm=args.algo)
    agent.train(
        env=train_env,
        total_timesteps=args.timesteps,
        eval_env=eval_env,
        tensorboard_log="./tensorboard" if args.tensorboard else None,
    )
    agent.save("pead_agent_v1")
    logger.info("Training complete. Model saved to models/pead_agent_v1.zip")


def cmd_regime(args) -> None:
    from macro.regime import MacroRegimeModule
    import pandas as pd

    module = MacroRegimeModule()
    regime = module.build_regime_series(
        start="2023-01-01",
        end=str(pd.Timestamp.today().date()),
    )
    latest = regime.iloc[-1]
    print("\n" + "=" * 60)
    print(f"MACRO REGIME — {regime.index[-1].date()}")
    print("=" * 60)
    print(f"  Composite score:    {int(latest['composite_score'])}")
    print(f"  Sizing multiplier:  {latest['sizing_multiplier']:.0%}")
    print(f"  Halted:             {'YES' if latest['is_halted'] else 'No'}")
    print()
    print("Component Signals:")
    for col in regime.columns:
        if col.startswith("s_"):
            val = int(latest[col])
            flag = " ← ADVERSE" if val < 0 else ""
            print(f"  {col:<15} {val:>3}{flag}")


def cmd_signal(args) -> None:
    from signals.generator import SignalGenerator
    import pandas as pd

    tickers = args.tickers or ["AAPL", "MSFT", "GOOGL"]
    gen = SignalGenerator()
    end = str(pd.Timestamp.today().date())
    start = str((pd.Timestamp.today() - pd.DateOffset(months=3)).date())
    events = gen.generate(tickers, start=start, end=end)

    print("\n" + "=" * 60)
    print("LATEST PEAD SIGNALS")
    print("=" * 60)
    display_cols = ["ticker", "announce_date", "std_surprise", "signal_strength",
                    "direction", "sector", "intangible_multiplier", "roic_multiplier"]
    available = [c for c in display_cols if c in events.columns]
    print(events[available].tail(20).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="PEAD Trading System")
    sub = parser.add_subparsers(dest="command")

    # backtest
    p_bt = sub.add_parser("backtest", help="Run historical backtest")
    p_bt.add_argument("--start", default=CONFIG.data.backtest_start)
    p_bt.add_argument("--end",   default=CONFIG.data.backtest_end)
    p_bt.add_argument("--short", action="store_true", help="Allow short positions")

    # train
    p_tr = sub.add_parser("train", help="Train RL agent")
    p_tr.add_argument("--tickers", nargs="+", default=None)
    p_tr.add_argument("--algo", default="PPO", choices=["PPO", "SAC"])
    p_tr.add_argument("--timesteps", type=int, default=CONFIG.rl.total_timesteps)
    p_tr.add_argument("--tensorboard", action="store_true")

    # regime
    sub.add_parser("regime", help="Show current macro regime")

    # signal
    p_sig = sub.add_parser("signal", help="Show latest signals")
    p_sig.add_argument("--tickers", nargs="+", default=None)

    args = parser.parse_args()

    if args.command == "backtest":
        cmd_backtest(args)
    elif args.command == "train":
        cmd_train(args)
    elif args.command == "regime":
        cmd_regime(args)
    elif args.command == "signal":
        cmd_signal(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
