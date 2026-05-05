"""Completion-portfolio SLSQP optimizer (FR-4.5).

Allocates 23% of NAV between IVE and IYR to neutralize factor tilts,
targeting Fama-French 3-factor betas (Mkt-Rf=0.985, SMB=-0.155, HML=+0.025).
Uses scipy.optimize.minimize with method='SLSQP'. DB-free, stateless.

The optimizer finds internal weights (summing to 1.0 within the completion
sleeve) that minimize squared deviations from FF3_TARGETS. The returned
`weights` dict stores NAV fractions (internal_weight * COMPLETION_WEIGHT),
ensuring weights["IVE"] + weights["IYR"] == COMPLETION_WEIGHT (0.23).
The `achieved_betas` are computed from the raw internal weights so that they
can be directly compared with FF3_TARGETS (standalone beta values).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from scipy.optimize import minimize

COMPLETION_WEIGHT: Decimal = Decimal("0.23")  # 23% NAV
COMPLETION_INSTRUMENTS: tuple[str, ...] = ("IVE", "IYR")

# Target FF3 betas the completion sleeve must achieve (FR-4.5)
FF3_TARGETS: dict[str, float] = {
    "Mkt-Rf": 0.985,
    "SMB": -0.155,
    "HML": 0.025,
}
FF3_TOLERANCE: float = 0.05  # achieved beta within +/- 0.05 of target (per domain spec)

_FACTORS = ("Mkt-Rf", "SMB", "HML")


@dataclass(frozen=True)
class CompletionAllocation:
    """Result of the SLSQP completion optimizer.

    Attributes:
        weights: {"IVE": Decimal("..."), "IYR": Decimal("...")}
                 Values are NAV fractions; weights["IVE"] + weights["IYR"] == COMPLETION_WEIGHT.
        achieved_betas: {"Mkt-Rf": ..., "SMB": ..., "HML": ...}
                        Computed from internal sleeve weights (sum-to-1 basis),
                        so values are directly comparable to FF3_TARGETS.
        success: SLSQP convergence flag
    """
    weights: dict[str, Decimal]
    achieved_betas: dict[str, float]
    success: bool


def optimize_completion_weights(
    instrument_betas: dict[str, dict[str, float]],
    # e.g. {"IVE": {"Mkt-Rf": 0.97, "SMB": -0.18, "HML": 0.30}, "IYR": {...}}
) -> CompletionAllocation:
    """Optimize IVE/IYR sleeve allocation to achieve FF3 beta targets via SLSQP.

    Decision variables: w = [w_IVE, w_IYR] — internal fractional weights
    within the completion sleeve (sum to 1.0). These are then scaled by
    COMPLETION_WEIGHT to produce NAV fractions stored in `weights`.

    Objective: minimize sum of squared beta deviations from FF3_TARGETS.
    Equality constraint: w[0] + w[1] == 1.0 (internal weights sum to 1).
    Bounds: each internal weight in [0.0, 1.0].

    Returns a CompletionAllocation with:
      - weights: NAV fractions (internal_weight * COMPLETION_WEIGHT),
                 quantized to 6 decimal places.
      - achieved_betas: computed from internal weights (comparable to FF3_TARGETS).
      - success: SLSQP convergence flag.
    """
    ive_betas = instrument_betas["IVE"]
    iyr_betas = instrument_betas["IYR"]

    def objective(w: list[float]) -> float:
        achieved = {
            f: w[0] * ive_betas[f] + w[1] * iyr_betas[f]
            for f in _FACTORS
        }
        return sum((achieved[f] - FF3_TARGETS[f]) ** 2 for f in _FACTORS)

    # Internal weights sum to 1.0 (fraction within the sleeve)
    constraints = [
        {"type": "eq", "fun": lambda w: w[0] + w[1] - 1.0}
    ]
    bounds = [
        (0.0, 1.0),
        (0.0, 1.0),
    ]
    x0 = [0.5, 0.5]

    result = minimize(
        objective,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
    )

    w_ive_internal, w_iyr_internal = result.x

    # Scale internal weights by COMPLETION_WEIGHT to get NAV fractions
    completion_float = float(COMPLETION_WEIGHT)
    nav_ive = w_ive_internal * completion_float
    nav_iyr = w_iyr_internal * completion_float

    # Convert to Decimal, quantized to 6 dp
    quant = Decimal("0.000001")
    dec_ive = Decimal(str(nav_ive)).quantize(quant, rounding=ROUND_HALF_UP)
    dec_iyr = Decimal(str(nav_iyr)).quantize(quant, rounding=ROUND_HALF_UP)

    # achieved_betas use internal weights so they're directly comparable to FF3_TARGETS
    achieved_betas = {
        f: w_ive_internal * ive_betas[f] + w_iyr_internal * iyr_betas[f]
        for f in _FACTORS
    }

    return CompletionAllocation(
        weights={"IVE": dec_ive, "IYR": dec_iyr},
        achieved_betas=achieved_betas,
        success=bool(result.success),
    )
