# Phase 5: SAC Ensemble RL - Research

**Researched:** 2026-05-04
**Domain:** Deep RL (SAC ensemble, PER, MoE, Transformer encoder) + PostgreSQL checkpoint storage
**Confidence:** HIGH — all major components already exist in `rl/` and are verified against the codebase

---

## Summary

Phase 5 is primarily an **integration and repair phase**, not a greenfield build. The core RL components (`rl/sac_agent.py`, `rl/per_buffer.py`, `rl/moe_controller.py`, `rl/transformer_encoder.py`, `rl/environment.py`, `rl/reward.py`) already exist and are substantially functional. However, the existing code diverges from the FR specifications in several critical ways that must be corrected:

1. **Actor distribution mismatch (FR-5.3):** The current `ContinuousActor` uses a Gaussian policy with sigmoid squash — not a Beta distribution. FR-5.3 mandates Beta distribution output for position size in [0,1]. This requires replacing the Gaussian head with `torch.distributions.Beta` and adjusting the entropy term accordingly.

2. **Ensemble initialization (FR-5.1):** Agents are created with identical architecture and no distinct seeds or hyperparameter perturbations. FR-5.1 requires each of the 5 agents to have distinct random seeds (PyTorch/NumPy) and ±30% perturbations on `lr`, `gamma`, and `tau`.

3. **MoE architecture mismatch (FR-5.5):** The existing `MoEController` blends outputs from 3 regime-specialist agents (one per regime). FR-5.5 requires a weighted blend of **all 5 SAC agents** (not 3 specialists), with the regime-classified weights as the blending mechanism. The existing 3-specialist design is a different architecture.

4. **Transformer layer count discrepancy (FR-5.4):** FR says 3 layers; `TransformerStateEncoder.__init__` defaults to `n_layers=4`. `SACConfig` also sets `transformer_layers=4`. Must be corrected to 3 in both `config.py` (SACConfig) and the encoder default.

5. **DB-backed PER (FR-5.2):** The existing `PERBuffer` is entirely in-memory (SumTree). FR-5.2 requires transitions to be stored in and sampled from the PostgreSQL `rl_transitions` hypertable. The in-memory buffer can serve as the sampling index structure, but push/persist must write to DB, and sampling must hydrate from DB.

6. **Diversity monitoring (FR-5.6):** No diversity monitoring exists. Must add pairwise cosine similarity computation between agent Beta distribution parameters after each training epoch, with `rl_diversity_alert` event firing when similarity > 0.9.

7. **DB checkpoint storage (FR-5.7):** The existing `rl_tasks.py` writes checkpoints to `rl_checkpoints` table, but this table does not exist in any Alembic migration (0001–0003). A new migration is required. Also, checkpoints must be written every 1,000 training steps, not just at task completion.

8. **Training loop entry point:** `docker-compose.yml` references `python -m flows.rl_trainer` but `worker/flows/rl_trainer.py` does not exist. This module must be created.

**Primary recommendation:** Correct the five architectural divergences (Beta dist, distinct seeds, MoE blend of all 5 agents, 3-layer transformer, DB-backed PER), add diversity monitoring, create the missing migration and training loop, then wire into the existing Celery + Railway manual-deploy infrastructure.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FR-5.1 | 5 SAC agents initialize with distinct random seeds and ±30% hyperparameter perturbations; no two agents share identical network weights | Requires seeded `torch.manual_seed(seed_i)` + `np.random.seed(seed_i)` per agent at init; perturb `lr`, `gamma`, `tau` from `SACConfig` base |
| FR-5.2 | Experience replay transitions stored in and sampled from PostgreSQL `rl_transitions` hypertable; prioritized sampling returns higher-priority transitions more frequently | `rl_transitions` hypertable exists with `priority`, `agent_id`, `state_vec` (JSONB); need DB-backed push + SumTree-indexed sampling |
| FR-5.3 | Each agent outputs continuous position size in [0,1] via Beta distribution; macro multiplier applied post-RL as deterministic override, does not backpropagate | Replace `ContinuousActor` Gaussian head with `torch.distributions.Beta`; apply `apply_sizing_multiplier()` after SAC select_action, not inside backward pass |
| FR-5.4 | Transformer encoder (d_model=64, 3 layers, 4 heads, 8-quarter input) pre-trained on next-quarter EPS surprise regression; loads frozen weights in v1.0 | Fix `n_layers` from 4 to 3 in `SACConfig.transformer_layers` and `TransformerStateEncoder` default; pre-training script reads 8 quarters of `earnings_events` |
| FR-5.5 | MoE meta-controller classifies macro state into 3 regimes and produces a weighted blend of the 5 agent outputs | Redesign `MoEController.blend()` to accept outputs from all 5 `SACAgent` instances (not 3 specialists) and apply softmax regime weights |
| FR-5.6 | Pairwise cosine similarity between agent action distributions computed after each training epoch; similarity > 0.9 triggers `rl_diversity_alert` event | `torch.nn.functional.cosine_similarity` on stacked Beta parameters; fire alert via existing `dispatch_alert` Celery task |
| FR-5.7 | RL trainer Railway service requires manual deploy; checkpoints written to PostgreSQL every 1,000 training steps | `deployTrigger = "manual"` already in `railway.toml`; need Alembic migration for `rl_checkpoints` table + checkpoint loop every 1k steps |
| FR-5.8 | (not listed in ROADMAP — likely same as FR-5.7 or covers online vs offline training separation) | Verify against REQUIREMENTS.md |
| FR-5.9 | (not listed in ROADMAP — likely Integration with portfolio pipeline) | Verify against REQUIREMENTS.md |
</phase_requirements>

