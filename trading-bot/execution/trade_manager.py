"""Risk management and execution guardrails."""
from __future__ import annotations

from dataclasses import dataclass

from strategy.signal_generator import Signal
from strategy.support_resistance import Zone


@dataclass
class TradePlan:
    side: str
    volume: float
    entry: float
    stop_loss: float
    take_profit: float
    reason: str
    zone_center: float


class TradeManager:
    def __init__(self, connector, cfg_mt5, cfg_risk, cfg_runtime, logger):
        self.connector = connector
        self.cfg_mt5 = cfg_mt5
        self.cfg_risk = cfg_risk
        self.cfg_runtime = cfg_runtime
        self.logger = logger
        self.last_trade_zone: float | None = None

    def has_open_position(self) -> bool:
        return len(self.connector.get_open_positions(self.cfg_mt5.symbol)) > 0

    def spread_ok(self) -> bool:
        tick = self.connector.get_tick(self.cfg_mt5.symbol)
        symbol_info = self.connector.get_symbol_info(self.cfg_mt5.symbol)
        points = (tick.ask - tick.bid) / symbol_info.point
        return points <= self.cfg_risk.max_spread_points

    def should_skip_duplicate_zone(self, zone: Zone) -> bool:
        return self.last_trade_zone is not None and abs(zone.center - self.last_trade_zone) < 1e-6

    def build_plan(self, signal: Signal, supports: list[Zone], resistances: list[Zone]) -> TradePlan:
        tick = self.connector.get_tick(self.cfg_mt5.symbol)
        symbol_info = self.connector.get_symbol_info(self.cfg_mt5.symbol)
        entry = tick.ask if signal.side == "buy" else tick.bid
        point = symbol_info.point

        if signal.side == "buy":
            sl = signal.zone.low - self.cfg_risk.sl_buffer_points * point
            tp_candidate = self._next_zone_target(entry, resistances, above=True)
        else:
            sl = signal.zone.high + self.cfg_risk.sl_buffer_points * point
            tp_candidate = self._next_zone_target(entry, supports, above=False)

        risk_distance = abs(entry - sl)
        rr_tp = entry + self.cfg_risk.min_risk_reward * risk_distance if signal.side == "buy" else entry - self.cfg_risk.min_risk_reward * risk_distance

        if tp_candidate is None:
            tp = rr_tp
        else:
            tp = max(tp_candidate, rr_tp) if signal.side == "buy" else min(tp_candidate, rr_tp)

        volume = self._calc_position_size(entry, sl)
        return TradePlan(signal.side, volume, entry, sl, tp, signal.reason, signal.zone.center)

    def _calc_position_size(self, entry: float, stop_loss: float) -> float:
        account = self.connector.get_account_info()
        symbol_info = self.connector.get_symbol_info(self.cfg_mt5.symbol)

        risk_money = account.balance * (self.cfg_risk.risk_per_trade_pct / 100)
        distance = abs(entry - stop_loss)
        if distance <= 0:
            return symbol_info.volume_min

        tick_value = symbol_info.trade_tick_value or 1.0
        tick_size = symbol_info.trade_tick_size or symbol_info.point
        risk_per_lot = (distance / tick_size) * tick_value
        raw_lot = risk_money / max(risk_per_lot, 1e-6)

        volume = max(symbol_info.volume_min, min(raw_lot, symbol_info.volume_max))
        step = symbol_info.volume_step
        volume = round(volume / step) * step
        return float(max(symbol_info.volume_min, volume))

    @staticmethod
    def _next_zone_target(entry: float, zones: list[Zone], above: bool) -> float | None:
        centers = sorted(zone.center for zone in zones)
        if above:
            for c in centers:
                if c > entry:
                    return c
        else:
            for c in reversed(centers):
                if c < entry:
                    return c
        return None

    def mark_zone_traded(self, zone_center: float) -> None:
        self.last_trade_zone = zone_center
