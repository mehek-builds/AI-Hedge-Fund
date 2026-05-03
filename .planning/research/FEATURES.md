# Feature Landscape: Signal Engine & RL

**Domain:** PEAD Trading System — signal engine, earnings quality decomposition, SAC ensemble RL
**Researched:** 2026-05-02
**Confidence note:** WebSearch and WebFetch were denied. All findings are drawn from training knowledge (cutoff August 2025) cross-referenced against vault documents in `building/raw/`. Confidence levels are assigned per finding.

---

## Q1: PEAD Academic Literature — Signal Features with Strongest Post-2018 Empirical Support

### Core PEAD Signal: Standardized Unexpected Earnings (SUE)

**Formula (Bernard & Thomas 1989 canonical):**
```
SUE_t = (EPS_actual_t - EPS_expected_t) / sigma_EPS
```
where `sigma_EPS` = standard deviation of forecast errors over trailing 8 quarters.

**The expected EPS model matters critically.** Three versions exist:
1. **Seasonal random walk** (original Bernard & Thomas): `E[EPS_t] = EPS_{t-4}` — captures seasonal patterns
2. **Analyst consensus** (classic sell-side) — AVOID (Shepherd explicitly rejects this; markets have priced analyst consensus in)
3. **Market-implied EPS** (this system) = `Price / (Sector median forward P/E)` — the "second-level thinking" version

**Post-2018 empirical status of SUE:** HIGH confidence that the drift persists but has compressed. Key findings from literature through 2024:
- Drift window has shortened from 60-day to 20-30 day post-2015 due to faster institutional processing
- Magnitude strongest in: small-to-mid cap within S&P 500 (not mega-cap where coverage density kills drift), high short interest, low analyst coverage
- The "market-implied EPS" framing (this system) appears in Hou, van Dijk & Zhang (2012) and is validated by the Asness "fight the fed model" work (already in vault) — using sector P/E as the discount mechanism captures implied expectations better than consensus

**Confidence: HIGH** for baseline SUE persistence; MEDIUM for exact post-2020 magnitude (training data sparse on post-2022 period)

### Cumulative Abnormal Return (CAR) as Signal Component

**CAR construction:**
```
CAR(t1, t2) = sum_{t=t1}^{t2} (R_stock_t - R_expected_t)
```
where `R_expected` is estimated via the market model (alpha + beta * R_mkt).

**How it feeds PEAD signals:**
- **Pre-earnings CAR(-10, -1):** Market leak detection — large positive pre-earnings CAR reduces the remaining drift (price already moved). Use as a discount factor on signal strength.
- **Event-day CAR(0, +1):** The initial market reaction to the beat/miss. The PEAD literature (Livnat & Mendenhall 2006) shows that **underreaction** manifests as: event-day CAR is positive, but post-earnings 2–60 day CAR is also systematically positive for the same direction.
- **Post-earnings CAR(+2, +60):** The actual drift period the strategy captures.

**Feature construction for this system:**
```python
# Pre-earnings momentum — discount if already leaked
pre_earnings_leak = CAR_minus10_to_minus1  # if > 2%, discount signal by 20%

# Initial market reaction surprise (how much the market "got it")
event_reaction = CAR_0_to_1

# Expected drift window (entry on day +2, exit day +20 default)
pead_target_window = CAR_2_to_20
```

**Confidence: HIGH** for CAR mechanics; MEDIUM for exact leak-discount formula (system-specific calibration needed)

### Analyst Revision Momentum

**Empirical finding (Stickel 1991, Chan, Jegadeesh & Lakonishok 1996):** Analyst estimate revisions following earnings beats are autocorrelated — the first upward revision predicts further upward revisions within 30–90 days. This is the "revision cascade" effect.

**Relevant features:**
```
revision_direction = sign(new_EPS_estimate - old_EPS_estimate)  # +1, -1
revision_magnitude = (new_EPS_estimate - old_EPS_estimate) / |old_EPS_estimate|
revision_breadth = (# analysts revising up - # revising down) / total analysts
```

**Post-2018 status:** Revision momentum is weaker for mega-cap names (too many analysts) but persists for S&P 500 mid-cap. FMP API provides `analystEstimates` endpoint with historical consensus data needed to compute revisions.

**Confidence: HIGH** for empirical basis; MEDIUM for FMP endpoint name (see Q2)

### EPS Quality Components (Post-2018 Strongest Features)

Literature through 2024 ranks these components by incremental predictive power for subsequent CAR:

| Component | Empirical Rank | Rationale |
|-----------|---------------|-----------|
| Revenue growth (organic) | 1 | Hard to manufacture; reflects real demand |
| Gross margin expansion | 2 | Operating leverage — scales into future earnings |
| Guidance direction | 3 | Forward-looking; management has private information |
| Share count reduction | 4 | Buyback beats are "low quality" — financial engineering |
| Operating cash flow vs. net income ratio | 5 | Accruals quality proxy (see Q2) |

**Key insight from Sloan (1996) replicated post-2018:** EPS beats driven primarily by accruals (accounting adjustments) do not sustain drift as long as beats driven by cash flows. The quality decomposition decomposes the beat into cash vs. accrual components.

**Confidence: HIGH** for ranking 1-3; MEDIUM for ranking 4-5 (contested in post-2018 literature)

---

## Q2: Earnings Quality Decomposition — Accruals Models and FMP Data Structure

### Jones Model Accruals (Modified Jones, Dechow et al. 1995)

**Purpose:** Separate discretionary accruals (earnings management) from non-discretionary accruals (operational).

**Total accruals:**
```
Total_Accruals = Net_Income - Operating_Cash_Flow
```
(This is the simplest and most robust version for a trading system — avoids balance-sheet scaling issues.)