---

## Standard Stack

### Core (already in repo)
| Library | Version | Purpose | Source |
|---------|---------|---------|--------|
| torch | 2.11.0 | SAC networks, Beta distribution, gradient updates | [VERIFIED: local `python3 -c "import torch; print(torch.__version__)"`] |
| numpy | 2.1.3 | Array ops, SumTree, IS weights | [VERIFIED: local] |
| gymnasium | 1.2.3 | `PEADTradingEnv` base class, env checker | [VERIFIED: local] |
| psycopg2-binary | 2.9.10 | Sync DB writes from training loop | [VERIFIED: local] |
| sqlalchemy | 2.0.49 | ORM models (`RlTransition`) | [VERIFIED: backend/requirements.txt] |
| loguru | in root requirements | Structured logging in trainer | [VERIFIED: requirements.txt] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| torch.distributions.Beta | (built-in to torch 2.11) | Beta dist actor; entropy for SAC alpha update | FR-5.3 actor replacement |
| torch.nn.functional.cosine_similarity | (built-in) | Pairwise diversity monitoring | FR-5.6 after each epoch |
| io.BytesIO + torch.save | (stdlib + torch) | Serialize model state_dict to bytes for DB storage | FR-5.7 checkpoint persistence |
| statsmodels | in root requirements | FF5 OLS recalibration in reward function | Already used in `rl/reward.py` |

### What NOT to Add
- **stable-baselines3:** Already imported in `rl/agent.py` (legacy PPO wrapper) but Phase 5 uses the custom `SACEnsemble` directly — do not route training through SB3.
- **Redis for PER:** Explicitly forbidden by project decision (see STATE.md). PostgreSQL only.
- **pickle for checkpoint storage:** Already used in `rl_tasks.py` for filesystem storage. For DB storage (FR-5.7), use `io.BytesIO` + `torch.save` → `psycopg2.Binary`.

### Installation
No new packages required. All dependencies already present in `requirements.txt` (root) and `backend/requirements.txt`.

---

## Architecture Patterns

### Recommended Project Structure (additions only)

```
rl/
├── sac_agent.py          ← MODIFY: Beta dist actor, distinct seeds, FR-5.1/5.3
├── moe_controller.py     ← MODIFY: blend all 5 agents, not 3 specialists (FR-5.5)
├── transformer_encoder.py← MODIFY: fix n_layers=3, add pre-training script (FR-5.4)
├── per_buffer.py         ← MODIFY: add DB-backed push/sample (FR-5.2)
├── diversity_monitor.py  ← CREATE: pairwise cosine sim, alert firing (FR-5.6)
└── trainer.py            ← CREATE: training loop, 1k-step checkpoint, entry point (FR-5.7)

worker/flows/
└── rl_trainer.py         ← CREATE: module entry point for `python -m flows.rl_trainer`

backend/alembic/versions/
└── 0004_rl_phase5_tables.py  ← CREATE: rl_checkpoints + rl_diversity_alerts tables
```

### Pattern 1: Beta Distribution Actor (FR-5.3)

**What:** Replace the Gaussian + sigmoid squash in `ContinuousActor` with a proper `torch.distributions.Beta` parameterized by `alpha, beta > 0`. Beta naturally produces samples in (0,1) without squashing.

**Why Beta over Gaussian+sigmoid:** The sigmoid-squash Gaussian has a correction term `-log(action*(1-action))` that introduces numerical instability near 0 and 1. Beta distribution has closed-form log-prob and entropy, satisfying the FR spec exactly.

**PyTorch pattern:**
```python
# Source: torch.distributions.Beta documentation [ASSUMED — standard PyTorch API]
import torch
from torch.distributions import Beta

class BetaActor(nn.Module):
    LOG_ALPHA_BETA_MIN = -5.0
    LOG_ALPHA_BETA_MAX = 2.0

    def __init__(self, obs_dim: int, hidden: list[int] = [256, 256]) -> None:
        super().__init__()
        self.net = _mlp(obs_dim, hidden[:-1], hidden[-1])
        self.alpha_head = nn.Linear(hidden[-1], 1)   # log alpha
        self.beta_head  = nn.Linear(hidden[-1], 1)   # log beta

    def forward(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        h = F.relu(self.net(obs))
        log_alpha = self.alpha_head(h).clamp(self.LOG_ALPHA_BETA_MIN, self.LOG_ALPHA_BETA_MAX)
        log_beta  = self.beta_head(h).clamp(self.LOG_ALPHA_BETA_MIN, self.LOG_ALPHA_BETA_MAX)
        return log_alpha.exp() + 1e-3, log_beta.exp() + 1e-3  # ensure > 0

    def sample(self, obs: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        alpha, beta = self(obs)
        dist = Beta(alpha, beta)
        action = dist.rsample()          # differentiable sample
        log_prob = dist.log_prob(action).sum(-1, keepdim=True)
        return action, log_prob

    def entropy(self, obs: torch.Tensor) -> torch.Tensor:
        alpha, beta = self(obs)
        return Beta(alpha, beta).entropy()
```

