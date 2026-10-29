from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RiskRules:
    high_amount_threshold: Decimal = Decimal("10000.00")
    high_amount_score: int = 35
    frequency_window_minutes: int = 60
    frequency_max_transactions: int = 5
    frequency_score: int = 30
    duplicate_window_minutes: int = 5
    duplicate_pattern_score: int = 50
    duplicate_id_score: int = 60

    @classmethod
    def from_file(cls, path: Path) -> "RiskRules":
        if not path.exists():
            return cls()
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        rules = cls(
            high_amount_threshold=Decimal(str(payload.get("high_amount_threshold", "10000.00"))),
            high_amount_score=int(payload.get("high_amount_score", 35)),
            frequency_window_minutes=int(payload.get("frequency_window_minutes", 60)),
            frequency_max_transactions=int(payload.get("frequency_max_transactions", 5)),
            frequency_score=int(payload.get("frequency_score", 30)),
            duplicate_window_minutes=int(payload.get("duplicate_window_minutes", 5)),
            duplicate_pattern_score=int(payload.get("duplicate_pattern_score", 50)),
            duplicate_id_score=int(payload.get("duplicate_id_score", 60)),
        )
        rules.validate()
        return rules

    def validate(self) -> None:
        if self.high_amount_threshold <= 0:
            raise ValueError("high_amount_threshold must be greater than zero")
        for name in ("high_amount_score", "frequency_score", "duplicate_pattern_score", "duplicate_id_score"):
            value = getattr(self, name)
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100")
        if self.frequency_window_minutes < 1 or self.duplicate_window_minutes < 1:
            raise ValueError("Rule windows must be at least one minute")
        if self.frequency_max_transactions < 1:
            raise ValueError("frequency_max_transactions must be at least one")
