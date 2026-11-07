# Architecture

## Context

```
 Sensor / simulator ──POST readings──►┐
                                      │        ┌──────────────── AquaGuard service (FastAPI) ────────────────┐
 Customer browser ──dashboard/chat───►├─ HTTPS ─► auth (HMAC token) → policy (deny by default) → workflow  │
                                      │        │   monitoring | assistant | handoff | feedback              │
 Support agent ──case console────────►┘        │        │            │           │                         │
                                               │   repository (SQLite, transactions)   AI adapter (aq-v1)  │
                                               └──────────────────────────────────────────────────────────────┘
```

## Modules

| Module | Responsibility | Key decisions |
| --- | --- | --- |
| `main.py` | Routes, strict request models, error envelope, chat rate limit | Routes stay thin; no business logic |
| `security.py` | PBKDF2-SHA256 (120k iterations) password hashes; compact HMAC-SHA256 bearer tokens with expiry | Constant-time compares |
| `policy.py` + `policy/aquaguard.rego` | Role/tenant authorization | Out-of-tenant resources return 404; policy errors fail closed (503) |
| `monitoring.py` | Validate, threshold, persist, paginate readings | Idempotent `reading_id`; keyset cursor pagination |
| `ai.py` | `detect_anomaly` + scoped intent assistant behind `AIAdapter` | Deadline + output validation; provider is swappable |
| `assistant.py` | Conversation flow, idempotent messages, in-flight guard, fallback | Any AI failure becomes a human case, never a guess |
| `handoff.py` | Case queue, transcript, agent replies | One open case per conversation; idempotent replies |
| `feedback.py` | One rating per assistant answer, queued for review | Feeds future model evaluation |
| `customer_adapter.py` | Maps tenant → customer/service context | Missing mapping → 409, not silent defaults |
| `repository.py` | SQLite schema, `transaction()` context manager | Foreign keys on; every write in one transaction |

## Anomaly detector (aq-v1)

1. Take the last 20 finite temperature readings; require that they span ≤ 30 minutes, else `insufficient_data`.
2. Fit a least-squares line; `rise_30 = slope × 30 min`. Warn if `rise_30 ≥ 0.45 °C`.
3. Robust spike check on the newest reading: `z = 0.6745 (x − median) / max(MAD, 0.1 °C)`; warn if `|z| ≥ 4`.
   The MAD floor equals the probe resolution so quantization noise is not mistaken for a spike
   (this was a real bug caught by `test_stable_series_normal`).

Thresholds were swept on training scenarios and reported on separate held-out scenarios (see EVALUATION.md).

## Request flow: customer question

1. Token verified → policy `messages:write` on the tank's client.
2. Idempotency: same `message_id` + same body → stored response; different body → 409; in flight → 409.
3. Context = question + last 10 conversation messages + last 20 readings + customer context.
4. `AIAdapter.analyze` runs the provider in a worker with the deadline; output schema validated.
5. Unresolved / timeout / invalid → case opened in the same transaction as the messages.

## Deployment target vs. alpha

| Concern | Alpha 0.5 | Target (design spec) |
| --- | --- | --- |
| Database | SQLite file | PostgreSQL via SQLAlchemy + Alembic |
| Policy | In-process mirror of Rego | OPA sidecar |
| AI | Local `aq-v1` provider | Azure-hosted model behind the same adapter |
| UI | Vanilla JS | React/Vite |
| Rate limit / in-flight | In-memory | Redis (multi-replica safe) |

See TECHNICAL_DEBT.md for the plan.