**Macro multiplier integration (FR-5.3):** Post-RL, not inside the backward pass:
```python
# In training loop / inference, AFTER select_action:
raw_size = ensemble.select_action(obs)           # from Beta dist
macro_score = load_macro_score_from_db(as_of)   # from macro_indicators
multiplier = apply_sizing_multiplier(macro_score) # from backend/app/portfolio/macro.py
final_size = float(raw_size * multiplier)        # deterministic override, no grad
```

### Pattern 2: Distinct Agent Initialization (FR-5.1)

**What:** Each of 5 agents gets a unique seed and ±30% perturbation of base hyperparameters.

**Pattern:**
```python
# Source: [ASSUMED — standard ensemble diversity technique]
import copy, dataclasses

BASE_SEEDS = [42, 137, 271, 314, 999]
PERTURB_KEYS = ["lr", "gamma", "tau"]
PERTURB_RANGE = 0.30

def _perturb_cfg(cfg: SACConfig, seed: int) -> SACConfig:
    rng = np.random.default_rng(seed)
    cfg_dict = dataclasses.asdict(cfg)
    for key in PERTURB_KEYS:
        factor = 1.0 + rng.uniform(-PERTURB_RANGE, PERTURB_RANGE)
        cfg_dict[key] = cfg_dict[key] * factor
    return SACConfig(**cfg_dict)

def make_ensemble(base_cfg: SACConfig, obs_dim: int, device: str) -> list[SACAgent]:
    agents = []
    for seed in BASE_SEEDS:
        torch.manual_seed(seed)
        np.random.seed(seed)
        agent_cfg = _perturb_cfg(base_cfg, seed)
        agents.append(SACAgent(obs_dim, agent_cfg, device))
    return agents
```

**Verification:** After init, assert `not torch.allclose(agents[0].cont_actor.net[0].weight, agents[1].cont_actor.net[0].weight)`.

### Pattern 3: MoE Blend of All 5 Agents (FR-5.5)

**What:** The MoE meta-controller takes raw actions from **all 5 SACAgents** and blends them using softmax regime weights. The existing 3-specialist design maps one agent to each regime — this is incompatible with FR-5.5.

**Correct architecture:**
```python
# MoEController.blend receives list of 5 (entry, hold) tuples from all agents
def blend(
    self,
    agent_outputs: list[tuple[float, int]],  # len=5, one per SACAgent
    macro_score: int,
    vix: float | None = None,
) -> MoEAction:
    rw = self.weights(macro_score, vix)  # regime weights [expansion, caution, crisis]
    # Reduce 3 regime weights to 5-agent weights via assignment
    # Agents 0-1 → expansion, agents 2-3 → caution, agent 4 → crisis
    agent_weights = self._regime_weights_to_agent_weights(rw)  # shape (5,), sums to 1
    entries = np.array([e for e, _ in agent_outputs])
    holds   = np.array([h for _, h in agent_outputs], dtype=float)
    blended_entry = float(np.dot(agent_weights, entries))
    blended_hold  = int(round(float(np.dot(agent_weights, holds))))
    return MoEAction(entry_size=blended_entry, hold_bin=blended_hold,
                     weights=rw, dominant_regime=rw.dominant())
```

The regime→agent weight mapping strategy is at Claude's discretion (soft assignment or one-hot then smooth). The simplest approach: uniform weights within each regime bucket, scaled by regime weight.

### Pattern 4: DB-Backed PER (FR-5.2)

**What:** The `rl_transitions` hypertable is already defined with `priority`, `state_vec` (JSONB), `action`, `reward`, `next_state_vec`, `done`, `agent_id`. The in-memory `PERBuffer` SumTree can continue to serve as the priority index for O(log n) sampling — but transitions must be **persisted to DB on push** and **hydrated from DB** into the SumTree on startup.

**Key insight:** The hypertable is the source of truth; the in-memory SumTree is a cache/index. Two modes:
1. **Online training:** transitions arrive in real time → write to DB immediately → add to SumTree
2. **Cold start:** training restarts → load recent N transitions from DB ordered by `priority DESC` → repopulate SumTree

**Sampling with DB priority:**
```python
# When SumTree is populated from DB, use stored priority as initial tree priority
# SELECT ts, episode_id, step, state_vec, action, reward, next_state_vec, done, priority
# FROM rl_transitions WHERE agent_id = :aid ORDER BY priority DESC LIMIT :n
```

