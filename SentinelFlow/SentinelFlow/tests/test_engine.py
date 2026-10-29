from datetime import datetime, timezone
from decimal import Decimal

from app.engine import score_transactions
from app.rules import RiskRules


def tx(transaction_id: str, account_id: str, amount: str, minute: int) -> dict:
    return {
        "transaction_id": transaction_id,
        "account_id": account_id,
        "amount": Decimal(amount),
        "currency": "INR",
        "timestamp": datetime(2026, 10, 28, 11, minute, tzinfo=timezone.utc),
    }


def test_high_amount_is_explained_and_scored():
    result = score_transactions([tx("TX-1", "A-1", "15000.00", 0)], [], RiskRules())[0]

    assert result["risk_score"] == 35
    assert result["risk_level"] == "MEDIUM"
    assert result["triggered_rules"][0]["rule_id"] == "HIGH_AMOUNT"
    assert "threshold=10000.00" in result["triggered_rules"][0]["evidence"]


def test_frequency_rule_uses_prior_window_activity():
    batch = [tx(f"TX-{index}", "A-1", "10.00", index) for index in range(6)]

    results = score_transactions(batch, [], RiskRules())

    assert results[4]["risk_score"] == 0
    assert results[5]["risk_score"] == 30
    assert results[5]["triggered_rules"][0]["rule_id"] == "HIGH_FREQUENCY"


def test_duplicate_pattern_and_id_are_separately_explained():
    first = tx("TX-DUP", "A-1", "10.00", 0)
    second = tx("TX-DUP", "A-1", "10.00", 2)

    results = score_transactions([first, second], [], RiskRules())

    assert results[0]["risk_score"] == 100
    assert {item["rule_id"] for item in results[0]["triggered_rules"]} == {
        "DUPLICATE_TRANSACTION_ID", "REPEATED_TRANSACTION_PATTERN"
    }


def test_normal_transaction_has_no_alert_rules():
    result = score_transactions([tx("TX-OK", "A-2", "75.00", 0)], [], RiskRules())[0]

    assert result["risk_score"] == 0
    assert result["triggered_rules"] == []


def test_duplicate_id_in_recent_history_is_flagged():
    result = score_transactions(
        [tx("TX-REUSED", "A-1", "91.00", 2)],
        [tx("TX-REUSED", "A-1", "90.00", 0)],
        RiskRules(),
    )[0]

    assert result["risk_score"] == 60
    assert result["triggered_rules"][0]["rule_id"] == "DUPLICATE_TRANSACTION_ID"
