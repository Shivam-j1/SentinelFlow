from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import create_tables, get_db
from app.engine import score_transactions
from app.models import RiskAlert, Transaction
from app.rules import RiskRules
from app.schemas import (
    AlertResponse,
    AnalysisRequest,
    AnalysisResponse,
    HealthResponse,
    RuleFinding,
)

RULES_PATH = Path(os.getenv("SENTINELFLOW_RULES_PATH", "rules.json"))
RISK_RULES = RiskRules.from_file(RULES_PATH)


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield


app = FastAPI(
    title="SentinelFlow",
    description="Explainable transaction risk scoring API",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post("/api/v1/analyze", response_model=AnalysisResponse, tags=["risk"])
def analyze(payload: AnalysisRequest, db: Session = Depends(get_db)) -> AnalysisResponse:
    now = datetime.now(timezone.utc)
    inputs = [
        item.model_dump() | {"timestamp": item.timestamp.astimezone(timezone.utc)}
        for item in payload.transactions
    ]
    account_ids = {item["account_id"] for item in inputs}
    min_time = min(item["timestamp"] for item in inputs)
    max_time = max(item["timestamp"] for item in inputs)
    lookback = max(RISK_RULES.frequency_window_minutes, RISK_RULES.duplicate_window_minutes)
    history_start = min_time - timedelta(minutes=lookback)
    history_end = max_time + timedelta(minutes=RISK_RULES.duplicate_window_minutes)
    transaction_ids = {item["transaction_id"] for item in inputs}
    history_rows = db.scalars(
        select(Transaction).where(or_(
            (Transaction.account_id.in_(account_ids)
             & (Transaction.timestamp >= history_start)
             & (Transaction.timestamp <= history_end)),
            Transaction.transaction_id.in_(transaction_ids),
        ))
    ).all()
    history = [
        {
            "transaction_id": item.transaction_id,
            "account_id": item.account_id,
            "amount": item.amount,
            "currency": item.currency,
            "timestamp": item.timestamp.replace(tzinfo=timezone.utc)
            if item.timestamp.tzinfo is None else item.timestamp.astimezone(timezone.utc),
        }
        for item in history_rows
    ]

    scored = score_transactions(inputs, history, RISK_RULES)
    batch_id = str(uuid4())
    transaction_rows: list[Transaction] = []
    for result in scored:
        transaction_rows.append(Transaction(
            transaction_id=result["transaction_id"],
            account_id=result["account_id"],
            amount=Decimal(result["amount"]),
            currency=result["currency"],
            timestamp=result["timestamp"],
        ))
    db.add_all(transaction_rows)
    try:
        db.flush()
        alerts: list[RiskAlert] = []
        for transaction, result in zip(transaction_rows, scored, strict=True):
            if result["triggered_rules"]:
                alerts.append(RiskAlert(
                    transaction_row_id=transaction.id,
                    transaction_id=transaction.transaction_id,
                    account_id=transaction.account_id,
                    risk_score=result["risk_score"],
                    risk_level=result["risk_level"],
                    triggered_rules=result["triggered_rules"],
                    analyzed_at=now,
                ))
        db.add_all(alerts)
        db.commit()
    except Exception:
        db.rollback()
        raise

    response_alerts = [
        AlertResponse(
            id=alert.id,
            transaction_id=alert.transaction_id,
            account_id=alert.account_id,
            risk_score=alert.risk_score,
            risk_level=alert.risk_level,
            triggered_rules=[RuleFinding(**finding) for finding in alert.triggered_rules],
            analyzed_at=now,
        )
        for alert in alerts
    ]
    return AnalysisResponse(
        batch_id=batch_id,
        transactions_analyzed=len(scored),
        alerts_generated=len(response_alerts),
        alerts=response_alerts,
    )


@app.get("/api/v1/alerts", response_model=list[AlertResponse], tags=["risk"])
def list_alerts(
    risk_level: str | None = Query(default=None, pattern="^(LOW|MEDIUM|HIGH)$"),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AlertResponse]:
    statement = select(RiskAlert).order_by(RiskAlert.id.desc()).limit(limit)
    if risk_level:
        statement = statement.where(RiskAlert.risk_level == risk_level)
    alerts = db.scalars(statement).all()
    return [
        AlertResponse(
            id=alert.id,
            transaction_id=alert.transaction_id,
            account_id=alert.account_id,
            risk_score=alert.risk_score,
            risk_level=alert.risk_level,
            triggered_rules=[RuleFinding(**finding) for finding in alert.triggered_rules],
            analyzed_at=alert.analyzed_at.replace(tzinfo=timezone.utc)
            if alert.analyzed_at.tzinfo is None else alert.analyzed_at,
        )
        for alert in alerts
    ]
