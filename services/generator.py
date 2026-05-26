import random
from typing import Dict, List, Optional

from models.lottery_types import LotteryType, LOTTERY_CONFIGS
from models.ticket import Ticket


def _gen_extra(lt: LotteryType):
    if lt == LotteryType.TIMEMANIA:
        return random.randint(1, 80)
    if lt == LotteryType.DIA_DE_SORTE:
        return random.randint(1, 12)
    if lt == LotteryType.MAIS_MILIONARIA:
        return sorted(random.sample(range(1, 7), 2))
    return None


def generate_games(
    lottery_type: LotteryType,
    n_picks: int,
    n_games: int,
    strategy: str = "random",
    freq: Optional[Dict[int, int]] = None,
) -> List[Ticket]:
    """Generate n_games tickets.
    strategy: 'random' | 'hot' | 'cold' | 'balanced' | 'genetic'
    freq: dict[number → occurrence count], required for non-random strategies.
    """
    config = LOTTERY_CONFIGS[lottery_type]
    lo, hi = config.number_range
    pool = list(range(lo, hi + 1))

    has_history = freq and sum(freq.values()) > 0

    # Genetic strategy: delegate entirely to the GA module
    if strategy == "genetic" and has_history and not config.is_positional:
        from services.genetic import generate_genetic
        numbers_list = generate_genetic(
            lottery_type, n_picks, min(n_games, 100), freq,
            generations=40, pop_size=120,
        )
        tickets = []
        for nums in numbers_list:
            tickets.append(Ticket.create(lottery_type, nums,
                                         extra=_gen_extra(lottery_type),
                                         label="Genético"))
        return tickets

    label_map = {
        "hot": "Quente", "cold": "Frio",
        "balanced": "Balanceado", "genetic": "Gerado",
    }
    label = label_map.get(strategy, "Gerado")

    def pick_numbers() -> List[int]:
        if config.is_positional:
            return [random.randint(lo, hi) for _ in range(config.draw_count)]

        if not has_history or strategy == "random":
            return sorted(random.sample(pool, n_picks))

        max_f = max(freq.values()) + 1
        avg = sum(freq.values()) / len(freq)

        if strategy == "hot":
            weights = [max(freq.get(n, 1), 1) for n in pool]
        elif strategy == "cold":
            weights = [max(max_f - freq.get(n, 0), 1) for n in pool]
        elif strategy == "balanced":
            weights = [max(avg - abs(freq.get(n, 0) - avg) + 1, 1) for n in pool]
        else:
            return sorted(random.sample(pool, n_picks))

        from services.statistics import weighted_picks
        return weighted_picks(pool, weights, n_picks)

    games: List[Ticket] = []
    for _ in range(n_games):
        games.append(Ticket.create(lottery_type, pick_numbers(),
                                   extra=_gen_extra(lottery_type),
                                   label=label))
    return games
