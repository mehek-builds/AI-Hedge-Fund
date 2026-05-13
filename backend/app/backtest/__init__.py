"""Backtest engine package for Phase 6.

Provides point-in-time-correct replay of 2018-2023 using the production
signal engine and SAC ensemble. All DB queries filter ingestion_timestamp <= as_of
to prevent look-ahead bias (FR-6.1, NFR-1).
"""
