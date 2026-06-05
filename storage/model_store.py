"""Persists learned lottery model data to data/model.json.

The model accumulates statistical knowledge from every draw imported:
  - cumulative frequency (all-time count per number)
  - recency-weighted frequency (recent draws count more, via exponential decay)
  - recent-50 frequency (plain count over last 50 draws)
  - sum distribution (histogram of draw sums)

The model is rebuilt in full after a batch import and updated
incrementally when a single draw is saved manually.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from models.lottery_types import LOTTERY_CONFIGS, LotteryType
from models.ticket import DrawResult

_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "model.json")
_RECENT_WINDOW = 50
_DECAY = 0.985          # per-draw decay for recency weighting


class ModelStore:
    def __init__(self) -> None:
        self._data: dict = self._load()

    # ── persistence ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if os.path.exists(_FILE):
            try:
                with open(_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(_FILE), exist_ok=True)
        with open(_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    # ── full rebuild ──────────────────────────────────────────────────────────

    def rebuild(self, draws: List[DrawResult], lt: LotteryType) -> None:
        """Full rebuild of the model for one lottery from its complete draw history."""
        lt_draws = sorted(
            [d for d in draws if d.lottery_type == lt],
            key=lambda d: d.contest_number.zfill(8) if d.contest_number else "",
        )
        if not lt_draws:
            return

        cfg = LOTTERY_CONFIGS[lt]
        lo, hi = cfg.number_range
        total = len(lt_draws)

        freq:    Dict[int, int]   = {n: 0   for n in range(lo, hi + 1)}
        r_freq:  Dict[int, float] = {n: 0.0 for n in range(lo, hi + 1)}
        sum_hist: Dict[int, int]  = {}

        for i, draw in enumerate(lt_draws):
            weight = _DECAY ** (total - 1 - i)
            nums = list(draw.numbers) + (list(draw.numbers2) if draw.numbers2 else [])
            for n in nums:
                if n in freq:
                    freq[n] += 1
                    r_freq[n] += weight
            s = sum(draw.numbers)
            sum_hist[s] = sum_hist.get(s, 0) + 1

        # Normalise recency weights to integers in [1, 1000]
        max_r = max(r_freq.values()) or 1.0
        r_int = {str(k): max(1, round(v / max_r * 1000)) for k, v in r_freq.items()}

        # Recent-50 plain frequency
        r50: Dict[int, int] = {n: 0 for n in range(lo, hi + 1)}
        for draw in lt_draws[-_RECENT_WINDOW:]:
            for n in draw.numbers:
                if n in r50:
                    r50[n] += 1

        self._data[cfg.display_name] = {
            "frequency":        {str(k): v for k, v in freq.items()},
            "recency_weighted": r_int,
            "recent_50":        {str(k): v for k, v in r50.items()},
            "sum_distribution": {str(k): v for k, v in sum_hist.items()},
            "draws_processed":  total,
            "last_contest":     lt_draws[-1].contest_number or "",
            "last_updated":     datetime.now().strftime("%d/%m/%Y %H:%M"),
        }
        self._flush()

    # ── incremental update (single draw) ────────────────────────────────────

    def update_incremental(self, draw: DrawResult) -> None:
        """Add one new draw to the model without a full rebuild.

        Cumulative frequency and sum histogram are updated precisely.
        Recency-weighted and recent-50 fields become approximate until
        the next full rebuild, but remain usable.
        """
        lt = draw.lottery_type
        cfg = LOTTERY_CONFIGS[lt]
        key = cfg.display_name
        if key not in self._data:
            return  # no model yet; full rebuild needed first

        entry = self._data[key]
        freq     = entry.setdefault("frequency", {})
        sum_hist = entry.setdefault("sum_distribution", {})

        nums = list(draw.numbers) + (list(draw.numbers2) if draw.numbers2 else [])
        for n in nums:
            k = str(n)
            freq[k] = freq.get(k, 0) + 1

        s = sum(draw.numbers)
        sum_hist[str(s)] = sum_hist.get(str(s), 0) + 1

        entry["draws_processed"] = entry.get("draws_processed", 0) + 1
        if draw.contest_number:
            entry["last_contest"] = draw.contest_number
        entry["last_updated"] = datetime.now().strftime("%d/%m/%Y %H:%M")

        self._flush()

    # ── queries ───────────────────────────────────────────────────────────────

    def get_frequency(self, lt: LotteryType,
                      mode: str = "all") -> Dict[int, int]:
        """Return frequency weights.
        mode: 'all' (cumulative) | 'recency' (decay-weighted) | 'recent50'
        """
        key = LOTTERY_CONFIGS[lt].display_name
        entry = self._data.get(key)
        if not entry:
            return {}
        field = {
            "recency":  "recency_weighted",
            "recent50": "recent_50",
        }.get(mode, "frequency")
        return {int(k): v for k, v in entry.get(field, {}).items()}

    def get_sum_distribution(self, lt: LotteryType) -> Dict[int, int]:
        key = LOTTERY_CONFIGS[lt].display_name
        entry = self._data.get(key)
        if not entry:
            return {}
        return {int(k): v for k, v in entry.get("sum_distribution", {}).items()}

    def info(self, lt: LotteryType) -> Optional[dict]:
        key = LOTTERY_CONFIGS[lt].display_name
        entry = self._data.get(key)
        if not entry:
            return None
        return {
            "draws_processed": entry.get("draws_processed", 0),
            "last_contest":    entry.get("last_contest",    "—"),
            "last_updated":    entry.get("last_updated",    "—"),
        }

    def all_info(self) -> List[dict]:
        return [
            {
                "name":            name,
                "draws_processed": e.get("draws_processed", 0),
                "last_contest":    e.get("last_contest",    "—"),
                "last_updated":    e.get("last_updated",    "—"),
            }
            for name, e in self._data.items()
        ]

    def has_model(self, lt: LotteryType) -> bool:
        return LOTTERY_CONFIGS[lt].display_name in self._data
