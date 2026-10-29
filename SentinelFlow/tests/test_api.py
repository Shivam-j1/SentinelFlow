import os

os.environ["SENTINELFLOW_DATABASE_URL"] = "sqlite:///./data/sentinelflow-test.sqlite3"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=test_engine, autoflush=False, expire_on_commit=False)


def override_get_db():
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def test_analyze_persists_alert_and_exposes_explanation():
    response = client.post("/api/v1/analyze", json={
        "transactions": [{
            "transaction_id": "TX-HIGH",
            "account_id": "ACC-1",
            "amount": "15000.00",
            "currency": "INR",
            "timestamp": "2026-10-28T11:00:00Z",
        }]
    })

    assert response.status_code == 200
    body = response.json()
    assert body["transactions_analyzed"] == 1
    assert body["alerts_generated"] == 1
    assert body["alerts"][0]["risk_score"] == 35
    assert body["alerts"][0]["triggered_rules"][0]["rule_id"] == "HIGH_AMOUNT"
    stored = client.get("/api/v1/alerts?risk_level=MEDIUM").json()
    assert stored[0]["transaction_id"] == "TX-HIGH"


def test_rejects_timestamp_without_timezone():
    response = client.post("/api/v1/analyze", json={
        "transactions": [{
            "transaction_id": "TX-LOCAL",
            "account_id": "ACC-1",
            "amount": "10.00",
            "currency": "INR",
            "timestamp": "2026-10-28T11:00:00",
        }]
    })

    assert response.status_code == 422


def test_health_endpoint():
    assert client.get("/health").json() == {"status": "ok"}
