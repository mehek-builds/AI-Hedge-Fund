"""PEAD eToro P&L tracker — run anytime to check performance.

Usage:
    python3 ~/pead_pnl.py
"""

import json, os
import yfinance as yf
from datetime import datetime

LEDGER = os.path.expanduser("~/pead_etoro_ledger.json")

with open(LEDGER) as f:
    ledger = json.load(f)

nav_start  = ledger["nav_start"]
cash       = ledger["cash_remaining"]
positions  = ledger["positions"]
today      = datetime.now().strftime("%Y-%m-%d")

print()
print("=" * 62)
print(f"PEAD PORTFOLIO SNAPSHOT — {today}")
print("=" * 62)
print(f"  Platform : eToro virtual portfolio")
print(f"  Started  : {ledger['created']}  |  NAV start: ${nav_start:,.2f}")
print()

total_value = cash
rows = []
alerts = []

for pos in positions:
    sym        = pos["ticker"]
    cost       = pos["dollar_amount"]
    entry_px   = pos["entry_price"]
    frac       = pos["approx_shares"]
    stop_pct   = pos["stop_loss_pct"]
    target_pct = pos["target_pct"]
    exit_date  = pos["target_exit_date"]

    hist = yf.Ticker(sym).history(period="1d")
    if hist.empty:
        cur_px = entry_px
    else:
        cur_px = float(hist["Close"].iloc[-1])

    cur_value = frac * cur_px
    pnl_dollar = cur_value - cost
    pnl_pct    = (cur_px - entry_px) / entry_px * 100
    total_value += cur_value

    stop_px   = entry_px * (1 + stop_pct)
    target_px = entry_px * (1 + target_pct)

    flag = ""
    if cur_px <= stop_px:
        flag = "  *** STOP HIT — EXIT IN ETORO ***"
        alerts.append(f"STOP: {sym} at ${cur_px:.2f} (stop ${stop_px:.2f})")
    elif cur_px >= target_px:
        flag = "  *** TARGET HIT — EXIT IN ETORO ***"
        alerts.append(f"TARGET: {sym} at ${cur_px:.2f} (target ${target_px:.2f})")
    elif today >= exit_date:
        flag = "  *** 60D WINDOW EXPIRED — EXIT IN ETORO ***"
        alerts.append(f"EXPIRED: {sym} past {exit_date}")

    rows.append((sym, cost, cur_value, pnl_dollar, pnl_pct, cur_px, stop_px, target_px, flag))

for sym, cost, cur_val, pnl_d, pnl_pct, cur_px, stop_px, target_px, flag in rows:
    sign = "+" if pnl_d >= 0 else ""
    print(f"  {sym:<5}  entry ${cost:>7.2f}  now ${cur_val:>7.2f}  "
          f"P&L {sign}${pnl_d:>6.2f} ({sign}{pnl_pct:.1f}%){flag}")
    print(f"         stop ${stop_px:.2f}  |  target ${target_px:.2f}  |  exit by {exit_date}")
    print()

nav_now  = total_value
nav_pnl  = nav_now - nav_start
nav_pct  = nav_pnl / nav_start * 100
sign     = "+" if nav_pnl >= 0 else ""

print(f"  Cash:             ${cash:>8.2f}")
print(f"  Portfolio value:  ${nav_now:>8.2f}")
print(f"  Total P&L:        {sign}${nav_pnl:>7.2f}  ({sign}{nav_pct:.2f}%)")
print()

if alerts:
    print("  ACTIONS NEEDED:")
    for a in alerts:
        print(f"    - {a}")
    print()

# Append snapshot to ledger
snapshot = {
    "date": today,
    "nav": round(nav_now, 2),
    "pnl_dollar": round(nav_pnl, 2),
    "pnl_pct": round(nav_pct, 2),
    "positions": [
        {"ticker": r[0], "cur_value": round(r[2], 2), "pnl_dollar": round(r[3], 2), "pnl_pct": round(r[4], 2)}
        for r in rows
    ]
}
ledger["pnl_snapshots"].append(snapshot)
with open(LEDGER, "w") as f:
    json.dump(ledger, f, indent=2)

print(f"  Snapshot saved to {LEDGER}")
print("=" * 62)
