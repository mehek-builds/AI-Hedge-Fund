---
phase: 05-sac-ensemble-rl
plan: 02b
type: execute
wave: 2
depends_on: ["05-02"]
files_modified:
  - rl/pretrain_transformer.py
  - rl/transformer_encoder.py
  - backend/tests/rl/test_transformer_encoder.py
autonomous: true
requirements:
  - FR-5.4

must_haves:
  truths:
    - "rl/pretrain_transformer.py reads earnings_events.eps_surprise (computed from eps_actual - eps_estimate) and trains TransformerStateEncoder on next-quarter EPS surprise regression with MSELoss"
    - "Pre-trained encoder state_dict is saved to rl/weights/transformer_pretrained.pt"
    - "TransformerStateEncoder.from_pretrained(path) loads the checkpoint, calls freeze(), and returns an encoder where every parameter has requires_grad == False"
    - "Pretrain script degrades gracefully: if a ticker has < 8 quarters of earnings, it is skipped; if total tickers with >= 8 quarters is 0, the script exits with a non-zero code and a clear message"
    - "test_frozen_encoder_loads_weights asserts that, after from_pretrained, every parameter has requires_grad == False AND the loaded weights match what was saved (within float tolerance)"
  artifacts:
    - path: "rl/pretrain_transformer.py"
      provides: "Standalone CLI to pretrain the transformer encoder on EPS surprise regression"
      contains: "def pretrain"
      contains_2: "MSELoss"
      contains_3: "earnings_events"
    - path: "rl/transformer_encoder.py"
      provides: "from_pretrained classmethod (already present) — verify behavior matches new pretrain artifact"
      contains: "def from_pretrained"
    - path: "backend/tests/rl/test_transformer_encoder.py"
      provides: "test_frozen_encoder_loads_weights"
      contains: "test_frozen_encoder_loads_weights"
  key_links:
    - from: "rl/pretrain_transformer.py:pretrain"
      to: "earnings_events.eps_actual / eps_estimate"
      via: "SQLAlchemy text() SELECT"
      pattern: "FROM earnings_events"
    - from: "rl/pretrain_transformer.py:pretrain"
      to: "rl/weights/transformer_pretrained.pt"
      via: "torch.save(state_dict, path)"
      pattern: "torch\\.save\\(.*state_dict"
    - from: "TransformerStateEncoder.from_pretrained"
      to: "freeze()"
      via: "internal call (already present in encoder)"
      pattern: "model\\.freeze\\(\\)"
---

<objective>
Implement the missing FR-5.4 pre-training component flagged as BLOCKING in RESEARCH.md (architectural gap analysis row "Transformer pre-training script missing"). The Transformer encoder must be pre-trained on next-quarter EPS surprise regression using `earnings_events` data BEFORE SACEnsemble.__init__ loads it as a frozen feature extractor in v1.0.

Purpose: FR-5.4 explicitly requires "Transformer encoder pre-trained on next-quarter EPS surprise regression; loads frozen weights in v1.0." Without a pretrain script and saved checkpoint, the SACEnsemble cannot satisfy "loads frozen weights" — it would only ever load random init weights, defeating the purpose of the encoder.

Output: `rl/pretrain_transformer.py` runnable as `python -m rl.pretrain_transformer`; checkpoint saved at `rl/weights/transformer_pretrained.pt`; new test `test_frozen_encoder_loads_weights` GREEN.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@.planning/phases/05-sac-ensemble-rl/05-RESEARCH.md
@.planning/phases/05-sac-ensemble-rl/05-02-SUMMARY.md
@CLAUDE.md
@rl/transformer_encoder.py
@backend/app/models/earnings_events.py
@backend/tests/rl/test_transformer_encoder.py
@rl/db_per.py

