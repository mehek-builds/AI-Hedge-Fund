---
status: partial
phase: 03-signal-engine
source: [03-VERIFICATION.md]
started: 2026-05-03T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Test

[awaiting human testing — requires live TimescaleDB]

## Tests

### 1. DB integration — qualifying signal writes row
expected: run_signal_pipeline() with valid AAPL earnings event writes exactly 1 row to signals table with naive_position_size=0.0200 and direction='long'
result: [pending]

### 2. DB integration — sector hurdle suppression
expected: run_signal_pipeline() with MSFT event where quality_score < 60 returns None and writes 0 rows to signals
result: [pending]

### 3. DB integration — ROIC<WACC suppression
expected: run_signal_pipeline() with event where operating_income/(revenue*0.4) < 0.10 returns None and writes 0 rows
result: [pending]

### 4. Performance benchmark (FR-3.7)
expected: compute_signal_for_event() completes in < 5.0 seconds wall-clock for one earnings event against live DB
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