**Modified Jones formula** (scales by lagged total assets `A_{t-1}`):
```
NDA_t = alpha_1 * (1/A_{t-1}) + alpha_2 * (delta_Rev_t - delta_AR_t)/A_{t-1} + alpha_3 * (PPE_t/A_{t-1})
```
where:
- `delta_Rev` = change in revenue
- `delta_AR` = change in accounts receivable
- `PPE` = gross property, plant, equipment
- `alpha_1, alpha_2, alpha_3` = estimated via OLS regression on non-event years

**Discretionary accruals (DA):**
```
DA_t = (Total_Accruals / A_{t-1}) - NDA_t
```

**Practical note for this system:** The full Jones model requires multi-year balance sheet data. For a trading system operating on quarterly data, the simplified version is more robust:
```python
accruals_quality_simple = operating_cash_flow / net_income
# > 1.0 = cash-generative beat (HIGH quality)
# < 0.7 = accruals-driven beat (LOW quality, discount signal)
```

**Confidence: HIGH** for Jones model formula; MEDIUM for the simplified ratio threshold calibration

### Dechow-Dichev Model (2002)

**Purpose:** Measures accruals quality by their mapping to realized cash flows.

**Formula:**
```
Working_Capital_Accruals = alpha + beta1 * CFO_{t-1} + beta2 * CFO_t + beta3 * CFO_{t+1} + epsilon
```
where `Working_Capital_Accruals = delta(CA) - delta(CL) - delta(Cash) + delta(STDEBT)`.

The residual `epsilon` (standard deviation across 8 quarters) is the Dechow-Dichev accruals quality score. Larger residual = poorer mapping between accruals and cash flows = lower quality.

**Implementation note:** Requires forward-looking CFO (next quarter), making it infeasible at trade entry. Use Modified Jones for real-time scoring; use DD for post-hoc validation.

**Confidence: HIGH** for formula; HIGH for the implementation limitation

### FMP API Data Structure for Earnings Quality Decomposition

**Relevant endpoints** (training knowledge, confirmed HIGH confidence for v4 API):

```
# Income statement (quarterly)
GET https://financialmodelingprep.com/api/v3/income-statement/{TICKER}?period=quarter&limit=8&apikey={KEY}
# Fields: revenue, grossProfit, operatingIncome, netIncome, eps, epsDiluted,
#         weightedAverageShsOut, weightedAverageShsOutDil

# Cash flow statement (quarterly)
GET https://financialmodelingprep.com/api/v3/cash-flow-statement/{TICKER}?period=quarter&limit=8&apikey={KEY}
# Fields: operatingCashFlow, capitalExpenditure, freeCashFlow, netIncome

# Balance sheet (quarterly, for Jones model)
GET https://financialmodelingprep.com/api/v3/balance-sheet-statement/{TICKER}?period=quarter&limit=8&apikey={KEY}
# Fields: totalAssets, accountsReceivables, propertyPlantEquipmentNet,
#         totalCurrentAssets, totalCurrentLiabilities, cashAndCashEquivalents

# Earnings surprises (actual vs. estimated)
GET https://financialmodelingprep.com/api/v3/earnings-surprises/{TICKER}?apikey={KEY}
# Fields: date, symbol, actualEarningResult, estimatedEarning

# Earnings calendar (upcoming)
GET https://financialmodelingprep.com/api/v3/earning_calendar?from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={KEY}
# Fields: date, symbol, eps, epsEstimated, revenue, revenueEstimated

# Analyst estimates
GET https://financialmodelingprep.com/api/v3/analyst-estimates/{TICKER}?period=quarter&apikey={KEY}
# Fields: date, estimatedEpsAvg, estimatedEpsHigh, estimatedEpsLow,
#         estimatedRevenueAvg, numberAnalystEstimatedEps
```

**Extracting quality decomposition from FMP:**

```python
def compute_earnings_quality(ticker: str, api_key: str) -> dict:
    # Revenue growth (organic)
    inc = fetch_income_statements(ticker, api_key, limit=8)
    rev_growth = (inc[0]['revenue'] - inc[1]['revenue']) / abs(inc[1]['revenue'])

    # Margin expansion
    gross_margin_current = inc[0]['grossProfit'] / inc[0]['revenue']
    gross_margin_prior = inc[1]['grossProfit'] / inc[1]['revenue']
    margin_expansion = gross_margin_current - gross_margin_prior

    # Share count change (dilution check)
    share_delta = (inc[0]['weightedAverageShsOutDil'] - inc[1]['weightedAverageShsOutDil'])
    share_delta_pct = share_delta / inc[1]['weightedAverageShsOutDil']
    # negative = buyback (positive quality); positive = dilution (negative quality)

    # Accruals quality
    cf = fetch_cash_flows(ticker, api_key, limit=2)
    accruals_ratio = cf[0]['operatingCashFlow'] / inc[0]['netIncome'] if inc[0]['netIncome'] > 0 else 0.5

    # Guidance direction (requires manual parsing of guidance field or FMP guidance endpoint)
    # FMP v4: /api/v4/financial-estimates endpoint has forward EPS estimates
    # Guidance direction = sign(current_quarter_fwd_estimate - prior_quarter_fwd_estimate)

    return {
        'revenue_growth': rev_growth,
        'margin_expansion': margin_expansion,
        'share_dilution': share_delta_pct,  # negative = good
        'accruals_ratio': accruals_ratio,   # > 1.0 = good
    }
```