<interfaces>
<!-- TransformerStateEncoder already has from_pretrained + freeze (verified) -->
From rl/transformer_encoder.py:
```python
class TransformerStateEncoder(nn.Module):
    def __init__(self, input_dim=31, d_model=64, n_heads=4, n_layers=3, ...): ...
    def freeze(self) -> None: ...   # sets all requires_grad = False
    @classmethod
    def from_pretrained(cls, path: str, **kwargs) -> "TransformerStateEncoder":
        model = cls(**kwargs)
        state = torch.load(path, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
        model.freeze()
        return model
```

<!-- earnings_events schema (eps_surprise must be computed) -->
From backend/app/models/earnings_events.py:
```python
class EarningsEvent(Base):
    __tablename__ = "earnings_events"
    symbol: str
    announced_at: datetime          # ordering
    fiscal_quarter: str
    eps_actual: Decimal             # nullable
    eps_estimate: Decimal           # nullable
    # NOTE: there is NO eps_surprise column. RESEARCH.md A4 assumed one exists.
    # Derived: eps_surprise = eps_actual - eps_estimate
```

<!-- DB engine helper (Plan 03) -->
From rl/db_per.py:
get_engine(database_url=None) -> sqlalchemy.Engine
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add test_frozen_encoder_loads_weights to existing transformer test file</name>
  <files>backend/tests/rl/test_transformer_encoder.py</files>
  <read_first>
    - backend/tests/rl/test_transformer_encoder.py (current Plan 01 contents — must append, not overwrite)
    - rl/transformer_encoder.py (from_pretrained signature)
  </read_first>
  <behavior>
    - test_frozen_encoder_loads_weights creates a small encoder, saves its state_dict to a temp .pt file, calls from_pretrained on that path, then asserts every parameter has requires_grad == False AND a sentinel weight matches the saved value
  </behavior>
  <action>
Append to `backend/tests/rl/test_transformer_encoder.py` (at end of file):

