---
status: partial
phase: 04-portfolio-architecture
source: [04-VERIFICATION.md]
started: 2026-05-03T00:00:00Z
updated: 2026-05-03T00:00:00Z
---

## Current Test

[awaiting human clarification + DB testing]

## Tests

### 1. Macro score storage intent clarification
expected: ROADMAP SC-1 says composite score "stored in macro_indicators" — confirm whether this means (a) raw input series are in macro_indicators (Phase 2 delivers this, DONE) OR (b) computed integer score must be persisted to a new column in that table (not implemented)
result: [pending — author clarification needed]

### 2. DB integration — end-to-end portfolio sizing
expected: compute_portfolio_size_task runs against live DB with valid signal, macro_loader reads macro_indicators, PositionSizingResult returned with final_size > 0
result: [pending — requires DATABASE_URL_SYNC]

### 3. DB integration — Mag-7 cap fires and is logged
expected: AAPL signal with naive_size > 0.03 → final_size == 0.03, log contains "MAG7 cap applied"
result: [pending — requires DATABASE_URL_SYNC]

### 4. DB integration — stop-loss triggers at exactly 8%
expected: current_price 8% below entry → stop_loss_triggered == True in result
result: [pending — requires DATABASE_URL_SYNC]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
