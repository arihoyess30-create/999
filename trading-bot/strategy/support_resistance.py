"""Support and resistance detection using swing pivots and zone clustering."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Zone:
    low: float
    high: float
    center: float
    touches: int
    kind: str

    def contains(self, price: float) -> bool:
        return self.low <= price <= self.high


class SupportResistanceDetector:
    def __init__(self, pivot_window: int, zone_tolerance: float, min_touches: int, max_zones_each_side: int):
        self.pivot_window = pivot_window
        self.zone_tolerance = zone_tolerance
        self.min_touches = min_touches
        self.max_zones_each_side = max_zones_each_side

    def detect(self, df: pd.DataFrame) -> tuple[list[Zone], list[Zone]]:
        lows = self._find_pivot_lows(df)
        highs = self._find_pivot_highs(df)

        support = self._cluster_levels(lows, "support")
        resistance = self._cluster_levels(highs, "resistance")
        return support, resistance

    def _find_pivot_lows(self, df: pd.DataFrame) -> list[float]:
        vals = df["low"].to_numpy()
        pivots = []
        for i in range(self.pivot_window, len(vals) - self.pivot_window):
            cur = vals[i]
            window = vals[i - self.pivot_window:i + self.pivot_window + 1]
            if cur == np.min(window):
                pivots.append(float(cur))
        return pivots

    def _find_pivot_highs(self, df: pd.DataFrame) -> list[float]:
        vals = df["high"].to_numpy()
        pivots = []
        for i in range(self.pivot_window, len(vals) - self.pivot_window):
            cur = vals[i]
            window = vals[i - self.pivot_window:i + self.pivot_window + 1]
            if cur == np.max(window):
                pivots.append(float(cur))
        return pivots

    def _cluster_levels(self, levels: list[float], kind: str) -> list[Zone]:
        if not levels:
            return []

        levels = sorted(levels)
        clusters: list[list[float]] = [[levels[0]]]

        for level in levels[1:]:
            cluster_mean = float(np.mean(clusters[-1]))
            if abs(level - cluster_mean) <= self.zone_tolerance:
                clusters[-1].append(level)
            else:
                clusters.append([level])

        zones: list[Zone] = []
        for cluster in clusters:
            touches = len(cluster)
            if touches < self.min_touches:
                continue
            center = float(np.mean(cluster))
            low = center - self.zone_tolerance
            high = center + self.zone_tolerance
            zones.append(Zone(low=low, high=high, center=center, touches=touches, kind=kind))

        zones.sort(key=lambda z: z.touches, reverse=True)
        return zones[: self.max_zones_each_side]