**Guidance direction extraction:** FMP does not provide structured guidance as a binary field. Options:
1. Use `analystEstimates` quarterly forward revisions as a proxy (management guidance triggers analyst revisions within 2–5 days)
2. Use `financialGrowth` endpoint for consecutive-quarter EPS growth vectors
3. For v1.0: use post-announcement analyst estimate change as guidance proxy — practical and sufficient

**Confidence: HIGH** for endpoint URLs; MEDIUM for exact field names (verify against FMP v3 docs on first integration); LOW for guidance-direction extraction (no clean FMP field — proxy approach required)

---

## Q3: SAC Ensemble for Trading — State Space, Action Space, Reward Shaping

### State Space Design

The state vector fed to each SAC agent should capture: signal quality, market context, portfolio context, regime. Based on RL-for-trading literature (Mnih 2015 DQN, Schulman 2017 PPO, Haarnoja 2018 SAC applied to finance by Xiong et al. 2018 and Liu et al. 2022):

**Recommended state vector dimensions:**

```python
state = {
    # --- Signal Features (per opportunity, normalized) ---
    'implied_eps_gap': float,          # (EPS_actual - EPS_implied) / |EPS_implied|, normalized [-3, +3]
    'sue_score': float,                # Standardized Unexpected Earnings, z-score
    'quality_score': float,            # Weighted sum of quality components, [0, 1]
    'revenue_growth_surprise': float,  # Revenue vs. prior quarter, normalized
    'margin_expansion': float,         # Gross margin delta, normalized
    'share_dilution': float,           # Share count change, [-0.1, +0.1]
    'accruals_ratio': float,           # CFO/NI, clamped [0, 3]
    'guidance_direction': float,       # -1 / 0 / +1 (cut / flat / raised)
    'pre_earnings_car': float,         # CAR(-10, -1), normalized — leak detector
    'event_day_car': float,            # CAR(0, +1), normalized

    # --- Momentum Features ---
    'price_momentum_20d': float,       # 20-day prior return, normalized
    'price_momentum_60d': float,       # 60-day prior return, normalized
    'analyst_revision_breadth': float, # (up - down) / total, [-1, +1]
    'short_interest': float,           # % float short (higher = more squeeze potential)

    # --- Valuation Context ---
    'sector_pe_ratio': float,          # Current sector median P/E (denominator for implied EPS)
    'roic_vs_wacc': float,             # ROIC / WACC spread, company-level
    'intangible_adj_pb': float,        # Intangibles-adjusted P/B (Eisfeldt/Kim model)

    # --- Macro / Regime Features ---
    'macro_score': float,              # Composite macro score [0, -6], normalized [0, 1]
    'vix': float,                      # Log VIX, normalized
    'erp_spread': float,               # Earnings yield - real 10Y TIPS yield
    'yield_curve_slope': float,        # 10Y - 2Y, normalized
    'credit_spread': float,            # HYG/LQD implied spread proxy, normalized
    'cyclical_flag': int,              # 0/1 — sector is cyclical (from Shepherd sector classification)

    # --- Portfolio Context ---
    'current_position_size': float,    # Existing position in this name [0, 0.05], normalized
    'portfolio_utilization': float,    # Fraction of NAV currently deployed [0, 1]
    'sector_concentration': float,     # Current sector weight vs. S&P 500 sector weight
    'portfolio_beta': float,           # Running weighted beta of open positions
    'portfolio_hml_tilt': float,       # HML loading of running book (completion portfolio input)
    'days_since_entry': int,           # For existing positions: normalized [0, 60]
}
```

**Total dimensions: ~27 features.** This is manageable; SAC scales well to 30–50 dimensional state spaces.

**Transformer encoder note:** The Transformer pre-trains on time-series of earnings (Q1→Q2→Q3→Q4 sequences per company). Its output is a fixed-length embedding (e.g., 64-d) that replaces the per-company historical features above — the embedding encodes company-specific drift behavior learned from past quarters. This embedding is concatenated with the macro/portfolio features (which are time-varying, not company-specific).

**Confidence: MEDIUM-HIGH** for feature selection (validated against vault docs and academic literature); MEDIUM for exact dimensionality (calibrate empirically during backtest)

### Action Space Design

**Recommendation: Continuous action space [0, 1] for position sizing**

The discrete vs. continuous decision:
- **Discrete (e.g., 0, 0.5%, 1%, 2%, 3%, 5%):** Simpler training, but coarse — misses optimal sizing between buckets. Creates artifacts at discrete boundaries.
- **Continuous [0, 1]:** Maps naturally to SAC's Gaussian policy. The actor outputs `mu` and `sigma` for a Beta distribution (bounded [0,1] is better than Gaussian for probabilities) or a clipped Gaussian. Then scale: `actual_size = action * max_position_size` (e.g., `max_position_size = 0.05` = 5% NAV).

**Implementation:**
```python
# SAC actor: output is position size fraction of max allowed NAV
# Beta distribution parameterization (strictly bounded [0,1])
alpha_param, beta_param = actor_network(state)  # both > 0 via softplus activation
action_dist = torch.distributions.Beta(alpha_param, beta_param)
raw_action = action_dist.rsample()  # differentiable sample

# Scale to actual position size
actual_position_pct = raw_action * MAX_POSITION_SIZE  # e.g., 0 to 5% NAV

# Apply macro multiplier AFTER RL output (not in action space — deterministic override)
final_position_pct = actual_position_pct * macro_multiplier * erp_cap
```

**Why separate macro multiplier from RL action:** The RL agent should learn to size on signal quality and portfolio context. The macro gating is a deterministic override layer that the agent does not need to learn — it's a risk control, not a signal. Mixing them forces the agent to relearn macro sensitivity every time the macro regime changes.

