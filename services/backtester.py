"""Historical backtesting: simulate tickets against stored draw history."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from models.lottery_types import LOTTERY_CONFIGS, LotteryType
from models.ticket import DrawResult, Ticket
from services.checker import CheckResult, check_ticket


@dataclass
class DrawRow:
    """One historical draw crossed against every selected ticket."""
    draw: DrawResult
    results: List[CheckResult]

    @property
    def best_result(self) -> Optional[CheckResult]:
        best: Optional[CheckResult] = None
        for r in self.results:
            if best is None or r.matches > best.matches:
                best = r
        return best

    @property
    def winners(self) -> int:
        return sum(1 for r in self.results if r.is_winner)

    @property
    def fixed_prize_total(self) -> float:
        total = 0.0
        for r in self.results:
            for tier in [r.prize_tier, getattr(r, "prize_tier2", None)]:
                if tier and tier.prize_type == "fixed":
                    total += tier.fixed_value
        return total

    @property
    def has_variable_prize(self) -> bool:
        for r in self.results:
            for tier in [r.prize_tier, getattr(r, "prize_tier2", None)]:
                if tier and tier.prize_type in ("variable", "jackpot"):
                    return True
        return False


@dataclass
class BacktestReport:
    lottery_type: LotteryType
    tickets: List[Ticket]
    rows: List[DrawRow]

    @property
    def total_draws(self) -> int:
        return len(self.rows)

    @property
    def total_events(self) -> int:
        return len(self.rows) * len(self.tickets)

    @property
    def total_cost(self) -> float:
        cfg = LOTTERY_CONFIGS[self.lottery_type]
        return len(self.tickets) * len(self.rows) * cfg.ticket_price

    @property
    def total_fixed_prizes(self) -> float:
        return sum(r.fixed_prize_total for r in self.rows)

    @property
    def net(self) -> float:
        return self.total_fixed_prizes - self.total_cost

    @property
    def roi(self) -> float:
        if self.total_cost == 0:
            return 0.0
        return self.total_fixed_prizes / self.total_cost * 100

    @property
    def best_overall(self) -> Optional[CheckResult]:
        best: Optional[CheckResult] = None
        for row in self.rows:
            br = row.best_result
            if br and (best is None or br.matches > best.matches):
                best = br
        return best

    @property
    def draws_with_prize(self) -> int:
        return sum(1 for r in self.rows if r.winners > 0 or r.has_variable_prize)

    @property
    def match_distribution(self) -> Dict[int, int]:
        dist: Dict[int, int] = {}
        for row in self.rows:
            for r in row.results:
                dist[r.matches] = dist.get(r.matches, 0) + 1
        return dict(sorted(dist.items(), reverse=True))


def run_backtest(tickets: List[Ticket], draws: List[DrawResult]) -> BacktestReport:
    lt = tickets[0].lottery_type if tickets else LotteryType.MEGA_SENA

    filtered = sorted(
        (d for d in draws if d.lottery_type == lt),
        key=lambda d: d.contest_number.zfill(8) if d.contest_number else "",
        reverse=True,
    )

    rows = [
        DrawRow(draw=d, results=[check_ticket(t, d) for t in tickets])
        for d in filtered
    ]

    return BacktestReport(lottery_type=lt, tickets=tickets, rows=rows)
