# AquaGuard

[![CI](https://github.com/texascoder254/aquaguard-capstone/actions/workflows/ci.yml/badge.svg)](https://github.com/texascoder254/aquaguard-capstone/actions/workflows/ci.yml)

AquaGuard is an aquarium-monitoring web service for a small aquarium-care business. Tank sensors (or the
included simulator) post temperature, pH, and water-level readings; customers see a live dashboard; an
AI module flags unusual temperature trends and answers tank questions; and anything the AI cannot answer
confidently is handed to a human support agent with the full conversation attached.

> CMSC 495 Computer Science Capstone, UMGC, Fall 2026. Built individually by **William Akinbayo**
> (see [docs/CONTRIBUTIONS.md](docs/CONTRIBUTIONS.md)). AI tools assisted with drafting, review, and tests;
> see [docs/AI_USAGE.md](docs/AI_USAGE.md).

## Why it exists

Aquarium failures (a stuck heater, a failed probe) usually show up as a *trend* minutes to hours before a
hard limit is crossed. Fixed thresholds alone either alarm too late or too often. AquaGuard combines
per-tank thresholds with a trend detector, then routes uncertain cases to people instead of guessing.

## Features (alpha 0.5)

| Area | What works |
| --- | --- |
| Ingestion | `POST /api/v1/tanks/{id}/readings` with schema validation, physical-range and timestamp-window checks, idempotent duplicates, per-tank threshold status |
| Dashboard | Login, tank selector, live stats, temperature chart with the tank's safe band |
| AI anomaly detection | `aq-v1`: least-squares trend over the last 20 readings (≤ 30 min) + robust z-score spike check |
| AI assistant | Scoped to the tank's own data (temperature, pH, level, status); refuses out-of-scope questions |
| Human handoff | Explicit "Talk to a human", automatic escalation on unanswerable questions, AI timeout, or invalid model output |
| Agent console | Scoped case queue, transcript, reply-and-close; idempotent replies |
| Feedback | One helpful/not-helpful rating per AI answer, queued for review |
| Security | Signed bearer tokens (HMAC-SHA256), PBKDF2 password hashes, deny-by-default policy (Rego + in-process mirror), tenant isolation, chat rate limit |

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q                                    # 32 tests
uvicorn app.server:app --port 8000           # open http://127.0.0.1:8000
python -m scripts.simulator --scenario gradual_rise --backfill 30   # in a second terminal
```

Demo users: `maya / reef-demo-1` (customer), `agent-lee / agent-demo-4` (support agent).
Full steps: [docs/INSTALL.md](docs/INSTALL.md). How to use the UI: [docs/USER_MANUAL.md](docs/USER_MANUAL.md).

## Measured results (held-out data, CI-gated)

| Metric | Target (design spec) | Result |
| --- | --- | --- |
| Gradual-rise detection (1–3 °C/h) | ≥ 80% | **99.1%** (1,000 held-out scenarios) |
| Spike detection | — | **100%** |
| False alarms (stable + normal drift) | ≤ 10% | **0.05%** (1 of 2,000) |
| Readings visible within 2 s | ≥ 95% | **100%**; ingest p95 3.4 ms in-process |
| Assistant response p95 | ≤ 8 s deadline | 3.9 ms (local provider) |
| Line coverage | ≥ 85% (CI gate) | **91%** |

Sources: [docs/metrics](docs/metrics), [docs/EVALUATION.md](docs/EVALUATION.md).
Benchmarks are in-process (no network); production latency will be higher.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) · [API reference](docs/API.md) (+ live OpenAPI at `/docs`)
- [Installation](docs/INSTALL.md) · [User manual](docs/USER_MANUAL.md)
- [Evaluation & benchmarks](docs/EVALUATION.md) · [Code review log](docs/CODE_REVIEW.md)
- [Technical debt register](docs/TECHNICAL_DEBT.md) · [Changelog](CHANGELOG.md)
- [CI/CD evidence](docs/CI_EVIDENCE.md) · [Screenshots](docs/SCREENSHOTS.md)

## Repository layout

```
app/            FastAPI service (routes in main.py; one module per workflow)
app/static/     Dashboard + agent console (vanilla JS, no build step)
policy/         Rego authorization policy (source of truth for the in-process mirror)
scripts/        simulator, detector evaluation, benchmark, CI quality gate
tests/          pytest unit + API integration tests
docs/           architecture, API, manuals, metrics, screenshots
```

## Safety note

AquaGuard is advisory. It never switches equipment on or off, and every AI answer shows the model version
and trend status so a person can judge it.

## License

MIT. See [LICENSE](LICENSE).
