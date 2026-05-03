"""Alpaca client wrapper using alpaca-py SDK."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from loguru import logger

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ---------------------------------------------------------------------------
# Alpaca client singleton
# ---------------------------------------------------------------------------


class AlpacaClient:
    """Thin wrapper around alpaca-py for PEAD trading operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self._api_key = api_key or os.environ["ALPACA_API_KEY"]
        self._secret_key = secret_key or os.environ["ALPACA_SECRET_KEY"]
        paper = "paper" in (base_url or os.environ.get("ALPACA_BASE_URL", "paper")).lower()

        self._trading = TradingClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=paper,
        )
        self._data = StockHistoricalDataClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
        )
        logger.info(f"AlpacaClient initialized (paper={paper})")

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def get_account(self) -> dict:
        """Return NAV, buying_power, equity, and cash from Alpaca account."""
        acct = self._trading.get_account()
        return {
            "id": str(acct.id),
            "status": acct.status,
            "equity": float(acct.equity or 0),
            "last_equity": float(acct.last_equity or 0),
            "nav": float(acct.portfolio_value or acct.equity or 0),
            "cash": float(acct.cash or 0),
            "buying_power": float(acct.buying_power or 0),
            "daytrade_count": int(acct.daytrade_count or 0),
        }

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    def get_positions(self) -> list[dict]:
        """Return all open positions."""
        positions = self._trading.get_all_positions()
        result = []
        for p in positions:
            result.append(
                {
                    "symbol": p.symbol,
                    "qty": float(p.qty or 0),
                    "side": p.side.value if hasattr(p.side, "value") else str(p.side),
                    "market_value": float(p.market_value or 0),
                    "avg_entry_price": float(p.avg_entry_price or 0),
                    "current_price": float(p.current_price or 0),
                    "unrealized_pl": float(p.unrealized_pl or 0),
                    "unrealized_plpc": float(p.unrealized_plpc or 0),
                    "cost_basis": float(p.cost_basis or 0),
                    "asset_id": str(p.asset_id),
                }
            )
        return result

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
    ) -> dict:
        """Submit a market order and return the created order as a dict."""
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        request = MarketOrderRequest(
            symbol=symbol.upper(),
            qty=qty,
            side=side_enum,
            time_in_force=TimeInForce.DAY,
        )
        order = self._trading.submit_order(request)
        logger.info(f"Order submitted: {side.upper()} {qty} {symbol} → {order.id}")
        return self._order_to_dict(order)

    def close_position(self, symbol: str) -> dict:
        """Close an entire position for the given symbol."""
        order = self._trading.close_position(symbol.upper())
        logger.info(f"Position closed: {symbol} → order {order.id}")
        return self._order_to_dict(order)

    def get_orders(self, status: str = "all", limit: int = 50) -> list[dict]:
        """Return recent orders."""
        status_map = {
            "all": QueryOrderStatus.ALL,
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
        }
        request = GetOrdersRequest(
            status=status_map.get(status, QueryOrderStatus.ALL),
            limit=limit,
        )
        orders = self._trading.get_orders(filter=request)
        return [self._order_to_dict(o) for o in orders]

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def get_bars(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Fetch OHLCV bars and return as a DataFrame indexed by timestamp."""
        tf_map = {
            "1Day": TimeFrame.Day,
            "1Hour": TimeFrame.Hour,
            "1Min": TimeFrame.Minute,
        }
        tf = tf_map.get(timeframe, TimeFrame.Day)
        request = StockBarsRequest(
            symbol_or_symbols=symbol.upper(),
            start=start,
            end=end,
            timeframe=tf,
        )
        bars = self._data.get_stock_bars(request)
        df = bars.df
        if df.empty:
            return pd.DataFrame()
        # Flatten multi-index if present
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol.upper(), level="symbol")
        return df

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _order_to_dict(order) -> dict:
        return {
            "id": str(order.id),
            "client_order_id": str(order.client_order_id) if order.client_order_id else None,
            "symbol": order.symbol,
            "side": order.side.value if hasattr(order.side, "value") else str(order.side),
            "qty": str(order.qty) if order.qty else None,
            "filled_qty": str(order.filled_qty) if order.filled_qty else None,
            "type": order.type.value if hasattr(order.type, "value") else str(order.type),
            "status": order.status.value if hasattr(order.status, "value") else str(order.status),
            "submitted_at": order.submitted_at.isoformat() if order.submitted_at else None,
            "filled_at": order.filled_at.isoformat() if order.filled_at else None,
            "filled_avg_price": str(order.filled_avg_price) if order.filled_avg_price else None,
        }


# Module-level singleton — constructed lazily on first use
_client: Optional[AlpacaClient] = None


def get_alpaca_client() -> AlpacaClient:
    global _client
    if _client is None:
        _client = AlpacaClient()
    return _client
