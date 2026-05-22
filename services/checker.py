from dataclasses import dataclass, field
from typing import List, Optional
from models.lottery_types import LotteryType, LotteryConfig, PrizeTier, LOTTERY_CONFIGS
from models.ticket import Ticket, DrawResult


@dataclass
class CheckResult:
    ticket: Ticket
    draw: DrawResult
    matches: int
    matched_numbers: List[int]
    extra_matches: int = 0
    prize_tier: Optional[PrizeTier] = None
    # Dupla-Sena only
    matches2: int = 0
    matched_numbers2: List[int] = field(default_factory=list)
    prize_tier2: Optional[PrizeTier] = None

    @property
    def is_winner(self) -> bool:
        return self.prize_tier is not None or self.prize_tier2 is not None

    @property
    def best_prize(self) -> Optional[PrizeTier]:
        if self.prize_tier and self.prize_tier2:
            return (self.prize_tier
                    if self.prize_tier.min_matches >= self.prize_tier2.min_matches
                    else self.prize_tier2)
        return self.prize_tier or self.prize_tier2


def check_ticket(ticket: Ticket, draw: DrawResult) -> CheckResult:
    config = LOTTERY_CONFIGS[ticket.lottery_type]
    lt = ticket.lottery_type

    if lt == LotteryType.SUPER_SETE:
        return _check_super_sete(ticket, draw, config)
    if lt == LotteryType.MAIS_MILIONARIA:
        return _check_mais_milionaria(ticket, draw, config)
    if lt == LotteryType.DUPLA_SENA:
        return _check_dupla_sena(ticket, draw, config)

    # Standard: hypergeometric matching
    matched = sorted(set(ticket.numbers) & set(draw.numbers))
    matches = len(matched)
    extra_matches = _count_extra(ticket, draw, lt)
    prize = _find_prize(matches, extra_matches, lt, config)

    return CheckResult(
        ticket=ticket,
        draw=draw,
        matches=matches,
        matched_numbers=matched,
        extra_matches=extra_matches,
        prize_tier=prize,
    )


def _check_super_sete(ticket: Ticket, draw: DrawResult, config: LotteryConfig) -> CheckResult:
    matched_cols = [i for i in range(7) if ticket.numbers[i] == draw.numbers[i]]
    matches = len(matched_cols)
    matched = [ticket.numbers[i] for i in matched_cols]
    prize = _find_standard_prize(matches, config)
    return CheckResult(ticket=ticket, draw=draw, matches=matches,
                       matched_numbers=matched, prize_tier=prize)


def _check_mais_milionaria(ticket: Ticket, draw: DrawResult, config: LotteryConfig) -> CheckResult:
    matched = sorted(set(ticket.numbers) & set(draw.numbers))
    matches = len(matched)
    ticket_trevos = set(ticket.extra) if isinstance(ticket.extra, list) else set()
    draw_trevos   = set(draw.extra)   if isinstance(draw.extra, list) else set()
    extra_matches = len(ticket_trevos & draw_trevos)
    prize = _find_milionaria_prize(matches, extra_matches, config)
    return CheckResult(ticket=ticket, draw=draw, matches=matches,
                       matched_numbers=matched, extra_matches=extra_matches,
                       prize_tier=prize)


def _check_dupla_sena(ticket: Ticket, draw: DrawResult, config: LotteryConfig) -> CheckResult:
    ticket_set = set(ticket.numbers)

    matched1 = sorted(ticket_set & set(draw.numbers))
    prize1 = _find_standard_prize(len(matched1), config)

    matched2: List[int] = []
    prize2: Optional[PrizeTier] = None
    if draw.numbers2:
        matched2 = sorted(ticket_set & set(draw.numbers2))
        prize2 = _find_standard_prize(len(matched2), config)

    return CheckResult(
        ticket=ticket, draw=draw,
        matches=len(matched1), matched_numbers=matched1, prize_tier=prize1,
        matches2=len(matched2), matched_numbers2=matched2, prize_tier2=prize2,
    )


def _count_extra(ticket: Ticket, draw: DrawResult, lt: LotteryType) -> int:
    if ticket.extra is None or draw.extra is None:
        return 0
    if lt == LotteryType.TIMEMANIA or lt == LotteryType.DIA_DE_SORTE:
        return 1 if ticket.extra == draw.extra else 0
    return 0


def _find_prize(matches: int, extra_matches: int,
                lt: LotteryType, config: LotteryConfig) -> Optional[PrizeTier]:
    if lt == LotteryType.LOTOMANIA:
        return _find_lotomania_prize(matches, config)
    if lt == LotteryType.TIMEMANIA:
        return _find_timemania_prize(matches, extra_matches, config)
    if lt == LotteryType.DIA_DE_SORTE:
        return _find_diasorte_prize(matches, extra_matches, config)
    return _find_standard_prize(matches, config)


def _find_standard_prize(matches: int, config: LotteryConfig) -> Optional[PrizeTier]:
    best: Optional[PrizeTier] = None
    for tier in config.prize_tiers:
        if tier.min_extra_matches == 0 and matches >= tier.min_matches:
            if best is None or tier.min_matches > best.min_matches:
                best = tier
    return best


def _find_lotomania_prize(matches: int, config: LotteryConfig) -> Optional[PrizeTier]:
    winning = {0, 15, 16, 17, 18, 19, 20}
    if matches not in winning:
        return None
    for tier in config.prize_tiers:
        if tier.min_matches == matches:
            return tier
    return None


def _find_timemania_prize(matches: int, team_match: int,
                          config: LotteryConfig) -> Optional[PrizeTier]:
    # Number prize takes priority; team prize is separate but we return first found
    number_prize = _find_standard_prize(matches, config)
    if number_prize:
        return number_prize
    if team_match:
        for tier in config.prize_tiers:
            if tier.min_extra_matches > 0:
                return tier
    return None


def _find_diasorte_prize(matches: int, month_match: int,
                         config: LotteryConfig) -> Optional[PrizeTier]:
    number_prize = _find_standard_prize(matches, config)
    if number_prize:
        return number_prize
    if month_match:
        for tier in config.prize_tiers:
            if tier.min_extra_matches > 0:
                return tier
    return None


def _find_milionaria_prize(matches: int, trevo_matches: int,
                           config: LotteryConfig) -> Optional[PrizeTier]:
    # Tiers ordered best-first in config; find first exact match
    for tier in config.prize_tiers:
        if matches == tier.min_matches and trevo_matches == tier.min_extra_matches:
            return tier
    return None
