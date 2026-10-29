from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    transaction_id: str = Field(min_length=1, max_length=100)
    account_id: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=19, decimal_places=2)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value


class AnalysisRequest(BaseModel):
    transactions: list[TransactionInput] = Field(min_length=1, max_length=10000)


class RuleFinding(BaseModel):
    rule_id: str
    explanation: str
    evidence: str


RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class AlertResponse(BaseModel):
    id: int | None = None
    transaction_id: str
    account_id: str
    risk_score: int
    risk_level: RiskLevel
    triggered_rules: list[RuleFinding]
    analyzed_at: datetime


class AnalysisResponse(BaseModel):
    batch_id: str
    transactions_analyzed: int
    alerts_generated: int
    alerts: list[AlertResponse]


class HealthResponse(BaseModel):
    status: Literal["ok"]

