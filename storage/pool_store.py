"""Persistence layer for bolão (betting pool) management."""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "boloes.json")


@dataclass
class Pool:
    id: str
    name: str
    lottery_type: str        # display_name string, e.g. "Mega-Sena"
    participants: List[str]  # member names
    ticket_ids: List[str]
    created_at: str
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "name": self.name,
            "lottery_type": self.lottery_type,
            "participants": self.participants,
            "ticket_ids": self.ticket_ids,
            "created_at": self.created_at,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pool":
        return cls(
            id=d["id"], name=d["name"],
            lottery_type=d["lottery_type"],
            participants=d.get("participants", []),
            ticket_ids=d.get("ticket_ids", []),
            created_at=d.get("created_at", ""),
            notes=d.get("notes", ""),
        )

    @classmethod
    def create(cls, name: str, lottery_type: str,
               participants: List[str], notes: str = "") -> "Pool":
        return cls(
            id=uuid.uuid4().hex[:8].upper(),
            name=name,
            lottery_type=lottery_type,
            participants=participants,
            ticket_ids=[],
            created_at=date.today().strftime("%d/%m/%Y"),
            notes=notes,
        )


class PoolStore:
    def __init__(self):
        self._load()

    def _load(self):
        if os.path.exists(_FILE):
            with open(_FILE, encoding="utf-8") as f:
                self._data = json.load(f)
        else:
            self._data = {"pools": []}

    def _flush(self):
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def get_all(self) -> List[Pool]:
        return [Pool.from_dict(p) for p in self._data.get("pools", [])]

    def get(self, pool_id: str) -> Optional[Pool]:
        for p in self._data.get("pools", []):
            if p["id"] == pool_id:
                return Pool.from_dict(p)
        return None

    def add(self, pool: Pool) -> None:
        self._data.setdefault("pools", []).append(pool.to_dict())
        self._flush()

    def update(self, pool: Pool) -> None:
        for i, p in enumerate(self._data["pools"]):
            if p["id"] == pool.id:
                self._data["pools"][i] = pool.to_dict()
                self._flush()
                return

    def delete(self, pool_id: str) -> bool:
        before = len(self._data["pools"])
        self._data["pools"] = [p for p in self._data["pools"] if p["id"] != pool_id]
        if len(self._data["pools"]) < before:
            self._flush()
            return True
        return False

    def add_ticket(self, pool_id: str, ticket_id: str) -> bool:
        for p in self._data["pools"]:
            if p["id"] == pool_id:
                if ticket_id not in p["ticket_ids"]:
                    p["ticket_ids"].append(ticket_id)
                    self._flush()
                return True
        return False

    def remove_ticket(self, pool_id: str, ticket_id: str) -> bool:
        for p in self._data["pools"]:
            if p["id"] == pool_id:
                if ticket_id in p["ticket_ids"]:
                    p["ticket_ids"].remove(ticket_id)
                    self._flush()
                return True
        return False

    def all_ticket_ids(self) -> set[str]:
        """Return the set of all ticket IDs currently assigned to any pool."""
        result: set[str] = set()
        for p in self._data.get("pools", []):
            result.update(p.get("ticket_ids", []))
        return result
