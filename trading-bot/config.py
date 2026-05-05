"""Central configuration for the MT5 support/resistance trading bot."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path

import MetaTrader5 as mt5


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE = DATA_DIR / "bot.log"


@dataclass(frozen=True)
class MT5Config:
    login: int | None = None
    password: str | None = None
    server: str | None = None
    path: str | None = None
    symbol: str = "XAUUSDm"
    timeframe: int = mt5.TIMEFRAME_M5
    candles_lookback: int = 350


@dataclass(frozen=True)
class StrategyConfig:
    pivot_window: int = 12
    zone_merge_tolerance_points: int = 250
    zone_min_touches: int = 2
    max_zones_each_side: int = 4
    confirmation_body_ratio: float = 0.55


@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct: float = 1.0
    min_risk_reward: float = 2.0
    sl_buffer_points: int = 80
    max_spread_points: int = 80
    deviation_points: int = 20


@dataclass(frozen=True)
class RuntimeConfig:
    poll_interval_seconds: int = 60
    magic_number: int = 260505
    enable_time_filter: bool = False
    blocked_hours_utc: tuple[time, time] = (time(12, 25), time(13, 10))


MT5 = MT5Config()
STRATEGY = StrategyConfig()
RISK = RiskConfig()
RUNTIME = RuntimeConfig()