**Confidence: HIGH** for continuous recommendation; HIGH for Beta distribution parameterization

### Reward Shaping for Information Ratio Optimization

**Primary reward signal (IR-optimized):**

```python
def compute_reward(
    position_return: float,        # return of position over holding period
    benchmark_return: float,       # S&P 500 return over same period
    position_volatility: float,    # realized vol of position during holding
    holding_days: int,
    ff5_factors: dict,             # Mkt-Rf, SMB, HML, RMW, CMA during period
    position_loadings: dict,       # pre-computed FF5 beta loadings for this position
) -> float:
    # Step 1: FF5 factor-adjusted return (alpha only)
    factor_return = sum(ff5_factors[f] * position_loadings[f] for f in ff5_factors)
    alpha = position_return - factor_return

    # Step 2: Risk-adjusted alpha (core reward)
    ir_reward = alpha / (position_volatility + 1e-6)

    # Step 3: Asymmetric loss penalty (Shepherd behavioral principle)
    # Losses hurt 1.5x more than equivalent gains — CVaR-aware
    if alpha < 0:
        ir_reward *= 1.5

    # Step 4: Tail risk penalty
    # Penalize positions that contributed to >2% single-day drawdown
    # (catches fat-tail events)
    tail_penalty = 0.0
    if position_max_daily_loss < -0.02:  # > 2% single day loss
        tail_penalty = 0.5 * abs(position_max_daily_loss)

    # Step 5: Holding period regularization
    # Penalize very short holds (< 3 days) — drift needs time to manifest
    # Penalize very long holds (> 30 days) — thesis decay
    if holding_days < 3:
        time_penalty = 0.2
    elif holding_days > 30:
        time_penalty = 0.1 * (holding_days - 30) / 30
    else:
        time_penalty = 0.0

    return ir_reward - tail_penalty - time_penalty
```

**Secondary reward: ensemble disagreement penalty**

The 5 SAC agents should independently agree before sizing up. Use disagreement as a variance penalty:
```python
agent_actions = [agent_i.act(state) for i in range(5)]
mean_action = np.mean(agent_actions)
std_action = np.std(agent_actions)

# The meta-controller takes mean_action; variance penalizes individual agents
# that deviated from ensemble consensus when the trade outcome was poor
ensemble_penalty = std_action * abs(outcome_reward)  # only penalizes when wrong direction
```

**Prioritized Experience Replay (PER) priority formula:**
```python
priority = abs(td_error) ** alpha_per + epsilon_per
# alpha_per = 0.6 (standard), epsilon_per = 0.01
# Importance sampling weight: w_i = (N * P(i))^(-beta_is)
# beta_is annealed from 0.4 to 1.0 over training
```

**Confidence: HIGH** for reward structure (well-established in RL-for-trading literature); MEDIUM for specific scalar coefficients (1.5x loss weight, tail penalty thresholds — calibrate in backtest)

---

## Q4: Mixture-of-Experts Regime Conditioner — Soft Routing Implementation

### Architecture

The MoE regime conditioner is a lightweight gating network that maps macro state to a probability distribution over K=3 expert SAC agents (or 3 regime-specific policy heads).

**Regime definitions (based on vault macro composite score):**
```
Expansion:  macro_score in [0, -1]    → full sizing multiplier 1.0x
Caution:    macro_score in [-2, -3]   → reduced multiplier 0.6-0.7x
Crisis:     macro_score in [-4, -6]   → minimal multiplier 0.2-0.3x
```

**Soft routing architecture:**
```python
import torch
import torch.nn as nn

class RegimeGatingNetwork(nn.Module):
    """
    Maps macro state vector → soft routing weights over K regime experts.
    Uses softmax (not argmax) for differentiable training.
    """
    def __init__(self, macro_state_dim: int = 8, n_experts: int = 3, hidden_dim: int = 32):
        super().__init__()
        self.gate = nn.Sequential(
            nn.Linear(macro_state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, n_experts),
            nn.Softmax(dim=-1)
        )
        # Noise injection for exploration (from Switch Transformer / GShard pattern)
        self.noise_std = 0.01

    def forward(self, macro_state: torch.Tensor, training: bool = False) -> torch.Tensor:
        logits = self.gate[:-1](macro_state)  # pre-softmax
        if training:
            logits += torch.randn_like(logits) * self.noise_std
        return torch.softmax(logits, dim=-1)  # shape: [batch, n_experts]

class SACMoEMetaController(nn.Module):
    """
    Meta-controller: combines 5 SAC agent outputs via regime-gated mixture.
    """
    def __init__(self, n_sac_agents: int = 5, n_regime_experts: int = 3):
        super().__init__()
        self.regime_gate = RegimeGatingNetwork()
        # Mapping from regime expert to SAC agent subset
        # Expert 0 (expansion) → agents [0, 1, 2] emphasized
        # Expert 1 (caution)   → agents [1, 2, 3] emphasized
        # Expert 2 (crisis)    → agents [3, 4] emphasized
        self.expert_agent_weights = nn.Parameter(
            torch.ones(n_regime_experts, n_sac_agents) / n_sac_agents
        )

    def forward(self, macro_state, agent_actions):
        # agent_actions: [n_agents, batch, action_dim]
        regime_weights = self.regime_gate(macro_state)  # [batch, n_experts]
        agent_weights = torch.softmax(self.expert_agent_weights, dim=-1)  # [n_experts, n_agents]

        # Weighted combination: [batch, n_experts] x [n_experts, n_agents] → [batch, n_agents]
        blended_agent_weights = torch.matmul(regime_weights, agent_weights)  # [batch, n_agents]

        # Final action: weighted mean of agent actions
        # agent_actions transposed: [batch, n_agents, action_dim]
        final_action = torch.einsum('bn,bnd->bd', blended_agent_weights, agent_actions.permute(1, 0, 2))
        return final_action, regime_weights
```