**TimescaleDB-specific:** The `ix_rl_agent_priority` index on `(agent_id, priority DESC)` already exists (migration 0001). Use it. For sampling N transitions proportional to priority, pull the top-K by priority and apply IS weights in Python — approximates true priority sampling at PostgreSQL scale without a full SumTree in SQL.

### Pattern 5: Diversity Monitoring (FR-5.6)

**What:** After each training epoch, compute pairwise cosine similarity between the Beta distribution parameter vectors of each agent pair. If any pair exceeds 0.9, fire `rl_diversity_alert`.

**Pattern:**
```python
# Source: verified torch.nn.functional.cosine_similarity works in torch 2.11
import torch.nn.functional as F

def compute_pairwise_diversity(agents: list[SACAgent], sample_obs: torch.Tensor) -> float:
    """Returns max pairwise cosine similarity across all agent pairs."""
    param_vecs = []
    for agent in agents:
        alpha, beta = agent.cont_actor.forward_params(sample_obs)  # (batch, 1) each
        # Concatenate mean params across batch as representative vector
        vec = torch.cat([alpha.mean(0), beta.mean(0)])
        param_vecs.append(vec)

    max_sim = 0.0
    for i in range(len(param_vecs)):
        for j in range(i + 1, len(param_vecs)):
            sim = float(F.cosine_similarity(
                param_vecs[i].unsqueeze(0),
                param_vecs[j].unsqueeze(0)
            ))
            max_sim = max(max_sim, sim)
    return max_sim

# After each epoch:
max_sim = compute_pairwise_diversity(agents, canonical_obs_batch)
if max_sim > 0.9:
    dispatch_alert.delay(
        event_type="rl_diversity_alert",
        title="SAC Ensemble collapse detected",
        message=f"max_pairwise_cosine_sim={max_sim:.4f} > 0.9",
        priority="high",
    )
```

**The "canonical_obs_batch"** should be a fixed representative batch (e.g., 100 randomly sampled observations from the PER buffer) held constant across epochs for consistent comparison.

### Pattern 6: PostgreSQL Checkpoint Storage (FR-5.7)

**What:** Every 1,000 training steps, serialize each agent's `state_dict` to bytea and write to `rl_checkpoints`. 

**Schema needed (new migration):**
```sql
CREATE TABLE IF NOT EXISTS rl_checkpoints (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    step            INTEGER NOT NULL,
    agent_id        SMALLINT NOT NULL,         -- 0-4 for each SAC agent
    model_bytes     BYTEA,                     -- torch.save(state_dict, BytesIO)
    total_steps     INTEGER,
    mean_reward_20  NUMERIC(10,6),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rl_diversity_alerts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    max_similarity  NUMERIC(6,4) NOT NULL,
    agent_pair      TEXT,                      -- e.g. "0,3"
    epoch           INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**Serialization pattern (verified in this session):**
```python
import io, torch
buf = io.BytesIO()
torch.save(agent.cont_actor.state_dict(), buf)
model_bytes = buf.getvalue()   # bytes → psycopg2.Binary(model_bytes) for DB insert
```

**Loading:**
```python
buf = io.BytesIO(row['model_bytes'])
state_dict = torch.load(buf, map_location='cpu', weights_only=True)
agent.cont_actor.load_state_dict(state_dict)
```

### Pattern 7: Training Loop Entry Point

**What:** `worker/flows/rl_trainer.py` must exist as a runnable module. The training loop should:
1. Load transitions from DB (populate SumTree)
2. Run online SAC updates
3. Every 1,000 steps: checkpoint to DB + check diversity
4. On completion: fire summary alert

**Structure:**
```
worker/flows/rl_trainer.py
  main()
    → load_transitions_from_db() → populate PERBuffer
    → for step in range(total_steps):
        batch = buffer.sample(batch_size)
        updates = ensemble.update_all_from_batch(batch)
        if step % 1000 == 0:
            save_checkpoint_to_db(ensemble, step)
            diversity = compute_pairwise_diversity(ensemble.agents, canonical_obs)
            if diversity > 0.9: fire_diversity_alert()
        push_new_transitions_if_available()
