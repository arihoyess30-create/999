"""Entry point for support/resistance MT5 trading bot."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from config import LOG_FILE, MT5, RISK, RUNTIME, STRATEGY
from execution.mt5_connector import MT5Connector, OrderParams
from execution.trade_manager import TradeManager
from strategy.signal_generator import SignalGenerator
from strategy.support_resistance import SupportResistanceDetector
from utils.logger import get_logger


def within_blocked_time() -> bool:
    if not RUNTIME.enable_time_filter:
        return False
    start, end = RUNTIME.blocked_hours_utc
    now = datetime.now(timezone.utc).time()
    return start <= now <= end


def run() -> None:
    logger = get_logger("trading_bot", LOG_FILE)
    connector = MT5Connector(logger)
    detector = None
    signal_gen = SignalGenerator(STRATEGY.confirmation_body_ratio)
    trade_manager = TradeManager(connector, MT5, RISK, RUNTIME, logger)

    try:
        connector.connect(MT5.login, MT5.password, MT5.server, MT5.path)
        connector.ensure_symbol(MT5.symbol)
        symbol_info = connector.get_symbol_info(MT5.symbol)
        detector = SupportResistanceDetector(
            pivot_window=STRATEGY.pivot_window,
            zone_tolerance=STRATEGY.zone_merge_tolerance_points * symbol_info.point,
            min_touches=STRATEGY.zone_min_touches,
            max_zones_each_side=STRATEGY.max_zones_each_side,
        )

        while True:
            try:
                if within_blocked_time():
                    logger.info("Skipping cycle due to time filter")
                    time.sleep(RUNTIME.poll_interval_seconds)
                    continue

                candles = connector.get_rates(MT5.symbol, MT5.timeframe, MT5.candles_lookback)
                supports, resistances = detector.detect(candles)
                signal = signal_gen.generate(candles, supports, resistances)

                if signal is None:
                    logger.info("No signal | supports=%d resistances=%d", len(supports), len(resistances))
                elif trade_manager.has_open_position():
                    logger.info("Signal ignored: open position exists | reason=%s", signal.reason)
                elif trade_manager.should_skip_duplicate_zone(signal.zone):
                    logger.info("Signal ignored: duplicate zone | side=%s zone=%.3f", signal.side, signal.zone.center)
                elif not trade_manager.spread_ok():
                    logger.info("Signal ignored: spread filter blocked")
                else:
                    plan = trade_manager.build_plan(signal, supports, resistances)
                    logger.info(
                        "Signal accepted | side=%s entry=%.3f sl=%.3f tp=%.3f reason=%s",
                        plan.side,
                        plan.entry,
                        plan.stop_loss,
                        plan.take_profit,
                        plan.reason,
                    )
                    params = OrderParams(
                        symbol=MT5.symbol,
                        side=plan.side,
                        volume=plan.volume,
                        stop_loss=plan.stop_loss,
                        take_profit=plan.take_profit,
                        deviation=RISK.deviation_points,
                        magic=RUNTIME.magic_number,
                        comment=plan.reason,
                    )
                    connector.send_market_order(params)
                    trade_manager.mark_zone_traded(plan.zone_center)

            except Exception as cycle_error:
                logger.exception("Cycle error: %s", cycle_error)

            time.sleep(RUNTIME.poll_interval_seconds)

    finally:
        connector.shutdown()
        logger.info("Bot stopped")


if __name__ == "__main__":
    run()