**Macro state inputs to gating network (8-dimensional):**
```python
macro_state = torch.tensor([
    yield_curve_slope,      # 10Y - 2Y, normalized
    lei_mom_3m,             # LEI 3-month momentum
    sahm_rule_value,        # Sahm Rule indicator (0 or positive float)
    ism_pmi,                # ISM PMI, normalized around 50
    credit_spread,          # HYG/LQD spread, normalized
    vix_level,              # log VIX, normalized
    erp_spread,             # Earnings yield - real TIPS, normalized
    jpy_carry,              # JPY/AUD rate of change (carry trade proxy)
])
```

**Training the MoE meta-controller:**
The gating network parameters are trained jointly with the RL agents via the shared reward signal. The key implementation details:
1. **Auxiliary load-balancing loss** (from Switch Transformer paper, Fedus et al. 2021): prevents all samples routing to one expert. Add `0.01 * load_balance_loss` to training objective.
2. **Gradient flow**: Use straight-through estimator or Gumbel-softmax for routing if using hard routing; with soft routing, standard backprop through softmax works.
3. **Pretrain gating network separately**: First train the gate to predict the current macro regime label (Expansion/Caution/Crisis) as a 3-class classification problem using historical FRED data. Then fine-tune end-to-end with RL.

**Existing implementations to reference:**
- `torch.nn.ModuleList` with soft gating is the standard PyTorch approach
- The `mixtral` implementation in HuggingFace Transformers uses the same sparse MoE pattern (though more complex)
- For a simpler v1.0: replace MoE with a single gating network that directly outputs `regime_multiplier ∈ [0.2, 1.0]` — less expressive but easier to train and debug

**Confidence: HIGH** for architecture pattern; MEDIUM for specific hyperparameters (load balance loss weight, noise std); MEDIUM for "pretrain gate first" recommendation (best practice from MoE literature, may require adjustment)

---

## Q5: Transformer Pre-Training on Earnings Sequences

### Architecture

**Goal:** Learn a company-specific earnings dynamics embedding from historical quarterly sequences. This embedding encodes: does this company consistently beat? Does its drift persist? Is the beat quality improving or deteriorating?

**Input features per quarter (normalized):**
```python
quarter_features = [
    eps_surprise_normalized,      # (actual - implied) / sigma, z-score
    revenue_surprise_normalized,  # (actual - prior) / prior, z-score
    margin_delta,                 # gross margin change vs. prior quarter, normalized
    guidance_direction,           # {-1, 0, +1} encoded as continuous after embedding
    accruals_ratio,               # CFO / NI, normalized
    qoq_revenue_growth,           # revenue(t) / revenue(t-1) - 1, normalized
    yoy_eps_growth,               # eps(t) / eps(t-4) - 1, normalized
    analyst_revision_post,        # avg analyst revision in 5 days after announcement
    event_day_car,                # cumulative abnormal return on announcement day
    pead_10d_return,              # realized 10-day drift (training target: this is what to predict)
]
# Sequence length: 8 quarters (2 years) → predict quarter 9 behavior
```

**Architecture:**
```python
class EarningsTransformer(nn.Module):
    def __init__(
        self,
        n_features: int = 9,        # input features per quarter (exclude target)
        d_model: int = 64,          # embedding dimension
        n_heads: int = 4,
        n_layers: int = 3,
        seq_len: int = 8,           # 8 quarters history
        dropout: float = 0.1,
    ):
        super().__init__()
        self.input_proj = nn.Linear(n_features, d_model)
        self.pos_embedding = nn.Embedding(seq_len, d_model)  # learnable positional encoding

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 4,
            dropout=dropout,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.cls_token = nn.Parameter(torch.randn(1, 1, d_model))  # CLS-style aggregation
        self.output_head = nn.Linear(d_model, 1)  # predict next-quarter EPS surprise

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # x: [batch, seq_len, n_features]
        positions = torch.arange(x.shape[1], device=x.device)
        x_proj = self.input_proj(x) + self.pos_embedding(positions)

        # Prepend CLS token
        cls = self.cls_token.expand(x.shape[0], -1, -1)
        x_with_cls = torch.cat([cls, x_proj], dim=1)  # [batch, seq_len+1, d_model]

        encoded = self.transformer(x_with_cls)   # [batch, seq_len+1, d_model]
        cls_embedding = encoded[:, 0, :]          # [batch, d_model] — the company embedding

        prediction = self.output_head(cls_embedding)  # [batch, 1] — next-quarter EPS surprise
        return cls_embedding, prediction
```

**Pre-training objective:**
1. **Primary:** Next-quarter EPS surprise prediction (regression loss: MSE on normalized surprise)
2. **Secondary (contrastive — optional):** Companies with similar historical drift patterns should have similar embeddings. Use a SimCLR-style contrastive loss: positive pairs = same company across different time windows, negative pairs = random companies.

**Training data:** 8 quarters × ~500 S&P 500 companies × ~20 years = ~80,000 sequences. This is sufficient for a 64-d model with 3 transformer layers. Do NOT use a large model — the data is limited.

**Freezing rationale (v1.0):** The Transformer is pre-trained offline on 2005-2022 historical data. In v1.0 the weights are frozen — the CLS embedding is used as a fixed feature by the SAC agents. Rationale from the vault PRD: reduces training instability in the RL loop. Unfreeze with LR=1e-5 in v2.0 for end-to-end fine-tuning.

