from dataclasses import dataclass, field
from typing import List, Optional, Union
from datetime import datetime
import uuid

from .lottery_types import LotteryType


@dataclass
class Ticket:
    id: str
    lottery_type: LotteryType
    numbers: List[int]
    extra: Optional[Union[int, List[int]]] = None   # month, team, or [trevo1, trevo2]
    label: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "lottery_type": self.lottery_type.value,
            "numbers": self.numbers,
            "extra": self.extra,
            "label": self.label,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ticket":
        return cls(
            id=data["id"],
            lottery_type=LotteryType(data["lottery_type"]),
            numbers=data["numbers"],
            extra=data.get("extra"),
            label=data.get("label", ""),
            created_at=data.get("created_at", ""),
        )

    @classmethod
    def create(cls, lottery_type: LotteryType, numbers: List[int],
               extra: Optional[Union[int, List[int]]] = None,
               label: str = "") -> "Ticket":
        from .lottery_types import LOTTERY_CONFIGS
        config = LOTTERY_CONFIGS[lottery_type]
        sorted_nums = numbers if config.is_positional else sorted(numbers)
        return cls(
            id=str(uuid.uuid4())[:8].upper(),
            lottery_type=lottery_type,
            numbers=sorted_nums,
            extra=extra,
            label=label,
        )


@dataclass
class DrawResult:
    lottery_type: LotteryType
    numbers: List[int]
    numbers2: Optional[List[int]] = None    # Dupla-Sena 2nd draw
    extra: Optional[Union[int, List[int]]] = None
    contest_number: str = ""
    draw_date: str = ""

    def to_dict(self) -> dict:
        return {
            "lottery_type": self.lottery_type.value,
            "numbers": self.numbers,
            "numbers2": self.numbers2,
            "extra": self.extra,
            "contest_number": self.contest_number,
            "draw_date": self.draw_date,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DrawResult":
        return cls(
            lottery_type=LotteryType(data["lottery_type"]),
            numbers=data["numbers"],
            numbers2=data.get("numbers2"),
            extra=data.get("extra"),
            contest_number=data.get("contest_number", ""),
            draw_date=data.get("draw_date", ""),
        )
