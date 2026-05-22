import json
import os
from typing import List
from models.ticket import Ticket, DrawResult
from models.lottery_types import LotteryType

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "jogos.json")


def _load() -> dict:
    if not os.path.exists(DATA_FILE):
        return {"tickets": [], "draw_history": []}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Store:
    def __init__(self):
        self._data = _load()

    def _flush(self):
        _save(self._data)

    # Tickets
    def get_tickets(self, lottery_type: LotteryType | None = None) -> List[Ticket]:
        tickets = [Ticket.from_dict(t) for t in self._data.get("tickets", [])]
        if lottery_type:
            tickets = [t for t in tickets if t.lottery_type == lottery_type]
        return tickets

    def add_ticket(self, ticket: Ticket) -> None:
        self._data.setdefault("tickets", []).append(ticket.to_dict())
        self._flush()

    def remove_ticket(self, ticket_id: str) -> bool:
        before = len(self._data["tickets"])
        self._data["tickets"] = [
            t for t in self._data["tickets"] if t["id"] != ticket_id
        ]
        changed = len(self._data["tickets"]) < before
        if changed:
            self._flush()
        return changed

    def clear_tickets(self, lottery_type: LotteryType | None = None) -> int:
        if lottery_type is None:
            removed = len(self._data["tickets"])
            self._data["tickets"] = []
        else:
            before = len(self._data["tickets"])
            self._data["tickets"] = [
                t for t in self._data["tickets"]
                if LotteryType(t["lottery_type"]) != lottery_type
            ]
            removed = before - len(self._data["tickets"])
        self._flush()
        return removed

    # Draw history
    def save_draw(self, draw: DrawResult) -> None:
        self._data.setdefault("draw_history", []).append(draw.to_dict())
        self._flush()

    def get_draws(self, lottery_type: LotteryType | None = None) -> List[DrawResult]:
        draws = [DrawResult.from_dict(d) for d in self._data.get("draw_history", [])]
        if lottery_type:
            draws = [d for d in draws if d.lottery_type == lottery_type]
        return draws
