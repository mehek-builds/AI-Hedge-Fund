"""Register all Phase 2 deployments on the Prefect server.

`flow.serve(...)` is a blocking call (it starts a worker process), so we cannot
sequentially call all six in one process. Instead we use multiprocessing to
serve each in its own subprocess. In production each flow can also run as its
own container; for the dev environment a single Python process with 6 children
is acceptable.

Usage:
    python -m scripts.deploy_all_flows         # blocks, runs all 6 schedulers
    python -m scripts.deploy_all_flows --once  # call deploy() once and exit
                                                 (useful for CI registration tests)
"""
from __future__ import annotations
import argparse
import multiprocessing
import sys
from typing import Callable


def _runners() -> list[tuple[str, Callable]]:
    from app.flows.prices import deploy as d_prices
    from app.flows.macro import deploy as d_macro
    from app.flows.ff5 import deploy as d_ff5
    from app.flows.earnings import deploy as d_earnings
    from app.flows.constituents import deploy as d_cons
    from app.flows.derived_macro import deploy as d_deriv
    return [
        ("ingest-prices-daily", d_prices),
        ("ingest-macro-daily", d_macro),
        ("ingest-ff5-weekly", d_ff5),
        ("ingest-earnings-daily", d_earnings),
        ("sync-sp500-constituents-weekly", d_cons),
        ("compute-hyg-lqd-daily", d_deriv),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true",
                        help="Just import deploy() functions and exit (smoke test).")
    args = parser.parse_args()

    runners = _runners()
    print(f"Found {len(runners)} flows to deploy")
    if args.once:
        for name, fn in runners:
            assert callable(fn), f"{name} deploy() not callable"
            print(f"  ok {name}")
        return 0

    procs = []
    for name, fn in runners:
        p = multiprocessing.Process(target=fn, name=name, daemon=False)
        p.start()
        procs.append(p)
        print(f"  started {name} (pid={p.pid})")
    try:
        for p in procs:
            p.join()
    except KeyboardInterrupt:
        for p in procs:
            p.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
