---
status: partial
phase: 02-data-pipelines
source: [02-VERIFICATION.md]
started: 2026-05-03T09:00:00Z
updated: 2026-05-03T09:00:00Z
---

## Current Test

[awaiting human testing — requires Docker stack]

## Tests

### 1. Prefect dashboard shows all 6 scheduled deployments
expected: http://localhost:4200 Deployments view lists ingest-prices-daily, ingest-macro-daily, ingest-ff5-weekly, ingest-earnings-daily, sync-sp500-constituents-weekly, compute-hyg-lqd-daily
result: [pending]

### 2. sp500_constituents table populates after live scrape
expected: SELECT count(*) FROM sp500_constituents > 400 after running sync_sp500_constituents_weekly
result: [pending]

### 3. price_bars table populates after live Alpaca run
expected: SELECT count(*) FROM price_bars > 0 after running ingest_prices_daily
result: [pending]

### 4. macro_indicators populates with FRED data
expected: SELECT count(*) FROM macro_indicators > 0 with 7 distinct series_ids after ingest_macro_daily
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 4

## Gaps

Blocked by: Docker Desktop daemon returning 500 errors — requires Docker restart/reinstall before live testing can proceed.
