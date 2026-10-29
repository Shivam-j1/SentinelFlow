from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.engine import score_transactions  # noqa: E402
from app.rules import RiskRules  # noqa: E402


def main() -> None:
    dataset_path = PROJECT_ROOT / "data" / "synthetic_transactions.csv"
    frame = pd.read_csv(dataset_path, dtype={"transaction_id": str, "account_id": str, "currency": str})
    labels = frame["label"].astype(int).tolist()
    rows = frame.drop(columns=["label"]).rename(columns={"timestamp": "timestamp"}).to_dict(orient="records")
    for row in rows:
        row["amount"] = Decimal(str(row["amount"]))
        row["timestamp"] = pd.to_datetime(row["timestamp"], utc=True).to_pydatetime()

    rules = RiskRules.from_file(PROJECT_ROOT / "rules.json")
    scored = score_transactions(rows, [], rules)
    predictions = [int(result["risk_score"] > 0) for result in scored]
    true_positives = sum(label == 1 and prediction == 1 for label, prediction in zip(labels, predictions, strict=True))
    false_positives = sum(label == 0 and prediction == 1 for label, prediction in zip(labels, predictions, strict=True))
    false_negatives = sum(label == 1 and prediction == 0 for label, prediction in zip(labels, predictions, strict=True))
    true_negatives = sum(label == 0 and prediction == 0 for label, prediction in zip(labels, predictions, strict=True))
    precision = true_positives / (true_positives + false_positives) if true_positives + false_positives else 0.0
    recall = true_positives / (true_positives + false_negatives) if true_positives + false_negatives else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    print(f"Rows: {len(rows)}")
    print(f"Precision: {precision:.3f}; recall: {recall:.3f}; F1: {f1:.3f}")
    print(f"TP={true_positives} FP={false_positives} FN={false_negatives} TN={true_negatives}")
    print("Flagged rows:")
    for transaction, result, label in zip(rows, scored, labels, strict=True):
        if result["risk_score"] > 0:
            rule_ids = ", ".join(item["rule_id"] for item in result["triggered_rules"])
            outcome = "false positive" if label == 0 else "expected alert"
            print(f"  {transaction['transaction_id']} ({outcome}) score={result['risk_score']} rules={rule_ids}")


if __name__ == "__main__":
    main()
