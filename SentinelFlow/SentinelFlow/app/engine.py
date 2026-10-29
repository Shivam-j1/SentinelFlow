from __future__ import annotations

from bisect import bisect_left, bisect_right
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pandas as pd

from app.rules import RiskRules


def score_transactions(
    transactions: list[dict[str, Any]],
    history: list[dict[str, Any]],
    rules: RiskRules,
) -> list[dict[str, Any]]:
    """Score new transactions against the current batch and recent SQL history."""
    if not transactions:
        return []

    rows: list[dict[str, Any]] = []
    for index, item in enumerate(history):
        rows.append(_normalize(item, f"history-{index}", False))
    new_keys: list[str] = []
    for index, item in enumerate(transactions):
        key = f"new-{index}"
        new_keys.append(key)
        rows.append(_normalize(item, key, True))

    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["amount_key"] = frame["amount"].map(lambda amount: Decimal(str(amount)).quantize(Decimal("0.01")))
    frame.sort_values(["account_id", "timestamp", "_key"], kind="stable", inplace=True)
    frame.reset_index(drop=True, inplace=True)

    times_ns = frame["timestamp"].astype("int64").to_numpy()
    account_positions = {
        account_id: positions.tolist()
        for account_id, positions in frame.groupby("account_id", sort=False).indices.items()
    }
    id_positions = {
        transaction_id: positions.tolist()
        for transaction_id, positions in frame.groupby("transaction_id", sort=False).indices.items()
    }
    pattern_positions = {
        pattern: positions.tolist()
        for pattern, positions in frame.groupby(
            ["account_id", "amount_key", "currency"], sort=False
        ).indices.items()
    }
    positions_by_key = {key: position for position, key in enumerate(frame["_key"].tolist())}
    frequency_window_ns = rules.frequency_window_minutes * 60 * 1_000_000_000
    duplicate_window_ns = rules.duplicate_window_minutes * 60 * 1_000_000_000

    scored: list[dict[str, Any]] = []
    for source_index, item in enumerate(transactions):
        key = new_keys[source_index]
        position = positions_by_key[key]
        row = frame.iloc[position]
        timestamp_ns = int(times_ns[position])
        findings: list[dict[str, str]] = []
        score = 0
        amount = row["amount_key"]

        if amount >= rules.high_amount_threshold:
            score += rules.high_amount_score
            findings.append({
                "rule_id": "HIGH_AMOUNT",
                "explanation": "Transaction amount met or exceeded the configured threshold.",
                "evidence": f"amount={amount}; threshold={rules.high_amount_threshold}",
            })

        positions = account_positions[row["account_id"]]
        account_times = [int(times_ns[p]) for p in positions]
        frequency_start = bisect_left(account_times, timestamp_ns - frequency_window_ns)
        frequency_end = bisect_right(account_times, timestamp_ns)
        frequency_count = frequency_end - frequency_start
        if frequency_count > rules.frequency_max_transactions:
            score += rules.frequency_score
            findings.append({
                "rule_id": "HIGH_FREQUENCY",
                "explanation": "Account activity exceeded the configured rolling-window limit.",
                "evidence": (f"transactions_in_window={frequency_count}; limit="
                             f"{rules.frequency_max_transactions}; window_minutes={rules.frequency_window_minutes}"),
            })

        same_id_positions = id_positions[row["transaction_id"]]
        if any(other != position for other in same_id_positions):
            score += rules.duplicate_id_score
            findings.append({
                "rule_id": "DUPLICATE_TRANSACTION_ID",
                "explanation": "Transaction ID already appears in the batch or recent history.",
                "evidence": f"transaction_id={row['transaction_id']}; matches={len(same_id_positions) - 1}",
            })

        pattern_key = (row["account_id"], amount, row["currency"])
        pattern_group = pattern_positions[pattern_key]
        pattern_times = [int(times_ns[p]) for p in pattern_group]
        pattern_start = bisect_left(pattern_times, timestamp_ns - duplicate_window_ns)
        pattern_end = bisect_right(pattern_times, timestamp_ns + duplicate_window_ns)
        nearby_pattern_count = pattern_end - pattern_start
        if nearby_pattern_count > 1:
            score += rules.duplicate_pattern_score
            findings.append({
                "rule_id": "REPEATED_TRANSACTION_PATTERN",
                "explanation": "A matching account, amount, and currency appeared within the duplicate window.",
                "evidence": (f"matching_transactions={nearby_pattern_count}; "
                             f"window_minutes={rules.duplicate_window_minutes}"),
            })

        score = min(score, 100)
        risk_level = "HIGH" if score >= 60 else "MEDIUM" if score >= 30 else "LOW"
        scored.append({
            "transaction_id": str(item["transaction_id"]),
            "account_id": str(item["account_id"]),
            "amount": amount,
            "currency": str(item["currency"]),
            "timestamp": row["timestamp"].to_pydatetime(),
            "risk_score": score,
            "risk_level": risk_level,
            "triggered_rules": findings,
        })
    return scored


def _normalize(item: dict[str, Any], key: str, is_new: bool) -> dict[str, Any]:
    timestamp = item["timestamp"]
    if isinstance(timestamp, str):
        timestamp = pd.Timestamp(timestamp).to_pydatetime()
    return {
        "_key": key,
        "_is_new": is_new,
        "transaction_id": str(item["transaction_id"]),
        "account_id": str(item["account_id"]),
        "amount": Decimal(str(item["amount"])),
        "currency": str(item["currency"]),
        "timestamp": timestamp,
    }
