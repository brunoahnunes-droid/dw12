"""Statistical analysis of lottery draw history."""
from __future__ import annotations

import random
from typing import Dict, List

from models.lottery_types import LotteryType, LOTTERY_CONFIGS
from models.ticket import DrawResult


def number_frequency(draws: List[DrawResult], lt: LotteryType) -> Dict[int, int]:
    """Return per-number occurrence count for a lottery type across all saved draws."""
    cfg = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    freq: Dict[int, int] = {n: 0 for n in range(lo, hi + 1)}
    for d in draws:
        if d.lottery_type != lt:
            continue
        for n in d.numbers:
            if n in freq:
                freq[n] += 1
        if d.numbers2:
            for n in d.numbers2:
                if n in freq:
                    freq[n] += 1
    return freq


def hot_numbers(freq: Dict[int, int], n: int) -> List[int]:
    return [k for k, _ in sorted(freq.items(), key=lambda x: -x[1])[:n]]


def cold_numbers(freq: Dict[int, int], n: int) -> List[int]:
    return [k for k, _ in sorted(freq.items(), key=lambda x: x[1])[:n]]


def chart_data(freq: Dict[int, int]) -> dict:
    """Prepare data for a Chart.js bar chart."""
    nums = sorted(freq.keys())
    values = [freq[n] for n in nums]
    mx = max(values) if values else 1
    colors = []
    for v in values:
        pct = v / mx if mx else 0
        if pct >= 0.75:
            colors.append("rgba(245,166,35,0.85)")   # hot – gold
        elif pct <= 0.25:
            colors.append("rgba(59,130,246,0.85)")   # cold – blue
        else:
            colors.append("rgba(74,85,104,0.70)")    # neutral
    return {
        "labels": [str(n) for n in nums],
        "data": values,
        "colors": colors,
    }


def weighted_picks(pool: List[int], weights: List[float], k: int) -> List[int]:
    """Pick k unique numbers from pool using per-number weights (without replacement)."""
    if k >= len(pool):
        return sorted(pool[:k])
    selected: List[int] = []
    remaining = list(zip(pool, weights))
    while len(selected) < k and remaining:
        total = sum(w for _, w in remaining)
        if total <= 0:
            # Fallback: uniform random
            break
        r = random.uniform(0, total)
        cumsum = 0.0
        for i, (num, w) in enumerate(remaining):
            cumsum += w
            if r <= cumsum:
                selected.append(num)
                remaining.pop(i)
                break
    # fill any shortage with uniform random
    if len(selected) < k:
        leftover = [n for n, _ in remaining]
        random.shuffle(leftover)
        selected.extend(leftover[: k - len(selected)])
    return sorted(selected)