```python


def test_frozen_encoder_loads_weights(tmp_path):
    """FR-5.4: from_pretrained loads checkpoint AND freezes every parameter."""
    import torch
    from rl.transformer_encoder import TransformerStateEncoder

    src = TransformerStateEncoder(input_dim=31, d_model=64, n_heads=4, n_layers=3)
    # Capture a sentinel weight to verify the load actually wrote weights
    sentinel_before = next(src.parameters()).detach().clone()

    ckpt = tmp_path / "transformer_pretrained.pt"
    torch.save(src.state_dict(), ckpt)

    loaded = TransformerStateEncoder.from_pretrained(
        str(ckpt), input_dim=31, d_model=64, n_heads=4, n_layers=3
    )

    # Frozen: no parameter trains
    assert all(not p.requires_grad for p in loaded.parameters()), \
        "from_pretrained must call freeze() — every parameter requires_grad must be False"

    # Loaded weights match what was saved (within float tolerance)
    sentinel_after = next(loaded.parameters()).detach().clone()
    assert torch.allclose(sentinel_before, sentinel_after, atol=1e-6), \
        "Loaded weights do not match saved weights — load_state_dict failed silently?"
```
  </action>
  <verify>
    <automated>cd backend && pytest tests/rl/test_transformer_encoder.py::test_frozen_encoder_loads_weights -v --tb=short</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "def test_frozen_encoder_loads_weights" backend/tests/rl/test_transformer_encoder.py` returns 1
    - `grep -c "from_pretrained" backend/tests/rl/test_transformer_encoder.py` returns >= 1
    - `pytest backend/tests/rl/test_transformer_encoder.py::test_frozen_encoder_loads_weights -x` exits 0
    - All other transformer tests still pass: `pytest backend/tests/rl/test_transformer_encoder.py -x` exits 0
  </acceptance_criteria>
  <done>New frozen-load test passes; existing layer-count and frozen tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Create rl/pretrain_transformer.py — EPS surprise regression pretrain</name>
  <files>rl/pretrain_transformer.py</files>
  <read_first>
    - rl/transformer_encoder.py (full file — TransformerStateEncoder forward signature is (batch, seq_len, input_dim) -> (batch, d_model))
    - backend/app/models/earnings_events.py (column names; eps_surprise must be DERIVED as eps_actual - eps_estimate, no such column exists)
    - rl/db_per.py (get_engine helper)
    - .planning/phases/05-sac-ensemble-rl/05-RESEARCH.md (A4 / Open Question Q2 — graceful skip when < 8 quarters available)
    - CLAUDE.md (RL trainer manual deploy only; pretrain is a one-shot dev task — runs locally, not on Railway)
  </read_first>
  <behavior>
    - pretrain(database_url=None, n_epochs=10, output_path="rl/weights/transformer_pretrained.pt", min_quarters=8) returns the saved path
    - SQL: SELECT symbol, announced_at, eps_actual, eps_estimate FROM earnings_events WHERE eps_actual IS NOT NULL AND eps_estimate IS NOT NULL ORDER BY symbol, announced_at
    - For each symbol with >= min_quarters quarters: build sliding windows of 8 quarters; target = next quarter's eps_surprise (eps_actual - eps_estimate)
    - Input feature vector per quarter: [eps_surprise_normalized, ...padding to 31 dims with zeros] — the encoder's input_dim is 31, but we have only 1 meaningful feature, so pad with zeros (this is acceptable for a lightweight pretrain — RESEARCH.md A5 noted the input_dim assumption)
    - Loss: nn.MSELoss between encoder(seq).cls_out projected through a linear head and the target eps_surprise
    - If 0 tickers qualify (< 8 quarters available globally) → exit with non-zero code and message "FR-5.4: insufficient earnings history (0 tickers with >= 8 quarters); skipping pretrain. Run again after Phase 2 ingestion completes."
    - On success: torch.save(encoder.state_dict(), output_path); print summary {tickers_used, windows_seen, final_mse, output_path}
  </behavior>
  <action>
Create new file `rl/pretrain_transformer.py`:

```python
"""Pre-train TransformerStateEncoder on next-quarter EPS surprise regression (FR-5.4).

Per FR-5.4: "Transformer encoder pre-trained on next-quarter EPS surprise regression;
loads frozen weights in v1.0."

Per RESEARCH.md A4 / Q2 (resolved): eps_surprise is DERIVED as eps_actual - eps_estimate
(the earnings_events table has no eps_surprise column). Tickers with < 8 quarters of
clean (eps_actual, eps_estimate) data are skipped — degrades gracefully when called
before Phase 2 ingestion has fully populated the table.

This is a one-shot developer task; not part of the Railway training service.
Run locally: `python -m rl.pretrain_transformer`
Output:      rl/weights/transformer_pretrained.pt
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from sqlalchemy import text

from rl.db_per import get_engine
from rl.transformer_encoder import TransformerStateEncoder

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

DEFAULT_OUTPUT = Path("rl/weights/transformer_pretrained.pt")
DEFAULT_INPUT_DIM = 31
SEQ_LEN = 8                # 8 quarters per FR-5.4
MIN_QUARTERS = 8           # need at least 8 to form one (input, target) pair


class _PretrainHead(nn.Module):
    """Tiny linear head from encoder cls_out (d_model) -> scalar EPS surprise."""

    def __init__(self, d_model: int = 64) -> None:
        super().__init__()
        self.head = nn.Linear(d_model, 1)

    def forward(self, cls_out: torch.Tensor) -> torch.Tensor:
        return self.head(cls_out).squeeze(-1)


def _load_eps_series(engine) -> dict[str, list[float]]:
    """Return {symbol: [eps_surprise_q1, eps_surprise_q2, ...]} ordered by announced_at."""
    rows = []
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT symbol, announced_at, eps_actual, eps_estimate
                FROM earnings_events
                WHERE eps_actual IS NOT NULL
                  AND eps_estimate IS NOT NULL
                  AND symbol IS NOT NULL
                ORDER BY symbol, announced_at
                """
            )
        ).all()

    series: dict[str, list[float]] = {}
    for r in rows:
        surprise = float(r.eps_actual) - float(r.eps_estimate)
        series.setdefault(r.symbol, []).append(surprise)
    return series