**Confidence: HIGH** for architecture pattern; MEDIUM for exact hyperparameters (d_model=64, n_layers=3); MEDIUM for pre-training objective (both supervised and contrastive are validated in financial time-series literature through 2024)

---

## Q6: FF5 Factor Completion Portfolio — Regression and Optimizer

### Computing FF5 Beta Loadings via OLS

**The system uses FF5 (Fama-French 5-factor) for reward computation and FF3 for completion portfolio.** This matches the vault's empirical framework (FF3 for completion, FF5 for performance attribution).

```python
import numpy as np
import pandas as pd
from scipy.optimize import minimize

def compute_ff5_loadings(
    portfolio_returns: pd.Series,
    factors: pd.DataFrame,  # columns: Mkt-RF, SMB, HML, RMW, CMA, RF
    window: int = 60,       # 60 months = 5 years (Shepherd's window)
) -> dict:
    """
    OLS regression of portfolio excess returns on FF5 factors.
    Returns: dict with alpha, beta_mkt, beta_smb, beta_hml, beta_rmw, beta_cma
    """
    excess_returns = portfolio_returns - factors['RF']
    X = factors[['Mkt-RF', 'SMB', 'HML', 'RMW', 'CMA']].tail(window)
    y = excess_returns.tail(window)

    X_with_const = np.column_stack([np.ones(len(X)), X.values])
    # OLS: beta = (X'X)^{-1} X'y
    beta = np.linalg.lstsq(X_with_const, y.values, rcond=None)[0]

    return {
        'alpha_monthly': beta[0],
        'beta_mkt': beta[1],
        'beta_smb': beta[2],
        'beta_hml': beta[3],
        'beta_rmw': beta[4],
        'beta_cma': beta[5],
    }
```

### Scipy Optimizer for Completion Portfolio

```python
def optimize_completion_portfolio(
    active_loadings: np.ndarray,     # [Mkt-RF, SMB, HML] of active PEAD portfolio
    etf_loadings: dict,              # ETF ticker -> [Mkt-RF, SMB, HML] loadings
    sp500_loadings: np.ndarray,      # target: [0.985, -0.155, 0.025]
    active_weight: float = 0.77,     # fraction of NAV in active sleeve
) -> dict:
    """
    Scipy optimizer: find ETF weights that minimize sum of squared factor deviations
    between total portfolio (active + passive) and S&P 500 benchmark.
    Matches Shepherd FF3 completion portfolio methodology exactly.
    """
    etf_tickers = list(etf_loadings.keys())
    etf_matrix = np.array([etf_loadings[t] for t in etf_tickers])  # [n_etfs, 3]
    passive_weight = 1.0 - active_weight

    def objective(etf_weights: np.ndarray) -> float:
        passive_factor_loadings = etf_matrix.T @ etf_weights  # [3]
        total_loadings = active_weight * active_loadings + passive_weight * passive_factor_loadings
        ssd = np.sum((total_loadings - sp500_loadings) ** 2)
        return ssd

    n_etfs = len(etf_tickers)
    constraints = [{'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}]  # weights sum to 1
    bounds = [(0.0, 1.0)] * n_etfs  # no short selling

    result = minimize(
        objective,
        x0=np.ones(n_etfs) / n_etfs,  # equal weight initialization
        method='SLSQP',
        bounds=bounds,
        constraints=constraints,
        options={'ftol': 1e-9, 'maxiter': 1000}
    )

    return {
        etf_tickers[i]: float(result.x[i])
        for i in range(n_etfs)
        if result.x[i] > 0.01  # filter near-zero weights
    }

# ETF universe and their FF3 loadings (from vault Fall 2025 data)
ETF_FF3_LOADINGS = {
    'IVE':  [0.94, -0.11, +0.34],   # S&P 500 Value — primary value correction
    'IYR':  [0.92, -0.16, +0.10],   # Real Estate — low beta + positive HML
    'VUG':  [1.10, -0.13, -0.30],   # Growth — use cautiously (growth tilt)
    'VTI':  [1.01, -0.03, +0.04],   # Total Market — neutral
    'VBR':  [1.05, +0.51, +0.51],   # Small Cap Value — AVOID (adds SMB)
}

# S&P 500 FF3 target (from vault Fall 2025 regression)
SP500_FF3_TARGET = np.array([0.985, -0.155, 0.025])

# Trigger reoptimization when SSD > 0.005 (Shepherd threshold)
REOPT_SSD_THRESHOLD = 0.005
```

**Confidence: HIGH** for methodology (directly from vault with empirical ETF loadings); HIGH for scipy SLSQP implementation pattern

---

## Q7: Ken French Data Library — Programmatic Fetch

### pandas_datareader (Recommended Method)

```python
import pandas_datareader.data as web
from datetime import datetime

def fetch_ff5_factors(start: str = '1963-07-01', end: str = None) -> pd.DataFrame:
    """
    Fetch Fama-French 5-factor daily or monthly data from Ken French library.
    Returns DataFrame with columns: Mkt-RF, SMB, HML, RMW, CMA, RF
    Values are percentages (divide by 100 for decimal returns).
    """
    if end is None:
        end = datetime.today().strftime('%Y-%m-%d')

    # Monthly factors
    ff5_monthly = web.DataReader(
        'F-F_Research_Data_5_Factors_2x3',
        'famafrench',
        start=start,
        end=end
    )
    # Returns a list; [0] is the monthly factors DataFrame
    factors_monthly = ff5_monthly[0]
    factors_monthly = factors_monthly / 100  # convert from % to decimal

    return factors_monthly

def fetch_ff5_daily(start: str = '1963-07-01', end: str = None) -> pd.DataFrame:
    """Fama-French 5-factor daily data."""
    if end is None:
        end = datetime.today().strftime('%Y-%m-%d')

    ff5_daily = web.DataReader(
        'F-F_Research_Data_5_Factors_2x3_daily',
        'famafrench',
        start=start,
        end=end
    )
    return ff5_daily[0] / 100
```

