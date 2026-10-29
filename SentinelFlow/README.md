# SentinelFlow

SentinelFlow is a configurable transaction risk API for flagging suspicious payment patterns. It applies transparent rules to transaction amount, account activity, repeated patterns, and reused transaction IDs, then stores transaction and alert history in SQL.

## Features

- Analyze batches through a REST API.
- Configure rule thresholds, rolling windows, and score weights in `rules.json`.
- Detect high amounts, rapid account activity, repeated account/amount/currency patterns, and reused transaction IDs.
- Return each alert's score, risk level, rules triggered, evidence, and a short explanation.
- Persist analyzed transactions and alerts with SQLAlchemy and SQLite by default.
- Evaluate a labeled synthetic dataset and print precision, recall, F1, confusion counts, and false positives.

## Requirements and setup

Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run the API

```bash
uvicorn app.main:app --reload
```

The API is available at `http://127.0.0.1:8000`; interactive docs are at `/docs`. The default database is `data/sentinelflow.sqlite3`.

### Analyze transactions

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "transactions": [
      {"transaction_id":"TX-1001","account_id":"ACC-01","amount":"12500.00","currency":"INR","timestamp":"2026-10-28T11:00:00Z"},
      {"transaction_id":"TX-1002","account_id":"ACC-02","amount":"75.00","currency":"INR","timestamp":"2026-10-28T11:01:00Z"}
    ]
  }'
```

The response contains `transactions_analyzed`, `alerts_generated`, and explainable alerts. Only transactions that trigger at least one rule appear in the alert list. Each finding includes the rule ID, a plain-language explanation, and the evidence used by that rule.

### Read stored alerts

```bash
curl 'http://127.0.0.1:8000/api/v1/alerts?risk_level=HIGH&limit=100'
curl http://127.0.0.1:8000/health
```

## Default rules

| Rule | Default condition | Score |
| --- | --- | ---: |
| `HIGH_AMOUNT` | Amount is at least 10,000.00 | 35 |
| `HIGH_FREQUENCY` | More than 5 account transactions in 60 minutes | 30 |
| `REPEATED_TRANSACTION_PATTERN` | Same account, amount, and currency within 5 minutes | 50 |
| `DUPLICATE_TRANSACTION_ID` | Transaction ID appeared previously | 60 |

Scores add up and cap at 100. Scores under 30 are `LOW`, 30–59 are `MEDIUM`, and 60–100 are `HIGH`. This is a transparent demo rules engine for investigation support, not a fraud verdict.

Edit `rules.json` to change thresholds, windows, or weights. Set `SENTINELFLOW_RULES_PATH` to use a different JSON config. Set `SENTINELFLOW_DATABASE_URL` to use another SQLAlchemy-compatible database URL; the default SQLite database works without a separate database server.

## Synthetic evaluation

```bash
python scripts/evaluate_synthetic.py
```

The bundled 13-row dataset produces precision `0.833`, recall `1.000`, and F1 `0.909` with the default rules. The report identifies `N-003` as a false positive: it is a legitimate 12,500.00 payment flagged by the high-amount rule. These numbers describe only the small synthetic dataset; see [reports/evaluation.md](reports/evaluation.md).

## Run tests

```bash
pytest
```

The tests cover rule explanations and scores, frequency windows, duplicate patterns, API validation, alert persistence, and the health endpoint.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `POST` | `/api/v1/analyze` | Score and persist a transaction batch |
| `GET` | `/api/v1/alerts` | Read recent alerts; optional `risk_level` and `limit` filters |

## Project layout

```text
app/                  API, validation, Pandas scoring, and SQL persistence
rules.json            Configurable thresholds and weights
data/                 Local SQLite database and synthetic dataset
scripts/              Synthetic evaluation runner
reports/              Evaluation notes and false-positive example
tests/                Engine and API tests
```
