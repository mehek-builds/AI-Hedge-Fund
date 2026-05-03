"""Trade execution Celery tasks — entry and exit."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from loguru import logger
from sqlalchemy import create_engine, text

from worker.celery_app import celery_app

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    return _engine


# ---------------------------------------------------------------------------
# execute_entry
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.execution.execute_entry", bind=True, max_retries=3)
def execute_entry(
    self,
    signal_id: str,
    action: float,
    macro_multiplier: float,
    sac_entry_size: float = 0.0,
    hold_bin: int = 4,
    moe_regime: str = "expansion",
) -> dict:
    """
    Compute share count from NAV + action sizing, submit Alpaca order,
    and create a new positions record.
    """
    engine = _get_engine()

    # Load the earnings event
    with engine.connect() as conn:
        event = conn.execute(
            text("SELECT * FROM earnings_events WHERE id = :id"),
            {"id": signal_id},
        ).fetchone()

    if event is None:
        logger.error(f"EarningsEvent {signal_id} not found for entry")
        return {"status": "event_not_found"}

    event = dict(event._mapping)
    ticker = event["ticker"]
    direction = event.get("direction", "long")

    if direction == "none":
        logger.info(f"Direction is 'none' for {ticker} — skipping entry")
        return {"status": "skipped_none_direction"}

    # Fetch Alpaca account for NAV
    from api.services.alpaca import get_alpaca_client
    try:
        alpaca = get_alpaca_client()
        account = alpaca.get_account()
        nav = float(account["nav"])
    except Exception as exc:
        logger.error(f"Failed to fetch Alpaca account: {exc}")
        raise self.retry(exc=exc, countdown=30)

    # Apply risk controls
    from risk.controls import RiskControls
    from config import CONFIG

    risk = RiskControls()
    effective_size = float(np.clip(abs(action) * macro_multiplier, 0.0, CONFIG.risk.max_position_weight))

    import pandas as pd
    announcement_ts = event["announcement_ts"]
    if not isinstance(announcement_ts, datetime):
        announcement_ts = pd.Timestamp(announcement_ts).to_pydatetime()

    sector = event.get("gics_sector") or "Unknown"
    allowed, reason = risk.can_enter(
        ticker=ticker,
        size=effective_size,
        sector=sector,
        announce_date=pd.Timestamp(announcement_ts),
    )
    if not allowed:
        logger.warning(f"Risk check blocked entry for {ticker}: {reason}")
        return {"status": "risk_blocked", "reason": reason}

    # Get current price
    with engine.connect() as conn:
        price_row = conn.execute(
            text(
                "SELECT close FROM prices WHERE ticker = :ticker ORDER BY time DESC LIMIT 1"
            ),
            {"ticker": ticker},
        ).fetchone()

    if price_row is None or price_row[0] is None:
        logger.error(f"No price available for {ticker}")
        return {"status": "no_price"}

    current_price = float(price_row[0])
    position_value = nav * effective_size
    shares = max(1, int(position_value / current_price))

    # Hard stop price
    if direction == "long":
        stop_price = current_price * (1 + CONFIG.risk.hard_stop_pct)  # hard_stop_pct is negative
    else:
        stop_price = current_price * (1 - CONFIG.risk.hard_stop_pct)

    # Holding period from SAC hold_bin (bins: 10,20,30,45,60,75,90)
    _HOLD_BINS = [10, 20, 30, 45, 60, 75, 90]
    holding_days_target = _HOLD_BINS[int(np.clip(hold_bin, 0, len(_HOLD_BINS) - 1))]

    # Submit order
    order_side = "buy" if direction == "long" else "sell"
    alpaca_order_id: Optional[str] = None
    entry_price = current_price

    try:
        order = alpaca.submit_order(symbol=ticker, qty=shares, side=order_side)
        alpaca_order_id = order["id"]
        if order.get("filled_avg_price"):
            entry_price = float(order["filled_avg_price"])
    except Exception as exc:
        logger.error(f"Alpaca order submission failed for {ticker}: {exc}")
        raise self.retry(exc=exc, countdown=30)

    # Get macro score at entry
    with engine.connect() as conn:
        macro_row = conn.execute(
            text("SELECT composite_score FROM macro_state ORDER BY time DESC LIMIT 1")
        ).fetchone()
    macro_score_at_entry = int(macro_row[0]) if macro_row else 0

    # Create position record
    now = datetime.now(timezone.utc)
    position_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO positions (id, ticker, signal_id, entry_ts, entry_price, shares,
                    direction, stop_price, holding_days_target, hold_bin, sac_entry_size,
                    rl_action_size, moe_regime, macro_score_at_entry, gics_sector,
                    alpaca_order_id, status, created_at)
                VALUES (:id, :ticker, :signal_id, :entry_ts, :entry_price, :shares,
                    :direction, :stop_price, :holding_days_target, :hold_bin, :sac_entry_size,
                    :rl_action_size, :moe_regime, :macro_score_at_entry, :gics_sector,
                    :alpaca_order_id, 'open', :created_at)
                """
            ),
            {
                "id": position_id,
                "ticker": ticker,
                "signal_id": signal_id,
                "entry_ts": now,
                "entry_price": entry_price,
                "shares": shares,
                "direction": direction,
                "stop_price": stop_price,
                "holding_days_target": holding_days_target,
                "hold_bin": int(hold_bin),
                "sac_entry_size": float(sac_entry_size),
                "rl_action_size": float(action),
                "moe_regime": moe_regime,
                "macro_score_at_entry": macro_score_at_entry,
                "gics_sector": sector,
                "alpaca_order_id": alpaca_order_id,
                "created_at": now,
            },
        )

    risk.register_entry(
        ticker=ticker,
        size=effective_size,
        sector=sector,
        announce_date=pd.Timestamp(announcement_ts),
    )

    logger.info(
        f"Entry executed: {ticker} {direction} {shares} shares @ {entry_price:.2f} "
        f"(position_id={position_id}, hold_bin={hold_bin}, regime={moe_regime})"
    )

    try:
        from worker.tasks.alerts import dispatch_alert
        dispatch_alert.delay(
            event_type="entry_executed",
            title=f"Entry: {ticker} {direction}",
            message=f"{shares} shares @ {entry_price:.2f} | size={sac_entry_size:.3f} | hold={holding_days_target}d | regime={moe_regime}",
            ticker=ticker,
            priority="medium",
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "position_id": position_id,
        "ticker": ticker,
        "shares": shares,
        "entry_price": entry_price,
        "alpaca_order_id": alpaca_order_id,
    }