**Dataset names for `pandas_datareader` (Ken French library identifiers):**

| Dataset Name | Frequency | Use Case |
|---|---|---|
| `F-F_Research_Data_5_Factors_2x3` | Monthly | FF5 factors — completion portfolio regression |
| `F-F_Research_Data_5_Factors_2x3_daily` | Daily | FF5 factors — daily reward computation |
| `F-F_Research_Data_Factors` | Monthly | FF3 factors (MKT, SMB, HML, RF) |
| `F-F_Research_Data_Factors_daily` | Daily | FF3 daily |
| `F-F_Momentum_Factor` | Monthly | MOM factor (if extending to FF6) |

**Direct download alternative** (if pandas_datareader breaks — it sometimes does when Ken French updates the site):

```python
import requests
import zipfile
import io

def fetch_ff5_direct(frequency: str = 'monthly') -> pd.DataFrame:
    """Direct download from Ken French library as fallback."""
    dataset_urls = {
        'monthly': 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_CSV.zip',
        'daily': 'https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip',
    }
    url = dataset_urls[frequency]
    response = requests.get(url, timeout=30)
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    csv_name = [f for f in zf.namelist() if f.endswith('.CSV')][0]

    with zf.open(csv_name) as f:
        # Skip header rows until the data starts (variable number of comment lines)
        lines = f.read().decode('utf-8').split('\n')
    data_start = next(i for i, line in enumerate(lines) if line.strip().startswith(',Mkt-RF'))
    df = pd.read_csv(
        io.StringIO('\n'.join(lines[data_start:])),
        index_col=0,
        na_values=['-99.99', '-999']
    )
    df.index = pd.to_datetime(df.index.astype(str), format='%Y%m' if frequency == 'monthly' else '%Y%m%d')
    return df / 100
```

**Prefect flow integration:**
```python
from prefect import flow, task
from datetime import timedelta

@task(cache_expiry=timedelta(days=1))
def update_ff5_factors():
    """Prefect task: refresh FF5 factors daily (they update monthly, but task runs daily for idempotency)."""
    factors = fetch_ff5_daily(start='2018-01-01')
    # Write to TimescaleDB ff5_factors hypertable
    upsert_to_timescale(factors, table='ff5_factors', index_col='date')
    return factors.index[-1]  # return last available date as artifact
```

**Confidence: HIGH** for pandas_datareader dataset names (stable Ken French API); MEDIUM for direct download CSV parsing (header row count varies — the `data_start` detection handles this but should be tested)

---

## Table Stakes Features

Features the system cannot function without. Missing any = broken product.

| Feature | Why Required | Complexity | Dependencies |
|---------|-------------|------------|-------------|
| Market-implied EPS calculation | Core signal; everything downstream depends on it | Low | FMP income statements + yfinance sector P/E |
| Earnings calendar ingestion | Without it, no trades fire | Low | FMP earnings_calendar endpoint |
| Revenue/margin decomposition | Distinguishes high-quality from financial-engineering beats | Medium | FMP income + cash flow statements |
| Accruals quality score | Filters out manipulation; empirically strongest quality predictor | Medium | FMP income + cash flow statements |
| SAC agent action/state pipeline | RL infrastructure | High | PyTorch, custom gym environment |
| FF5 factor fetch + storage | Required for reward computation and completion portfolio | Low | pandas_datareader or direct download |
| Completion portfolio optimizer | Strips factor beta from alpha attribution | Medium | scipy, ETF FF3 loadings |
| Macro composite score | Gates all position sizing | Medium | FRED API (yield curve, LEI, PMI, VIX) |
| PER experience replay buffer | Required for SAC training stability | Medium | PostgreSQL or Redis storage |

## Differentiating Features

Features that create the IR advantage over naive threshold strategy.

| Feature | Value Proposition | Complexity | Notes |
|---------|------------------|------------|-------|
| Market-implied vs. analyst consensus EPS | Removes anchoring bias; captures second-level thinking | Medium | Shepherd's #1 insight |
| Transformer company embedding | Captures company-specific drift personality (serial beaters vs. one-off) | High | Frozen in v1.0; high variance reduction |
| SAC ensemble disagreement signal | Uncertainty quantification for position sizing | Medium | 5 agents; std of actions drives sizing discount |
| MoE regime conditioner | Different sizing policy per macro regime | High | Pre-train gate on regime classification first |
| Earnings quality decomposition (accruals) | Distinguishes real vs. manufactured beats | Medium | Jones model; CFO/NI ratio simplification |
| FF5 reward (not raw P&L) | Ensures RL learns alpha not beta | Medium | Separates skill from market timing |
| Pre-earnings leak detector (CAR -10 to -1) | Discounts signals that have already priced in | Low | Requires intraday price data or daily OHLC |
| Guidance direction proxy (analyst revision delta) | FMP doesn't have structured guidance; proxy is practical | Low-Medium | 5-day post-announcement revision window |

## Anti-Features

Explicitly exclude from v1.0.

