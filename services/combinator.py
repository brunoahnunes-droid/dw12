"""Combinatorial game generator (desdobramento) with moldura/miolo classification."""
from __future__ import annotations

import math
import random
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from models.lottery_types import LotteryType, LOTTERY_CONFIGS

# Number of columns per row on the physical lottery card
_COLS: Dict[LotteryType, int] = {
    LotteryType.MEGA_SENA:        10,
    LotteryType.QUINA:            10,
    LotteryType.LOTOFACIL:         5,
    LotteryType.LOTOMANIA:        10,
    LotteryType.TIMEMANIA:        10,
    LotteryType.DUPLA_SENA:       10,
    LotteryType.DIA_DE_SORTE:      8,
    LotteryType.SUPER_SETE:        7,
    LotteryType.MAIS_MILIONARIA:  10,
}

MAX_COMBOS = 5_000   # cap on combinations held in memory


def grid_cols(lt: LotteryType) -> int:
    return _COLS.get(lt, 10)


def compute_moldura(lt: LotteryType) -> Tuple[Set[int], Set[int]]:
    """Return (moldura_set, miolo_set) based on the card's border/center split."""
    cfg  = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    cols = grid_cols(lt)
    all_nums = list(range(lo, hi + 1))
    rows = math.ceil(len(all_nums) / cols)

    def cell(r: int, c: int) -> Optional[int]:
        i = r * cols + c
        return all_nums[i] if i < len(all_nums) else None

    moldura: Set[int] = set()
    for r in range(rows):
        for c in range(cols):
            n = cell(r, c)
            if n is None:
                continue
            if r == 0 or r == rows - 1 or c == 0 or c == cols - 1:
                moldura.add(n)

    return moldura, set(all_nums) - moldura


def build_grid(lt: LotteryType) -> List[List[Optional[int]]]:
    """Return numbers as a 2-D grid matching the card layout."""
    cfg = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    cols = grid_cols(lt)
    all_nums = list(range(lo, hi + 1))
    rows = math.ceil(len(all_nums) / cols)
    grid: List[List[Optional[int]]] = []
    for r in range(rows):
        row: List[Optional[int]] = []
        for c in range(cols):
            i = r * cols + c
            row.append(all_nums[i] if i < len(all_nums) else None)
        grid.append(row)
    return grid


def combine(
    numbers: List[int],
    k: int,
    max_games: Optional[int] = None,
) -> Tuple[List[Tuple[int, ...]], int, bool]:
    """
    Generate combinations of `numbers` taken `k` at a time.
    Returns (combos, total_possible, truncated).
    """
    sorted_nums = sorted(numbers)
    total = math.comb(len(sorted_nums), k)
    limit = min(max_games or MAX_COMBOS, MAX_COMBOS)

    if total <= limit:
        return list(combinations(sorted_nums, k)), total, False

    # Random sampling when total > limit
    seen: set = set()
    out: List[Tuple[int, ...]] = []
    max_attempts = limit * 30
    attempts = 0
    while len(out) < limit and attempts < max_attempts:
        c = tuple(sorted(random.sample(sorted_nums, k)))
        if c not in seen:
            seen.add(c)
            out.append(c)
        attempts += 1

    return out, total, True


def apply_moldura_filter(
    combos: List[Tuple[int, ...]],
    moldura: Set[int],
    min_m: int,
    max_m: int,
) -> List[Tuple[int, ...]]:
    return [c for c in combos if min_m <= len(set(c) & moldura) <= max_m]


def combo_stats(combo: Tuple[int, ...], moldura: Set[int]) -> Tuple[int, int]:
    """Return (n_moldura, n_miolo) for a combo."""
    m = len(set(combo) & moldura)
    return m, len(combo) - m