```

### Anti-Patterns to Avoid

- **Gaussian+sigmoid actor for Beta spec:** The current `ContinuousActor` uses `torch.sigmoid(raw)` and has a manual log-prob correction. This is technically valid but does NOT produce a Beta distribution — it's a logistic-normal approximation. FR-5.3 is explicit: Beta distribution.
- **Checkpoint to filesystem only:** `rl_tasks.py` currently writes `sac_ensemble.pkl` to disk. Railway's filesystem is ephemeral. Only PostgreSQL survives Railway restarts.
- **pickle for network weights:** `pickle` on the full ensemble object is brittle (class changes break loading). Use `torch.save(state_dict)` → bytea.
- **All agents same seed:** The current `SACEnsemble` creates agents in a loop with no seed differentiation — produces near-identical initial weights given PyTorch's deterministic init.
- **3-specialist MoE with 5 agents:** Wiring 5 agents through 3 specialists (one per regime) loses 2 agents' contributions entirely. FR-5.5 requires all 5 to contribute.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Beta distribution sampling | Custom beta sampler | `torch.distributions.Beta` | Closed-form entropy, rsample (reparameterized), numerically stable |
| Cosine similarity | Manual dot product / norm | `torch.nn.functional.cosine_similarity` | Handles batched input, numerically stable |
| Priority tree | Custom binary heap | Existing `SumTree` in `rl/per_buffer.py` | Already correct, O(log n), tested |
| Transformer positional encoding | Custom sinusoidal PE | Existing `PositionalEncoding` in `rl/transformer_encoder.py` | Already implemented correctly |
| EPS surprise regression pre-training | Custom training loop from scratch | Standard PyTorch `nn.MSELoss` + `Adam` on existing `TransformerStateEncoder` | Model already correct, just needs training script |
| IS weight normalization | Manual weight computation | Existing `PERBuffer.sample()` returns `SampleBatch.weights` | Already handles beta annealing |

---

## Critical Architecture Decisions (Locked by STATE.md / CLAUDE.md)

| Decision | Value | Source |
|----------|-------|--------|
| PER storage backend | PostgreSQL `rl_transitions` hypertable (NOT Redis) | STATE.md — "Redis memory ceiling exceeded at S&P 500 scale" |
| Transformer encoder in v1.0 | Frozen weights (pre-trained, then `encoder.freeze()`) | STATE.md — "reduces training complexity, unfreeze in v2.0" |
| RL trainer deployment | Manual only — `deployTrigger = "manual"` | railway.toml already set; CI excludes rl/ |
| Macro multiplier integration | Post-RL deterministic override, NOT inside backward pass | FR-5.3 explicit |

---

## Architectural Gap Analysis

These gaps exist between what FR-5.x requires and what is currently implemented:

| Gap | File to Change | Severity |
|-----|---------------|----------|
| Actor uses Gaussian not Beta | `rl/sac_agent.py` → `ContinuousActor` | BLOCKING (FR-5.3) |
| No distinct agent seeds / perturbations | `rl/sac_agent.py` → `SACEnsemble.__init__` | BLOCKING (FR-5.1) |
| MoE blends 3 specialists not 5 agents | `rl/moe_controller.py` | BLOCKING (FR-5.5) |
| Transformer n_layers=4 not 3 | `rl/transformer_encoder.py` default + `config.py` `SACConfig.transformer_layers` | BLOCKING (FR-5.4) |
| PER buffer is in-memory only | `rl/per_buffer.py` + new `rl/db_per.py` | BLOCKING (FR-5.2) |
| No diversity monitoring | Create `rl/diversity_monitor.py` | BLOCKING (FR-5.6) |
| `rl_checkpoints` table missing from migrations | Create `backend/alembic/versions/0004_rl_phase5_tables.py` | BLOCKING (FR-5.7) |
| `rl_diversity_alerts` table missing | Same migration 0004 | BLOCKING (FR-5.6) |
| Training loop entry point missing | Create `worker/flows/rl_trainer.py` | BLOCKING (docker-compose command) |
| Transformer pre-training script missing | Create `rl/pretrain_transformer.py` | BLOCKING (FR-5.4) |
| Checkpoints every 1k steps not implemented | `worker/flows/rl_trainer.py` | BLOCKING (FR-5.7) |

---

## Common Pitfalls

### Pitfall 1: Beta Distribution Concentration at 0 or 1
**What goes wrong:** If `alpha` or `beta` parameters get very small (< 0.1), the Beta distribution concentrates all mass near 0 or 1, causing degenerate actions. Gradient can also explode at boundaries.
**Why it happens:** Unclamped `log_alpha_head` outputs can produce `exp(-5) ≈ 0.007`.
**How to avoid:** Clamp log params to `[-5, 2]` before `exp()`, then add `1e-3` to ensure `alpha, beta > 1e-3`. The clamp range `[-5, 2]` maps to approximately `[0.007, 7.4]` which keeps the distribution well-behaved.
**Warning signs:** `dist.entropy()` returning very negative values (< -2.0 nats).

### Pitfall 2: SumTree Index Mismatch After DB Reload
**What goes wrong:** After reloading transitions from DB, the SumTree leaf indices no longer correspond to DB primary keys, so `update_priorities` writes priorities to wrong leaves.
**Why it happens:** SumTree uses a circular write pointer (`_write`), so index mapping changes between process restarts.
**How to avoid:** Store both the SumTree leaf index and the DB primary key (`ts`, `episode_id`, `step`) in a side mapping. On priority update, write back to DB by PK, not SumTree index.

### Pitfall 3: Macro Multiplier Inside the Backward Pass
**What goes wrong:** If `apply_sizing_multiplier()` is applied before computing log_prob, the multiplier propagates gradients through the policy — making the agent learn to route around the macro gate.
**Why it happens:** Easy to accidentally apply multiplier inside `select_action()`.
**How to avoid:** `select_action()` returns raw Beta sample; multiplier applied in calling code with `torch.no_grad()` or as a plain Python float multiplication.

### Pitfall 4: Ensemble Diversity Collapse During Training
**What goes wrong:** All 5 agents converge to the same policy despite different seeds, triggering continuous diversity alerts.
**Why it happens:** Shared PER buffer means all agents train on identical batches. With similar architectures, entropy regularization drives them to the same maxent policy.
**How to avoid:** The ±30% hyperparameter perturbation (especially `alpha`/entropy temperature) is the primary diversity mechanism. Also consider per-agent experience replay subsets (each agent samples from a random 80% subset).
**Warning signs:** `rl_diversity_alert` fires within first 100 epochs.

### Pitfall 5: Railway Ephemeral Filesystem Breaks Pickle Checkpoint
**What goes wrong:** `sac_ensemble.pkl` written to local disk disappears on Railway service restart.
**Why it happens:** Railway services use ephemeral containers without persistent volumes attached to the `rl_trainer` service.
**How to avoid:** All checkpoint persistence must go through PostgreSQL `rl_checkpoints.model_bytes` (bytea). The `rl_tasks.py` filesystem save is development-only.

### Pitfall 6: `rl_transitions` JSONB State Vectors are Slow to Query
**What goes wrong:** Sampling 64 transitions from `rl_transitions` via `SELECT * FROM rl_transitions ORDER BY priority DESC LIMIT 64` takes >1s as table grows.
**Why it happens:** JSONB deserialization at query time; no limit pushdown.
**How to avoid:** Add `LIMIT` clause; use the existing `ix_rl_agent_priority` index. Pre-load a fixed working set (e.g., 50k most recent high-priority transitions) into the SumTree at training startup, then update incrementally.

### Pitfall 7: `n_layers=3` vs `n_layers=4` Breaks `from_pretrained`
**What goes wrong:** Pre-trained weights saved with `n_layers=3` fail to load into a model initialized with `n_layers=4` (or vice versa).
**Why it happens:** The layer count mismatch causes `load_state_dict` to raise a key mismatch error.
**How to avoid:** Fix `SACConfig.transformer_layers = 3` AND `TransformerStateEncoder.__init__` default `n_layers=3` in the same commit. The pre-training script must use the corrected count.

---

## Code Examples

### Beta Actor with Proper Entropy for SAC Alpha Update
```python
# Source: [ASSUMED — standard PyTorch Beta distribution SAC pattern]
# In BetaActor.sample():
alpha, beta_param = self(obs)
dist = Beta(alpha, beta_param)
action = dist.rsample()  # reparameterized — gradients flow through
log_prob = dist.log_prob(action).sum(-1, keepdim=True)
return action, log_prob

