"""Pre-train TransformerStateEncoder on next-quarter EPS surprise regression (FR-5.4).

Per FR-5.4: "Transformer encoder pre-trained on next-quarter EPS surprise regression;
loads frozen weights in v1.0."

Per RESEARCH.md A4 / Q2 (resolved): eps_surprise is DERIVED as eps_actual - eps_estimate
(the earnings_events table has no eps_surprise column). Tickers with < 8 quarters of
clean (eps_actual, eps_estimate) data are skipped -- degrades gracefully when called
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
        # Sliding windows of size (seq_len) -> predict surprise at index seq_len
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
        return (
            np.zeros((0, seq_len, input_dim), dtype=np.float32),
            np.zeros((0,), dtype=np.float32),
            tickers_used,
        )
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
        n_tickers,
        X.shape[0],
        seq_len,
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
        n_tickers,
        X.shape[0],
        final_mse,
        output_path,
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
