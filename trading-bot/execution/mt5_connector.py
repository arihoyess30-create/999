"""MetaTrader 5 connector and low-level request helpers."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import MetaTrader5 as mt5
import pandas as pd


@dataclass
class OrderParams:
    symbol: str
    side: str
    volume: float
    stop_loss: float
    take_profit: float
    deviation: int
    magic: int
    comment: str


class MT5Connector:
    def __init__(self, logger):
        self.logger = logger

    def connect(self, login: int | None = None, password: str | None = None, server: str | None = None, path: str | None = None) -> None:
        kwargs: dict[str, Any] = {}
        if login:
            kwargs["login"] = login
        if password:
            kwargs["password"] = password
        if server:
            kwargs["server"] = server
        if path:
            kwargs["path"] = path

        if not mt5.initialize(**kwargs):
            code, msg = mt5.last_error()
            raise RuntimeError(f"MT5 initialization failed: {code} {msg}")

        self.logger.info("Connected to MT5 terminal")

    def shutdown(self) -> None:
        mt5.shutdown()

    def ensure_symbol(self, symbol: str) -> None:
        info = mt5.symbol_info(symbol)
        if info is None:
            raise ValueError(f"Symbol not found: {symbol}")
        if not info.visible and not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Unable to select symbol: {symbol}")

    def get_rates(self, symbol: str, timeframe: int, count: int) -> pd.DataFrame:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError("No rates returned from MT5")

        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        return df


    def get_symbol_info(self, symbol: str):
        info = mt5.symbol_info(symbol)
        if info is None:
            raise RuntimeError(f"Unable to get symbol info for {symbol}")
        return info

    def get_tick(self, symbol: str):
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            raise RuntimeError("Failed to fetch live tick")
        return tick

    def get_account_info(self):
        account = mt5.account_info()
        if account is None:
            raise RuntimeError("Unable to get account information")
        return account

    def get_open_positions(self, symbol: str):
        positions = mt5.positions_get(symbol=symbol)
        return [] if positions is None else list(positions)

    def send_market_order(self, params: OrderParams):
        side = params.side.lower()
        tick = self.get_tick(params.symbol)
        order_type = mt5.ORDER_TYPE_BUY if side == "buy" else mt5.ORDER_TYPE_SELL
        price = tick.ask if side == "buy" else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": params.symbol,
            "volume": params.volume,
            "type": order_type,
            "price": price,
            "sl": params.stop_loss,
            "tp": params.take_profit,
            "deviation": params.deviation,
            "magic": params.magic,
            "comment": params.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is None:
            raise RuntimeError("order_send returned None")

        if result.retcode != mt5.TRADE_RETCODE_DONE:
            raise RuntimeError(f"Order failed retcode={result.retcode} comment={result.comment}")

        self.logger.info(
            "Order placed | side=%s volume=%.2f price=%.3f sl=%.3f tp=%.3f ticket=%s",
            side,
            params.volume,
            price,
            params.stop_loss,
            params.take_profit,
            result.order,
        )
        return result