# Entropy for alpha auto-tuning:
entropy = dist.entropy().sum(-1).mean()
alpha_loss = -(self.log_alpha * (entropy.detach() + self.target_entropy))
```

### DB Priority Sampling (approximation)
```python
# Source: [ASSUMED — PostgreSQL priority sampling pattern]
def sample_from_db(conn, agent_ids: list[int], batch_size: int) -> list[dict]:
    rows = conn.execute(
        text("""
        SELECT ts, episode_id, step, agent_id, state_vec, action, reward,
               next_state_vec, done, priority
        FROM rl_transitions
        WHERE agent_id = ANY(:aids)
        ORDER BY priority DESC
        LIMIT :n
        """),
        {"aids": agent_ids, "n": batch_size * 5}  # oversample, then stochastic select
    ).fetchall()
    # Apply priority-proportional selection in Python
    priorities = np.array([float(r.priority) for r in rows])
    probs = priorities / priorities.sum()
    selected = np.random.choice(len(rows), size=batch_size, replace=False, p=probs)
    return [dict(rows[i]._mapping) for i in selected]
```

### Checkpoint to PostgreSQL
```python
# Source: [VERIFIED: torch.save to BytesIO works in session, psycopg2.Binary confirmed]
import io, torch, psycopg2

def save_checkpoint(conn, ensemble, step: int):
    for agent_id, agent in enumerate(ensemble.agents):
        buf = io.BytesIO()
        torch.save({
            'cont_actor': agent.cont_actor.state_dict(),
            'disc_actor': agent.disc_actor.state_dict(),
            'critic': agent.critic.state_dict(),
            'log_alpha': agent.log_alpha.item(),
        }, buf)
        conn.execute(
            text("""
            INSERT INTO rl_checkpoints (step, agent_id, model_bytes, is_active)
            VALUES (:step, :agent_id, :model_bytes, TRUE)
            """),
            {
                "step": step,
                "agent_id": agent_id,
                "model_bytes": psycopg2.Binary(buf.getvalue()),
            }
        )
