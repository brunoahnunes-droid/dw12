"""Análise de pares de números que saem juntos com frequência."""
from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Dict, List, Tuple

from models.lottery_types import LotteryType, LOTTERY_CONFIGS
from models.ticket import DrawResult


def pair_frequency(draws: List[DrawResult], lt: LotteryType) -> Dict[Tuple[int,int], int]:
    """Conta quantas vezes cada par de números saiu junto."""
    freq: Dict[Tuple[int,int], int] = defaultdict(int)
    for d in draws:
        if d.lottery_type != lt:
            continue
        nums = sorted(d.numbers)
        for a, b in combinations(nums, 2):
            freq[(a, b)] += 1
        if d.numbers2:
            nums2 = sorted(d.numbers2)
            for a, b in combinations(nums2, 2):
                freq[(a, b)] += 1
    return dict(freq)


def top_pairs(freq: Dict[Tuple[int,int], int], n: int = 20) -> List[Tuple[Tuple[int,int], int]]:
    """Retorna os N pares mais frequentes."""
    return sorted(freq.items(), key=lambda x: -x[1])[:n]


def bottom_pairs(freq: Dict[Tuple[int,int], int], n: int = 20) -> List[Tuple[Tuple[int,int], int]]:
    """Retorna os N pares menos frequentes."""
    return sorted(freq.items(), key=lambda x: x[1])[:n]


def number_affinity(freq: Dict[Tuple[int,int], int], number: int) -> List[Tuple[int, int]]:
    """Retorna os números que mais saem junto com `number`, ordenado por freq desc."""
    result = []
    for (a, b), cnt in freq.items():
        if a == number:
            result.append((b, cnt))
        elif b == number:
            result.append((a, cnt))
    return sorted(result, key=lambda x: -x[1])