def _build_windows(
    series: dict[str, list[float]],
    seq_len: int,
    input_dim: int,
    min_quarters: int,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Return (X, y, n_tickers_used). X shape: (N, seq_len, input_dim); y shape: (N,)."""
    Xs: list[np.ndarray] = []
    ys: list[float] = []
    tickers_used = 0
    for symbol, surprises in series.items():
        if len(surprises) < min_quarters:
            continue
        tickers_used += 1
        # Sliding windows of size (seq_len) → predict surprise at index seq_len
        # Need at least seq_len + 1 quarters to form one (input, target) pair
        if len(surprises) < seq_len + 1:
            continue
        for i in range(len(surprises) - seq_len):
            window = np.zeros((seq_len, input_dim), dtype=np.float32)
            window[:, 0] = np.asarray(surprises[i : i + seq_len], dtype=np.float32)
            target = float(surprises[i + seq_len])
            Xs.append(window)
            ys.append(target)

    if not Xs:
        return np.zeros((0, seq_len, input_dim), dtype=np.float32), np.zeros((0,), dtype=np.float32), tickers_used
    return np.stack(Xs), np.asarray(ys, dtype=np.float32), tickers_used


def pretrain(
    database_url: Optional[str] = None,
    n_epochs: int = 10,
    batch_size: int = 64,
    lr: float = 1e-3,
    output_path: Path = DEFAULT_OUTPUT,
    seq_len: int = SEQ_LEN,
    input_dim: int = DEFAULT_INPUT_DIM,
    min_quarters: int = MIN_QUARTERS,
) -> Path:
    """Train the encoder on EPS surprise regression and save state_dict.

    Returns path to saved checkpoint.
    """
    engine = get_engine(database_url)
    series = _load_eps_series(engine)
    X, y, n_tickers = _build_windows(series, seq_len, input_dim, min_quarters)

    if n_tickers == 0 or X.shape[0] == 0:
        logger.error(
            "FR-5.4: insufficient earnings history (0 tickers with >= %d quarters); "
            "skipping pretrain. Run again after Phase 2 ingestion completes.",
            min_quarters,
        )
        sys.exit(2)

    logger.info(
        "pretrain corpus: tickers_used=%d windows=%d seq_len=%d",
        n_tickers, X.shape[0], seq_len,
    )

    encoder = TransformerStateEncoder(input_dim=input_dim, n_layers=3)
    head = _PretrainHead(d_model=encoder.d_model)
    params = list(encoder.parameters()) + list(head.parameters())
    optim = torch.optim.Adam(params, lr=lr)
    loss_fn = nn.MSELoss()

    Xt = torch.from_numpy(X)
    yt = torch.from_numpy(y)

    final_mse = float("nan")
    for epoch in range(1, n_epochs + 1):
        perm = torch.randperm(Xt.size(0))
        epoch_losses: list[float] = []
        for start in range(0, Xt.size(0), batch_size):
            idx = perm[start : start + batch_size]
            batch_x = Xt[idx]
            batch_y = yt[idx]
            cls_out = encoder(batch_x)
            pred = head(cls_out)
            loss = loss_fn(pred, batch_y)
            optim.zero_grad()
            loss.backward()
            optim.step()
            epoch_losses.append(float(loss.item()))
        final_mse = float(np.mean(epoch_losses)) if epoch_losses else float("nan")
        logger.info("epoch %d/%d mse=%.6f", epoch, n_epochs, final_mse)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(encoder.state_dict(), output_path)
    logger.info(
        "pretrain done: tickers=%d windows=%d final_mse=%.6f saved=%s",
        n_tickers, X.shape[0], final_mse, output_path,
    )
    return output_path


def _cli() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--database-url", type=str, default=None)
    p.add_argument("--n-epochs", type=int, default=10)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    p.add_argument("--min-quarters", type=int, default=MIN_QUARTERS)
    args = p.parse_args()
    pretrain(
        database_url=args.database_url,
        n_epochs=args.n_epochs,
        output_path=args.output,
        min_quarters=args.min_quarters,
    )
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
```
  </action>
  <verify>
    <automated>cd backend && python -c "import importlib.util; s = importlib.util.spec_from_file_location('m', '../rl/pretrain_transformer.py'); m = importlib.util.module_from_spec(s); s.loader.exec_module(m); assert callable(m.pretrain) and m.SEQ_LEN == 8 and m.MIN_QUARTERS == 8; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - File exists: `test -f rl/pretrain_transformer.py`
    - `grep -c "def pretrain" rl/pretrain_transformer.py` returns 1
    - `grep -c "MSELoss" rl/pretrain_transformer.py` returns 1
    - `grep -c "FROM earnings_events" rl/pretrain_transformer.py` returns 1
    - `grep -c "eps_actual" rl/pretrain_transformer.py` returns >= 2
    - `grep -c "eps_estimate" rl/pretrain_transformer.py` returns >= 2
    - `grep -c "torch.save(encoder.state_dict()" rl/pretrain_transformer.py` returns 1
    - `grep -c "transformer_pretrained.pt" rl/pretrain_transformer.py` returns >= 1
    - `grep -c "n_layers=3" rl/pretrain_transformer.py` returns 1
    - `grep -c "sys.exit(2)" rl/pretrain_transformer.py` returns 1 (graceful skip when corpus empty)
    - No string-format SQL: `grep -c 'f"SELECT\|f"FROM\|.format(.*SELECT' rl/pretrain_transformer.py` returns 0
    - Module imports cleanly (verify command above prints "OK")
  </acceptance_criteria>
  <done>Pretrain script exists, imports cleanly, uses parameterized SQL, derives eps_surprise from actual/estimate, saves to transformer_pretrained.pt, and exits with code 2 + clear message when the earnings corpus is too small.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| pretrain script→DB | Read-only SELECT on earnings_events; no writes |
| pretrain script→filesystem | Writes one .pt file under rl/weights/ |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-05-21 | Tampering | SQL injection via symbol filter | mitigate | Parameterized SQLAlchemy text() with no f-string interpolation |
| T-05-22 | DoS | Unbounded SELECT pulls full earnings history | accept | earnings_events bounded by S&P 500 * ~40 quarters ~= 20k rows; trivial size |
| T-05-23 | Tampering | rl/weights/ checkpoint poisoning | accept | Local-only artifact in dev; not committed to git; not deployed to Railway |
</threat_model>

<verification>
- `cd backend && pytest tests/rl/test_transformer_encoder.py -v` — all transformer tests including new test_frozen_encoder_loads_weights GREEN
- Import smoke: `python -c "from rl import pretrain_transformer; assert callable(pretrain_transformer.pretrain)"` exits 0
- DB-gated smoke (manual): `python -m rl.pretrain_transformer --n-epochs 1` exits 0 OR exit 2 with insufficient-data message — both are acceptable behaviors per FR-5.4 graceful-skip clause
</verification>

<success_criteria>
- rl/pretrain_transformer.py exists and is importable
- TransformerStateEncoder.from_pretrained(path) loads weights AND freezes (verified by new test)
- Pretrain script gracefully skips when earnings corpus has < 8 quarters
- FR-5.4 BLOCKING gap from RESEARCH.md is closed
</success_criteria>

<output>
After completion, create `.planning/phases/05-sac-ensemble-rl/05-02b-SUMMARY.md` documenting:
- New file rl/pretrain_transformer.py (lines, public functions)
- Note that eps_surprise is DERIVED in SQL (eps_actual - eps_estimate) — earnings_events has no eps_surprise column despite RESEARCH.md A4 wording
- Default output path rl/weights/transformer_pretrained.pt
- Behavior when corpus is empty (sys.exit(2))
- Wiring note for Plan 05: SACEnsemble.__init__ should call TransformerStateEncoder.from_pretrained("rl/weights/transformer_pretrained.pt", input_dim=31, n_layers=3) when the file exists; fall back to a fresh-init encoder otherwise (so trainer can run before pretrain has been executed)
</output>