```

---

## Runtime State Inventory

> Phase 5 creates new DB tables but does not rename or refactor existing state. Greenfield additions only.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `rl_transitions` hypertable — exists with schema, likely empty in dev | No migration needed for this table; it exists |
| Stored data | `rl_checkpoints` table — referenced in `rl_tasks.py` but NOT in any migration | Must create in migration 0004 |
| Stored data | `rl_diversity_alerts` table — does not exist anywhere | Must create in migration 0004 |
| Live service config | `rl-trainer` service in `railway.toml` with `deployTrigger = "manual"` | Already correct; no change needed |
| OS-registered state | None | None |
| Secrets/env vars | `DATABASE_URL_SYNC` env var used in `rl_tasks.py` — must be set in Railway rl_trainer service env | Document in Railway service config |
| Build artifacts | `worker/flows/rl_trainer.py` missing — docker-compose `command` will fail without it | Create file |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11 | RL training | ✓ | 3.11.4 | — |
| torch | SAC agents, Beta dist, Transformer | ✓ | 2.11.0 | — |
| numpy | SumTree, array ops | ✓ | 2.1.3 | — |
| gymnasium | PEADTradingEnv | ✓ | 1.2.3 | — |
| psycopg2-binary | DB PER writes | ✓ | 2.9.10 | — |
| Docker | rl-trainer container build | ✓ | 29.4.1 | — |
| Redis | Celery broker (alert dispatch) | ✓ (PONG) | — | — |
| PostgreSQL/TimescaleDB | rl_transitions + rl_checkpoints | ✗ locally (runs in Docker) | — | docker compose up db |

**Missing dependencies with no fallback:**
- PostgreSQL must be running (via `docker compose up -d db`) before the training loop can persist transitions or checkpoints.

**Missing dependencies with fallback:**
- None — all runtime dependencies available.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.3 |
| Config file | none (uses default discovery) |
| Quick run command | `cd backend && pytest tests/ -v --tb=short -k "not integration"` |
| Full suite command | `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead cd backend && pytest tests/ -v --tb=short` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FR-5.1 | 5 agents have distinct seeds; no two share identical weights at init | unit | `pytest backend/tests/rl/test_sac_ensemble.py::test_agent_weight_diversity -x` | ❌ Wave 0 |
| FR-5.1 | Hyperparameter perturbations are ±30% of base values | unit | `pytest backend/tests/rl/test_sac_ensemble.py::test_hyperparameter_perturbation -x` | ❌ Wave 0 |
| FR-5.2 | DB push writes transition to rl_transitions table | integration | `pytest backend/tests/rl/test_per_db.py::test_push_to_db -x` | ❌ Wave 0 |
| FR-5.2 | DB sample returns higher-priority transitions more frequently | unit | `pytest backend/tests/rl/test_per_db.py::test_priority_sampling -x` | ❌ Wave 0 |
| FR-5.3 | BetaActor produces samples in (0,1) | unit | `pytest backend/tests/rl/test_sac_ensemble.py::test_beta_action_range -x` | ❌ Wave 0 |
| FR-5.3 | Macro multiplier not in backward pass (gradient check) | unit | `pytest backend/tests/rl/test_sac_ensemble.py::test_macro_multiplier_no_grad -x` | ❌ Wave 0 |
| FR-5.4 | TransformerStateEncoder has d_model=64, 3 layers, 4 heads | unit | `pytest backend/tests/rl/test_transformer.py::test_encoder_config -x` | ❌ Wave 0 |
| FR-5.4 | Frozen encoder has no trainable parameters | unit | `pytest backend/tests/rl/test_transformer.py::test_frozen_encoder -x` | ❌ Wave 0 |
| FR-5.5 | MoE blend uses all 5 agent outputs (not 3 specialists) | unit | `pytest backend/tests/rl/test_moe.py::test_five_agent_blend -x` | ❌ Wave 0 |
| FR-5.5 | Expansion/caution/crisis weights sum to 1.0 | unit | `pytest backend/tests/rl/test_moe.py::test_regime_weights_sum -x` | ❌ Wave 0 |
| FR-5.6 | Diversity monitor fires alert when cosine sim > 0.9 | unit | `pytest backend/tests/rl/test_diversity.py::test_alert_fires_above_threshold -x` | ❌ Wave 0 |
| FR-5.6 | No alert when agents are diverse (sim < 0.9) | unit | `pytest backend/tests/rl/test_diversity.py::test_no_alert_below_threshold -x` | ❌ Wave 0 |
| FR-5.7 | Checkpoint written to rl_checkpoints table every 1000 steps | integration | `pytest backend/tests/rl/test_trainer.py::test_checkpoint_at_1000_steps -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend && pytest backend/tests/rl/ -v --tb=short -k "not integration"`
- **Per wave merge:** `DATABASE_URL_SYNC=postgresql://pead:pead@localhost:5432/pead pytest backend/tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/rl/__init__.py` — create test subpackage
- [ ] `backend/tests/rl/test_sac_ensemble.py` — covers FR-5.1, FR-5.3
- [ ] `backend/tests/rl/test_per_db.py` — covers FR-5.2 (integration, skips without DB)
- [ ] `backend/tests/rl/test_transformer.py` — covers FR-5.4
- [ ] `backend/tests/rl/test_moe.py` — covers FR-5.5
- [ ] `backend/tests/rl/test_diversity.py` — covers FR-5.6
- [ ] `backend/tests/rl/test_trainer.py` — covers FR-5.7 (integration)
- [ ] Framework install: already present — no action needed

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | Internal service only |
| V5 Input Validation | yes | Clamp Beta params; clip action to [0,1]; validate `priority > 0` before DB insert |
| V6 Cryptography | no | No secrets in checkpoint; model weights are not sensitive |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| JSONB injection via state_vec | Tampering | SQLAlchemy parameterized queries; never format JSON into raw SQL |
| Checkpoint bytea overflow | DoS | Enforce model size limit (< 50MB per agent checkpoint) |
| Diversity alert storm | DoS | Rate-limit `rl_diversity_alert` events via existing `alert_cooldown_seconds=300` in `AlertConfig` |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The correct MoE architecture for FR-5.5 is a weighted average of all 5 agents' outputs (not 3 specialist agents) | Architecture Patterns | If FR-5.5 intended 5 agents organized as specialists, redesign needed |
| A2 | FR-5.8 and FR-5.9 correspond to requirements not visible in ROADMAP.md (REQUIREMENTS.md file was not found) | Phase Requirements | May add requirements that require additional plan tasks |
| A3 | The 5-agent regime assignment in MoE (0-1→expansion, 2-3→caution, 4→crisis) is the preferred strategy | Architecture Patterns | Alternative: learned gating or equal assignment; revisit in planning |
| A4 | Pre-training the Transformer on EPS surprise regression uses `earnings_events.eps_surprise` from the existing DB schema | Architecture Patterns | If this column doesn't exist, pre-training data source must be derived from `earnings_events` |
| A5 | "8-quarter input" for the Transformer encoder means 8 consecutive quarterly EPS surprise values per ticker | Standard Stack | If it means 8 quarters of multi-feature input, input_dim changes from 31 to something else |

