"""System-wide configuration for PEAD Trading System."""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DataConfig:
    fred_api_key: str = field(default_factory=lambda: os.getenv("FRED_API_KEY", ""))
    # Ken French data library base URL
    french_data_url: str = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
    # Start of backtest universe (PRD §8: train on 2010-2023)
    backtest_start: str = "2010-01-01"
    backtest_end: str = "2023-12-31"
    paper_trade_start: str = "2024-01-01"


@dataclass
class SignalConfig:
    # Holding window bounds (days)
    hold_min: int = 60
    hold_max: int = 90
    # Cyclical sectors use shorter window initially
    cyclical_hold_init: int = 45
    # Price window for market-implied EPS (trading days)
    pre_announce_window: int = 5
    # Surprise standardization lookback (quarters)
    surprise_std_quarters: int = 4
    # Intangible filter thresholds (intangible as % of trailing-12M revenue)
    intangible_multipliers: dict = field(default_factory=lambda: {
        "bottom": 1.0,   # bottom tercile
        "middle": 1.15,
        "top": 1.30,
    })
    # ROIC vs WACC filter
    roic_wacc_spread_bps: int = 200  # 200bps threshold
    roic_above_wacc_multiplier: float = 1.20
    roic_below_wacc_multiplier: float = 1.0
    roic_lookback_quarters: int = 8


@dataclass
class MacroConfig:
    # FRED series IDs
    yield_spread_series: str = "T10Y2Y"       # 10Y-2Y
    core_pce_series: str = "PCEPILFE"
    real_gdp_series: str = "GDPC1"
    hy_spread_series: str = "BAMLH0A0HYM2"
    sahm_series: str = "SAHMREALTIME"
    jpy_usd_series: str = "DEXJPUS"
    aud_usd_series: str = "DEXUSAL"

    # Adverse thresholds
    yield_spread_threshold: float = -0.25    # percent
    core_pce_threshold: float = 3.5          # percent YoY
    real_gdp_threshold: float = 1.0          # percent QoQ annualized
    hy_spread_threshold: float = 500.0       # bps
    vix_threshold: float = 30.0
    sahm_threshold: float = 0.5              # Sahm rule trigger

    # Position sizing multipliers by composite score
    sizing_multipliers: dict = field(default_factory=lambda: {
        0: 1.00,
        -1: 0.85,
        -2: 0.65,
        -3: 0.35,
    })
    halt_threshold: int = -4


@dataclass
class RiskConfig:
    # Position-level
    hard_stop_pct: float = -0.08         # -8% triggers exit
    max_position_weight: float = 0.05    # 5% of NAV at entry

    # Portfolio-level
    max_gross_exposure: float = 1.50     # 150%
    max_net_long: float = 0.80           # 80% of NAV
    max_sector_concentration: float = 0.30   # 30% gross
    max_earnings_week_pct: float = 0.20  # 20% entering same earnings week

    # Execution
    transaction_cost_bps: float = 12.5  # midpoint of 10-15bps round-trip


@dataclass
class RLConfig:
    algorithm: str = "SAC"
    beta_rolling_months: int = 60
    beta_recalibration_quarters: int = 1
    # Legacy PPO fields kept for backcompat
    total_timesteps: int = 1_000_000
    learning_rate: float = 3e-4
    n_steps: int = 2048
    batch_size: int = 64
    n_epochs: int = 10
    gamma: float = 0.99
    observation_dim: int = 31
    action_dim: int = 2


@dataclass
class SACConfig:
    n_agents: int = 5
    lr: float = 3e-4
    gamma: float = 0.99
    tau: float = 0.005
    target_entropy: float = -1.0
    per_alpha: float = 0.6
    per_beta_start: float = 0.4
    per_beta_end: float = 1.0
    per_beta_anneal_steps: int = 10_000
    per_buffer_size: int = 50_000
    per_decay_lambda: float = 0.001
    online_batch_size: int = 64
    transformer_d_model: int = 64
    transformer_heads: int = 4
    transformer_layers: int = 3   # FR-5.4: 3 layers per spec
    hold_duration_bins: list = field(default_factory=lambda: [10, 20, 30, 45, 60, 75, 90])


@dataclass
class PortfolioArchConfig:
    mag7_per_name_cap: float = 0.03
    mag7_signal_floor: float = 1.5
    mag7_quality_floor: float = 0.65
    mag7_aggregate_cap: float = 0.12
    erp_compression_cap: float = 0.8
    gv_stretched_threshold: float = 2.0
    gv_signal_adjustment: float = 0.25
    short_stop_pct: float = 0.06
    short_max_position_pct: float = 0.025
    short_signal_threshold: float = -1.0
    short_quality_threshold: float = 0.4
    short_days_to_cover_max: float = 5.0


@dataclass
class AlertConfig:
    sendgrid_api_key: str = field(default_factory=lambda: os.getenv("SENDGRID_API_KEY", ""))
    slack_webhook_url: str = field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL", ""))
    from_email: str = field(default_factory=lambda: os.getenv("ALERT_FROM_EMAIL", "alerts@pead.local"))
    to_email: str = field(default_factory=lambda: os.getenv("ALERT_TO_EMAIL", ""))
    alert_cooldown_seconds: int = 300
    max_retries: int = 3


@dataclass
class SystemConfig:
    data: DataConfig = field(default_factory=DataConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    macro: MacroConfig = field(default_factory=MacroConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    rl: RLConfig = field(default_factory=RLConfig)
    sac: SACConfig = field(default_factory=SACConfig)
    portfolio_arch: PortfolioArchConfig = field(default_factory=PortfolioArchConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # GICS sectors (11)
    gics_sectors: list = field(default_factory=lambda: [
        "Energy", "Materials", "Industrials", "Consumer Discretionary",
        "Consumer Staples", "Health Care", "Financials", "Information Technology",
        "Communication Services", "Utilities", "Real Estate"
    ])
    cyclical_sectors: set = field(default_factory=lambda: {
        "Energy", "Materials", "Industrials",
        "Consumer Discretionary", "Financials"
    })


CONFIG = SystemConfig()
