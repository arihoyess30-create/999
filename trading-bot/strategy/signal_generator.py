"""Signal generation from support/resistance zones and candle confirmations."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategy.support_resistance import Zone


@dataclass(frozen=True)
class Signal:
    side: str
    zone: Zone
    reason: str


class SignalGenerator:
    def __init__(self, confirmation_body_ratio: float = 0.55):
        self.confirmation_body_ratio = confirmation_body_ratio

    def generate(self, candles: pd.DataFrame, support_zones: list[Zone], resistance_zones: list[Zone]) -> Signal | None:
        if len(candles) < 2:
            return None

        c1 = candles.iloc[-2]
        c2 = candles.iloc[-1]
        last_low = float(c2["low"])
        last_high = float(c2["high"])

        for zone in support_zones:
            if zone.low <= last_low <= zone.high and self._is_bullish_confirmation(c1, c2):
                return Signal("buy", zone, "Support touch + bullish confirmation")

        for zone in resistance_zones:
            if zone.low <= last_high <= zone.high and self._is_bearish_confirmation(c1, c2):
                return Signal("sell", zone, "Resistance touch + bearish confirmation")

        return None

    def _is_bullish_confirmation(self, prev: pd.Series, cur: pd.Series) -> bool:
        engulfing = prev["close"] < prev["open"] and cur["close"] > cur["open"] and cur["close"] > prev["open"]
        rejection = self._strong_body(cur) and cur["close"] > cur["open"] and self._lower_wick(cur) > self._body(cur)
        return bool(engulfing or rejection)

    def _is_bearish_confirmation(self, prev: pd.Series, cur: pd.Series) -> bool:
        engulfing = prev["close"] > prev["open"] and cur["close"] < cur["open"] and cur["close"] < prev["open"]
        rejection = self._strong_body(cur) and cur["close"] < cur["open"] and self._upper_wick(cur) > self._body(cur)
        return bool(engulfing or rejection)

    def _strong_body(self, candle: pd.Series) -> bool:
        rng = max(float(candle["high"] - candle["low"]), 1e-6)
        return self._body(candle) / rng >= self.confirmation_body_ratio

    @staticmethod
    def _body(candle: pd.Series) -> float:
        return abs(float(candle["close"] - candle["open"]))

    @staticmethod
    def _lower_wick(candle: pd.Series) -> float:
        return min(float(candle["open"]), float(candle["close"])) - float(candle["low"])

    @staticmethod
    def _upper_wick(candle: pd.Series) -> float:
        return float(candle["high"]) - max(float(candle["open"]), float(candle["close"]))