---

## Open Questions

1. **FR-5.8 and FR-5.9 content**
   - What we know: ROADMAP.md lists 9 requirements (FR-5.1 through FR-5.9) but only describes 7 success criteria
   - What's unclear: What do FR-5.8 and FR-5.9 specify?
   - Recommendation: Check REQUIREMENTS.md for exact text before planning; plan for 2 additional tasks

2. **Transformer pre-training data availability**
   - What we know: Phase 2 must complete before Phase 5 (data pipelines); `earnings_events` table exists with `eps_surprise`/`eps_actual` columns
   - What's unclear: Is there sufficient earnings history (8+ quarters per ticker) in the DB for pre-training?
   - Recommendation: Pre-training script should degrade gracefully if < 8 quarters exist (use available history, skip tickers with < 2 quarters)

3. **Integration point with portfolio pipeline (FR-5.3 macro multiplier)**
   - What we know: `apply_sizing_multiplier()` exists in `backend/app/portfolio/macro.py`; SAC output is `entry_size ∈ [0,1]`
   - What's unclear: Does the RL trainer need to call the macro multiplier at all, or only the inference path (Celery task → signal pipeline)?
   - Recommendation: Macro multiplier is applied only at **inference time** (in the Celery signal task), not during training. Training rewards are computed on raw RL actions. This keeps training and inference consistent with FR-5.3 "does not backpropagate."

---

## Sources

### Primary (HIGH confidence)
- Codebase: `rl/sac_agent.py` — verified current SAC architecture (Gaussian actor, n_agents=5 shared config)
- Codebase: `rl/moe_controller.py` — verified 3-specialist design vs FR-5.5 requirement
- Codebase: `rl/transformer_encoder.py` — verified n_layers=4 default vs FR-5.4 requirement for 3
- Codebase: `config.py` — verified `SACConfig.transformer_layers=4`
- Codebase: `backend/app/models/rl_transitions.py` — verified hypertable schema with priority column
- Codebase: `railway.toml` — verified `deployTrigger = "manual"` for rl_trainer
- Codebase: `backend/alembic/versions/0001_initial_schema.py` — verified `rl_transitions` hypertable exists; `rl_checkpoints` and `rl_diversity_alerts` do NOT exist
- Local env verification: torch 2.11.0, Beta distribution sampling, cosine_similarity, BytesIO checkpoint serialization — all confirmed working

### Secondary (MEDIUM confidence)
- PyTorch Beta distribution for [0,1] action spaces — standard technique in continuous RL for bounded actions; widely used in portfolio sizing and option pricing agents [ASSUMED]

### Tertiary (LOW confidence)
- Pairwise cosine similarity on Beta parameters as diversity metric — common in ensemble RL literature but specific threshold (0.9) is from FR spec, not validated against research [ASSUMED]

---

## Metadata

**Confidence breakdown:**
- Codebase gaps identified: HIGH — all verified by direct code reading
- Standard stack: HIGH — all verified locally installed
- Architecture corrections needed: HIGH — direct spec vs code comparison
- Pitfalls: MEDIUM — training pitfalls from [ASSUMED] general SAC/ensemble knowledge
- FR-5.8/5.9 content: LOW — REQUIREMENTS.md not found

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (stable PyTorch API; torch.distributions.Beta has been stable since torch 1.x)
