"""Genetic algorithm generator for lottery number combinations."""
from __future__ import annotations

import random
from typing import Dict, List

from models.lottery_types import LotteryType, LOTTERY_CONFIGS


def generate_genetic(
    lt: LotteryType,
    n_picks: int,
    n_games: int,
    freq: Dict[int, int],
    generations: int = 50,
    pop_size: int = 160,
) -> List[List[int]]:
    """
    Return up to n_games combinations optimised by historical number frequencies.
    Uses a simple genetic algorithm: selection + crossover + mutation.
    """
    cfg = LOTTERY_CONFIGS[lt]
    lo, hi = cfg.number_range
    pool = list(range(lo, hi + 1))
    weight_map = {n: max(freq.get(n, 1), 1) for n in pool}
    weights = [weight_map[n] for n in pool]

    def random_ind() -> List[int]:
        chosen: set[int] = set()
        attempts = 0
        while len(chosen) < n_picks and attempts < 3000:
            chosen.add(random.choices(pool, weights=weights, k=1)[0])
            attempts += 1
        if len(chosen) < n_picks:
            leftover = [n for n in pool if n not in chosen]
            random.shuffle(leftover)
            chosen.update(leftover[: n_picks - len(chosen)])
        return sorted(chosen)

    def fitness(ind: List[int]) -> float:
        return sum(weight_map.get(n, 0) for n in ind)

    def crossover(p1: List[int], p2: List[int]) -> List[int]:
        merged = list({*p1, *p2})
        random.shuffle(merged)
        child = merged[:n_picks]
        if len(child) < n_picks:
            extra = [n for n in pool if n not in child]
            random.shuffle(extra)
            child.extend(extra[: n_picks - len(child)])
        return sorted(child[:n_picks])

    def mutate(ind: List[int]) -> List[int]:
        ind = ind[:]
        idx = random.randrange(len(ind))
        others = [n for n in pool if n not in ind]
        if not others:
            return ind
        other_w = [weight_map[n] for n in others]
        ind[idx] = random.choices(others, weights=other_w, k=1)[0]
        return sorted(ind)

    population = [random_ind() for _ in range(pop_size)]

    for _ in range(generations):
        population.sort(key=fitness, reverse=True)
        elite_n = max(pop_size // 4, 4)
        elite = population[:elite_n]
        new_pop = elite[:]
        while len(new_pop) < pop_size:
            p1 = random.choice(elite[:min(20, elite_n)])
            p2 = random.choice(elite[:min(20, elite_n)])
            child = crossover(p1, p2)
            if random.random() < 0.25:
                child = mutate(child)
            if len(child) == n_picks:
                new_pop.append(child)
        population = new_pop

    population.sort(key=fitness, reverse=True)
    seen: set[tuple] = set()
    result: List[List[int]] = []
    for ind in population:
        key = tuple(ind)
        if key not in seen and len(ind) == n_picks:
            seen.add(key)
            result.append(ind)
        if len(result) >= n_games:
            break

    while len(result) < n_games:
        result.append(random_ind())

    return result[:n_games]
