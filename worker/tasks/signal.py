"""Signal computation Celery task."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
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


@celery_app.task(name="worker.tasks.signal.compute_signal", bind=True, max_retries=3)
def compute_signal(self, earnings_event_id: str) -> dict:
    """
    Load an earnings event, compute the full PEAD signal pipeline, update the
    earnings_events record, and trigger execute_entry if conditions are met.
    """
    engine = _get_engine()

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT * FROM earnings_events WHERE id = :id"),
            {"id": earnings_event_id},
        ).fetchone()

    if row is None:
        logger.error(f"EarningsEvent {earnings_event_id} not found")
        return {"status": "not_found"}

    event = dict(row._mapping)
    ticker = event["ticker"]
    announcement_ts: datetime = event["announcement_ts"]
    actual_eps = event.get("actual_eps")
    consensus_eps = event.get("consensus_eps")

    if actual_eps is None or consensus_eps is None:
        logger.info(f"EPS not available yet for {ticker} {earnings_event_id}")
        return {"status": "eps_missing"}

    # ------------------------------------------------------------------
    # 1. Load price history from DB
    # ------------------------------------------------------------------
    with engine.connect() as conn:
        price_rows = conn.execute(
            text(
                """
                SELECT time, close FROM prices
                WHERE ticker = :ticker
                  AND time <= :announce
                ORDER BY time DESC
                LIMIT 30
                """
            ),
            {"ticker": ticker, "announce": announcement_ts},
        ).fetchall()

    if not price_rows:
        logger.warning(f"No prices for {ticker} before {announcement_ts}")
        return {"status": "no_prices"}

    prices_series = pd.Series(
        {r[0]: float(r[1]) for r in price_rows if r[1] is not None}
    ).sort_index()

    # ------------------------------------------------------------------
    # 2. Compute EPS gap signal using existing module
    # ------------------------------------------------------------------
    from signals.eps_gap import EPSGapSignal
    from signals.intangible_filter import IntangibleFilter
    from signals.roic_filter import ROICFilter
    from config import CONFIG

    eps_signal = EPSGapSignal()
    intangible_filter = IntangibleFilter()
    roic_filter = ROICFilter()

    # Build minimal event DataFrame for batch API
    event_df = pd.DataFrame(
        [
            {
                "ticker": ticker,
                "announce_date": announcement_ts,
                "actual_eps": actual_eps,
                "consensus_eps": consensus_eps,
                "sector": event.get("gics_sector") or "Unknown",
                "is_cyclical": bool(event.get("is_cyclical", False)),
                "pre_announce_price": float(prices_series.iloc[-1]) if not prices_series.empty else np.nan,
                "sector_fwd_pe": 20.0,  # Neutral default
            }
        ]
    )

    try:
        event_df = eps_signal.compute_batch(event_df)
    except Exception as exc:
        logger.error(f"EPS gap computation failed for {ticker}: {exc}")
        raise self.retry(exc=exc, countdown=30)

    try:
        event_df = intangible_filter.apply_batch(event_df)
    except Exception as exc:
        logger.warning(f"Intangible filter failed for {ticker}: {exc} — using neutral multiplier")
        event_df["intangible_multiplier"] = 1.0

    try:
        event_df = roic_filter.apply_batch(event_df)
    except Exception as exc:
        logger.warning(f"ROIC filter failed for {ticker}: {exc} — using neutral multiplier")
        event_df["roic_multiplier"] = 1.0

    row_out = event_df.iloc[0]
    std_surprise = float(row_out.get("std_surprise", 0.0) or 0.0)
    intangible_mult = float(row_out.get("intangible_multiplier", 1.0) or 1.0)
    roic_mult = float(row_out.get("roic_multiplier", 1.0) or 1.0)
    raw_signal = std_surprise * intangible_mult * roic_mult
    implied_eps = float(row_out.get("implied_eps", consensus_eps) or consensus_eps)

    # ------------------------------------------------------------------
    # 3. Earnings quality decomposition (v3)
    # ------------------------------------------------------------------
    from signals.quality import QualityDecomposer
    from signals.hurdle_rates import passes_hurdle

    sector = event.get("gics_sector") or "Unknown"
    decomposer = QualityDecomposer()

    actual_rev = float(event.get("actual_rev") or 0.0)
    implied_rev = float(event.get("implied_rev") or actual_rev * 0.95 or 1.0)
    actual_margin = float(event.get("actual_margin") or 0.0)
    prior_margin = float(event.get("prior_margin") or actual_margin)
    curr_shares = float(event.get("curr_shares") or 1.0)
    prev_shares = float(event.get("prev_shares") or curr_shares)
    guidance = str(event.get("guidance") or "none")

    eq = decomposer.compute(
        raw_signal=raw_signal,
        actual_rev=actual_rev,
        implied_rev=implied_rev,
        actual_margin=actual_margin,
        prior_margin=prior_margin,
        curr_shares=curr_shares,
        prev_shares=prev_shares,
        guidance=guidance,
    )

    signal_composite = eq.signal_composite
    quality_score = eq.quality_score

    # Sector hurdle gate
    if not passes_hurdle(signal_composite, sector, global_min=CONFIG.portfolio_arch.mag7_signal_floor / 2):
        logger.info(f"Signal {signal_composite:.3f} for {ticker} below sector hurdle — no entry")
        _update_event(engine, earnings_event_id, std_surprise, intangible_mult, roic_mult,
                      signal_composite, implied_eps, "none", quality_score,
                      eq.revenue_surprise, eq.margin_surprise, eq.guidance_delta)
        return {"status": "below_hurdle", "signal": signal_composite}

    direction = "none"
    if signal_composite > CONFIG.signal.roic_wacc_spread_bps / 10000:
        direction = "long"
    elif signal_composite < -(CONFIG.signal.roic_wacc_spread_bps / 10000):
        direction = "short"

    # ------------------------------------------------------------------
    # 4. Query SAC Ensemble for position sizing (v3)
    # ------------------------------------------------------------------
    entry_size = 0.0
    hold_bin = 3   # default: 45-day bin
    macro_multiplier = 1.0
    moe_regime = "expansion"

    try:
        with engine.connect() as conn:
            macro_row = conn.execute(
                text(
                    "SELECT composite_score, size_multiplier, is_halted, erp_compressed, gv_stretched, vix FROM macro_state ORDER BY time DESC LIMIT 1"
                )
            ).fetchone()

        if macro_row:
            macro_score = int(macro_row[0] or 0)
            macro_multiplier = float(macro_row[1] or 1.0)
            is_halted = bool(macro_row[2])
            erp_compressed = bool(macro_row[3] or False)
            gv_stretched = bool(macro_row[4] or False)
            vix = float(macro_row[5] or 20.0)
            if is_halted:
                logger.info(f"Macro halt active — skipping signal for {ticker}")
                _update_event(engine, earnings_event_id, std_surprise, intangible_mult, roic_mult,
                              signal_composite, implied_eps, direction, quality_score,
                              eq.revenue_surprise, eq.margin_surprise, eq.guidance_delta)
                return {"status": "macro_halted"}
        else:
            macro_score = 0
            erp_compressed = False
            gv_stretched = False
            vix = 20.0
            is_halted = False

        from rl.sac_agent import SACEnsemble
        from rl.moe_controller import MoEController, Regime
        from config import CONFIG as cfg
        import pickle, pathlib

        is_cyclical = bool(event.get("is_cyclical", False))
        ticker_str = str(ticker)

        from portfolio.architecture import MAG7
        sector_oh = np.zeros(len(cfg.gics_sectors), dtype=np.float32)
        if sector in cfg.gics_sectors:
            sector_oh[cfg.gics_sectors.index(sector)] = 1.0

        obs = np.array([
            std_surprise, signal_composite, quality_score,
            eq.revenue_surprise, eq.margin_surprise, eq.guidance_delta,
            macro_score / 6.0, macro_multiplier,
            0.0, 0.0,            # holding_day_pct, pos_ret
            float(is_cyclical), float(ticker_str in MAG7),
            0.0, float(erp_compressed),
            1.0, float(gv_stretched),
            0.0, 0.0, 0.0, 0.0,  # sector_nav_pct, is_short, completion_sleeve, dtc
            *sector_oh,
        ], dtype=np.float32)

        ensemble_path = pathlib.Path("models/sac_ensemble.pkl")
        if ensemble_path.exists():
            with open(ensemble_path, "rb") as f:
                ensemble: SACEnsemble = pickle.load(f)
            entry_size, hold_bin = ensemble.select_action(obs, deterministic=True)
        else:
            logger.info("No SAC ensemble checkpoint — using naive baseline sizing")
            entry_size = min(abs(signal_composite) / 5.0, CONFIG.risk.max_position_weight)
            hold_bin = 4  # 60-day bin

        # MoE regime blending
        moe = MoEController()
        raw_entries = {r: entry_size for r in [Regime.EXPANSION, Regime.CAUTION, Regime.CRISIS]}
        raw_holds = {r: hold_bin for r in [Regime.EXPANSION, Regime.CAUTION, Regime.CRISIS]}
        moe_action = moe.blend(raw_entries, raw_holds, macro_score, vix=vix)
        entry_size = moe_action.entry_size
        hold_bin = moe_action.hold_bin
        moe_regime = moe_action.dominant_regime.value

    except Exception as exc:
        logger.warning(f"SAC ensemble prediction failed for {ticker}: {exc} — using naive baseline")
        entry_size = min(abs(signal_composite) / 5.0, CONFIG.risk.max_position_weight)
        hold_bin = 4

    action = entry_size * (1.0 if direction == "long" else -1.0)

    # ------------------------------------------------------------------
    # 5. Update earnings_events record
    # ------------------------------------------------------------------
    _update_event(
        engine, earnings_event_id, std_surprise, intangible_mult, roic_mult,
        signal_composite, implied_eps, direction, quality_score,
        eq.revenue_surprise, eq.margin_surprise, eq.guidance_delta,
    )

    # Dispatch alert for signal
    try:
        from worker.tasks.alerts import dispatch_alert
        dispatch_alert.delay(
            event_type="signal_generated",
            title=f"Signal: {ticker} ({direction})",
            message=f"signal_composite={signal_composite:.3f} quality={quality_score:.2f} hold_bin={hold_bin}",
            ticker=ticker,
            priority="medium",
        )
    except Exception:
        pass

    # ------------------------------------------------------------------
    # 6. Trigger entry if signal strong enough
    # ------------------------------------------------------------------
    import json
    min_threshold = 0.5
    with engine.connect() as conn:
        setting = conn.execute(
            text("SELECT value FROM system_settings WHERE key = 'signal'")
        ).fetchone()
        if setting:
            sig_cfg = json.loads(setting[0]) if isinstance(setting[0], str) else setting[0]
            min_threshold = float(sig_cfg.get("min_signal_threshold", 0.5))

    if abs(entry_size) >= 0.01 and abs(signal_composite) >= min_threshold and direction != "none":
        logger.info(f"Signal {signal_composite:.3f} for {ticker} — triggering entry (size={entry_size:.3f}, hold_bin={hold_bin})")
        from worker.tasks.execution import execute_entry
        execute_entry.delay(
            signal_id=earnings_event_id,
            action=action,
            macro_multiplier=macro_multiplier,
            sac_entry_size=entry_size,
            hold_bin=hold_bin,
            moe_regime=moe_regime,
        )
        return {"status": "entry_triggered", "action": action, "signal": signal_composite, "entry_size": entry_size}

    logger.info(f"Signal {signal_composite:.3f} for {ticker} below threshold — no entry")
    return {"status": "below_threshold", "signal": signal_composite}


def _update_event(
    engine,
    event_id: str,
    surprise_score: float,
    intangible_mult: float,
    roic_mult: float,
    signal_composite: float,
    implied_eps: Optional[float],
    direction: str,
    quality_score: float = 1.0,
    revenue_surprise: float = 0.0,
    margin_surprise: float = 0.0,
    guidance_delta: float = 0.0,
) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE earnings_events SET
                    surprise_score = :surprise_score,
                    intangible_mult = :intangible_mult,
                    roic_mult = :roic_mult,
                    signal_composite = :signal_composite,
                    implied_eps = :implied_eps,
                    direction = :direction,
                    quality_score = :quality_score,
                    revenue_surprise = :revenue_surprise,
                    margin_surprise = :margin_surprise,
                    guidance_delta = :guidance_delta
                WHERE id = :id
                """
            ),
            {
                "surprise_score": surprise_score,
                "intangible_mult": intangible_mult,
                "roic_mult": roic_mult,
                "signal_composite": signal_composite,
                "implied_eps": implied_eps,
                "direction": direction,
                "quality_score": quality_score,
                "revenue_surprise": revenue_surprise,
                "margin_surprise": margin_surprise,
                "guidance_delta": guidance_delta,
                "id": event_id,
            },
        )