# ---------------------------------------------------------------------------
# execute_exit
# ---------------------------------------------------------------------------


@celery_app.task(name="worker.tasks.execution.execute_exit", bind=True, max_retries=3)
def execute_exit(self, position_id: str, reason: str) -> dict:
    """
    Close an Alpaca position, update the positions record, compute FF5 alpha,
    and create an rl_episodes record.
    """
    engine = _get_engine()

    with engine.connect() as conn:
        pos = conn.execute(
            text("SELECT * FROM positions WHERE id = :id"),
            {"id": position_id},
        ).fetchone()

    if pos is None:
        logger.error(f"Position {position_id} not found")
        return {"status": "not_found"}

    pos = dict(pos._mapping)
    ticker = pos["ticker"]
    direction = pos["direction"]
    entry_price = float(pos["entry_price"] or 0)
    shares = int(pos["shares"] or 0)
    rl_action = float(pos.get("rl_action_size") or 0.0)

    if pos["status"] == "closed":
        logger.warning(f"Position {position_id} already closed")
        return {"status": "already_closed"}

    # Close position in Alpaca
    from api.services.alpaca import get_alpaca_client
    exit_price = entry_price  # fallback

    try:
        alpaca = get_alpaca_client()
        order = alpaca.close_position(ticker)
        if order.get("filled_avg_price"):
            exit_price = float(order["filled_avg_price"])
    except Exception as exc:
        logger.error(f"Alpaca close_position failed for {ticker}: {exc}")
        raise self.retry(exc=exc, countdown=30)

    # Realized P&L
    if direction == "long":
        realized_pnl = (exit_price - entry_price) * shares
        position_return = (exit_price - entry_price) / entry_price if entry_price else 0.0
    else:
        realized_pnl = (entry_price - exit_price) * shares
        position_return = (entry_price - exit_price) / entry_price if entry_price else 0.0

    # FF5 alpha
    ff5_alpha: Optional[float] = None
    try:
        from rl.reward import FF5RewardFunction
        from config import CONFIG

        entry_ts = pos["entry_ts"]
        now = datetime.now(timezone.utc)
        if not isinstance(entry_ts, datetime):
            import pandas as pd
            entry_ts = pd.Timestamp(entry_ts).to_pydatetime()

        reward_fn = FF5RewardFunction()
        tc = CONFIG.risk.transaction_cost_bps / 10_000
        ff5_alpha = reward_fn.compute_reward(
            entry_date=entry_ts,
            exit_date=now,
            position_return=position_return * abs(rl_action),
            transaction_cost=tc,
        )
    except Exception as exc:
        logger.warning(f"FF5 alpha computation failed for {position_id}: {exc}")

    now = datetime.now(timezone.utc)

    # Update position
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE positions SET
                    exit_ts = :exit_ts,
                    exit_price = :exit_price,
                    exit_reason = :exit_reason,
                    realized_pnl = :realized_pnl,
                    ff5_alpha = :ff5_alpha,
                    status = 'closed'
                WHERE id = :id
                """
            ),
            {
                "exit_ts": now,
                "exit_price": exit_price,
                "exit_reason": reason,
                "realized_pnl": realized_pnl,
                "ff5_alpha": ff5_alpha,
                "id": position_id,
            },
        )

    # Create RL episode record
    episode_id = str(uuid.uuid4())

    # Build state vector — use entry obs dims
    with engine.connect() as conn:
        macro_row = conn.execute(
            text("SELECT composite_score, size_multiplier FROM macro_state ORDER BY time DESC LIMIT 1")
        ).fetchone()
        signal_row = conn.execute(
            text("SELECT signal_composite, surprise_score, is_cyclical, gics_sector FROM earnings_events WHERE id = :id"),
            {"id": str(pos.get("signal_id"))},
        ).fetchone() if pos.get("signal_id") else None

    macro_score = int(macro_row[0]) if macro_row else 0
    macro_mult = float(macro_row[1]) if macro_row else 1.0

    from config import CONFIG as cfg
    sector = pos.get("gics_sector") or "Unknown"
    is_cyclical = False
    signal_composite = 0.0
    surprise_score = 0.0

    if signal_row:
        signal_composite = float(signal_row[0] or 0.0)
        surprise_score = float(signal_row[1] or 0.0)
        is_cyclical = bool(signal_row[2])
        sector = signal_row[3] or sector

    sector_oh = [0.0] * len(cfg.gics_sectors)
    if sector in cfg.gics_sectors:
        sector_oh[cfg.gics_sectors.index(sector)] = 1.0

    state_vector = [
        surprise_score,
        signal_composite,
        macro_score / 6.0,
        macro_mult,
        1.0,  # holding_day_pct = 1.0 at exit
        float(np.clip(position_return, -0.15, 0.15)),
        float(is_cyclical),
        *sector_oh,
    ]

    reward = float(ff5_alpha) if ff5_alpha is not None else float(realized_pnl)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO rl_episodes (id, position_id, state_vector, action, reward, done, created_at)
                VALUES (:id, :position_id, :state_vector::jsonb, :action, :reward, true, :created_at)
                """
            ),
            {
                "id": episode_id,
                "position_id": position_id,
                "state_vector": json.dumps([float(x) for x in state_vector]),
                "action": rl_action,
                "reward": reward,
                "created_at": now,
            },
        )

    logger.info(
        f"Exit executed: {ticker} {direction} @ {exit_price:.2f} "
        f"P&L={realized_pnl:.2f} alpha={ff5_alpha} reason={reason}"
    )

    try:
        from worker.tasks.alerts import dispatch_alert
        event_type = "stop_loss_triggered" if reason == "stop" else "exit_executed"
        priority = "high" if reason == "stop" else "medium"
        dispatch_alert.delay(
            event_type=event_type,
            title=f"Exit ({reason}): {ticker}",
            message=f"P&L={realized_pnl:.2f} alpha={ff5_alpha:.4f if ff5_alpha else 'N/A'} @ {exit_price:.2f}",
            ticker=ticker,
            priority=priority,
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "position_id": position_id,
        "realized_pnl": realized_pnl,
        "ff5_alpha": ff5_alpha,
        "episode_id": episode_id,
    }
