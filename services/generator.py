import random
from typing import List
from models.lottery_types import LotteryType, LOTTERY_CONFIGS
from models.ticket import Ticket


def generate_games(lottery_type: LotteryType, n_picks: int, n_games: int) -> List[Ticket]:
    """Generate n_games random tickets for the given lottery type."""
    config = LOTTERY_CONFIGS[lottery_type]
    games: List[Ticket] = []

    for _ in range(n_games):
        lo, hi = config.number_range

        if config.is_positional:
            # Super Sete: one digit 0-9 per column (duplicates allowed across cols)
            numbers = [random.randint(lo, hi) for _ in range(config.draw_count)]
        else:
            numbers = sorted(random.sample(range(lo, hi + 1), n_picks))

        extra = None
        lt = lottery_type
        if lt == LotteryType.TIMEMANIA:
            extra = random.randint(1, 80)
        elif lt == LotteryType.DIA_DE_SORTE:
            extra = random.randint(1, 12)
        elif lt == LotteryType.MAIS_MILIONARIA:
            extra = sorted(random.sample(range(1, 7), 2))

        games.append(Ticket.create(lt, numbers, extra=extra, label="Gerado"))

    return games