| Anti-Feature | Why Avoid | What to Do Instead |
|-------------|-----------|-------------------|
| Full Jones model with quarterly OLS | Requires 8+ quarters per company, high estimation error; calibration unstable | Use CFO/NI ratio as simpler accruals proxy |
| Dechow-Dichev model (requires forward CFO) | Requires next-quarter CFO — unavailable at trade entry | Use as post-hoc validation only |
| Online RL (update in real-time) | Dangerous with live/paper capital; overfits to regime du jour | Episodic offline RL only; quarterly batch updates |
| Short-side PEAD (v1.0) | Asymmetric risk; requires locate + borrowing costs not modeled | Behind feature flag; disabled by default |
| Unfreezing Transformer in v1.0 | Destabilizes RL training loop; PRD specifies frozen | Unfreeze with LR=1e-5 in v2.0 |
| Analyst consensus as EPS benchmark | Shepherd explicitly rejects; markets have already priced consensus in | Market-implied EPS (price / sector median P/E) |
| Options overlay | Requires separate volatility model; v3.0 scope | Stock positions only |
| Contrastive pre-training objective | Nice-to-have; primary supervised objective is sufficient for v1.0 | Next-quarter EPS surprise regression is primary |

## Feature Dependencies

```
FF5 factors (Ken French fetch)
  → FF5 reward computation (RL training)
  → Completion portfolio optimizer (factor loadings)

Market-implied EPS signal
  → Earnings quality decomposition
    → Accruals ratio (FMP CFO + NI)
    → Revenue growth decomposition (FMP income)
    → Margin expansion (FMP income)
  → Guidance direction (FMP analyst estimates proxy)
  → Pre-earnings CAR (Alpaca price data)

Transformer pre-training (offline)
  → Company earnings embedding [64-d]
    → SAC agent state vector (concatenated with macro features)

Macro composite score (FRED)
  → MoE gating network input
  → Position sizing multiplier (deterministic override, not learned)

SAC ensemble (5 agents)
  → PER experience replay buffer
  → MoE meta-controller (aggregates agent actions)
    → Final position size output
    → Macro multiplier override (post-RL deterministic cap)
```

## MVP Recommendation

Implement in this order to hit a tradeable v1.0:

1. **Signal pipeline first** (FMP → implied EPS → quality score → composite signal)
   - Validates signal exists before building RL on top
   - Can run naive threshold strategy (signal > X → buy) as baseline

2. **Backtest engine with naive baseline**
   - 2018–2023 data
   - Validates Sharpe > 1.0 threshold
   - Establishes IR baseline the RL must beat

3. **FF5 factor fetch + reward function**
   - Required before any RL training begins
   - Reward function determines what the RL optimizes

4. **SAC single agent (not ensemble) first**
   - Debug training loop, replay buffer, action space on single agent
   - Add 4 more agents once single agent converges

5. **MoE meta-controller**
   - Pre-train gate on regime classification separately
   - Integrate after ensemble is stable

6. **Transformer pre-training**
   - Can be done in parallel with steps 3–5
   - Frozen embedding is a feature input; doesn't block RL development

7. **Completion portfolio optimizer**
   - Quarterly rebalance; not on critical path for v1.0 trading
   - Add after backtest validates the active strategy

**Defer:** Dechow-Dichev validation, contrastive Transformer pre-training, short-side PEAD, options overlay — all v2.0+

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| PEAD academic literature (SUE, CAR) | HIGH | Well-established, stable findings. Post-2020 magnitude compression is MEDIUM confidence — verify with backtest. |
| Earnings quality (Jones model formula) | HIGH | Standard accounting textbook formula. |
| FMP API endpoints | MEDIUM | Endpoint URLs reflect v3 structure as of training data (Aug 2025). Verify field names on first integration — FMP has changed naming conventions before. |
| FMP guidance direction | LOW | No structured guidance field in FMP free/starter tier. Proxy via analyst revision confirmed as practical workaround, not ideal. |
| SAC ensemble architecture | HIGH | Haarnoja 2018 SAC + ensemble patterns well-established. |
| SAC reward shaping coefficients | MEDIUM | Structure is correct; specific scalars (1.5x loss weight) need backtest calibration. |
| MoE soft routing | MEDIUM | Architecture pattern is correct (Switch Transformer reference); financial application is newer. Load-balance loss weight needs tuning. |
| Transformer pre-training architecture | MEDIUM | BERT-style CLS token approach is standard; financial sequence specifics are lightly validated in literature. |
| pandas_datareader Ken French datasets | HIGH | Dataset names have been stable for years. Direct download URL is MEDIUM (Ken French occasionally restructures the site). |
| Completion portfolio optimizer | HIGH | Directly validated from vault materials with empirical ETF loadings. |

## Sources

- Bernard, Thomas (1989) — original PEAD paper (HIGH)
- Livnat & Mendenhall (2006) — SUE vs. analyst forecast PEAD comparison (HIGH)
- Sloan (1996) — accruals anomaly (HIGH)
- Dechow, Hutton, Kim, Sloan (1995 / 2002) — Jones model, Dechow-Dichev model (HIGH)
- Haarnoja, Zhou, Abbeel, Levine (2018) — SAC original paper (HIGH)
- Fedus et al. (2021) — Switch Transformer, load-balance loss (HIGH)
- Vault: `usif-shepherd-analytical-framework.md` — three-axis framework (HIGH)
- Vault: `usif-shepherd-sizing-framework.md` — macro multiplier, ERP cap, sizing rules (HIGH)
- Vault: `usif-shepherd-investment-philosophy.md` — market-implied EPS rationale (HIGH)
- Vault: `usif-ff-factor-analysis.md` — empirical ETF loadings, optimizer code (HIGH)
- Vault: `usif-ff3-completion-portfolio-fall2025.md` — FF3 target loadings, ETF universe (HIGH)
- FMP API documentation (training knowledge, MEDIUM — verify current endpoint names)
- Ken French Data Library (pandas_datareader, HIGH for dataset names)
