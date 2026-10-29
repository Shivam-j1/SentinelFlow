# Synthetic Rules Evaluation

The bundled dataset has 13 labeled rows: ordinary activity, one legitimate high-value payment, a high-frequency sequence, a repeated account/amount pattern, and a repeated transaction ID.

With the default rules, the expected detector behavior is:

- Flag the sixth transaction in the high-frequency sequence.
- Flag both rows in the repeated account/amount pattern.
- Flag both rows that share a transaction ID.
- Also flag `N-003`, a legitimate INR 12,500.00 payment. This is an intentional false-positive example showing that an amount threshold alone does not establish fraud.

The current default rules produce 5 true positives, 1 false positive, 0 false negatives, and 7 true negatives: precision `0.833`, recall `1.000`, and F1 `0.909`.

Run `python scripts/evaluate_synthetic.py` to recalculate the metrics from the CSV. Results are specific to this small synthetic dataset and are not a claim about real-world fraud performance.
