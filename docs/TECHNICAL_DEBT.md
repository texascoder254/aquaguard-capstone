# Technical debt register

Each item is deliberate for the alpha. Severity reflects risk if AquaGuard served real customers.

| # | Debt | Why it exists | Risk | Mitigation (planned) | Severity |
| --- | --- | --- | --- | --- | --- |
| TD-1 | SQLite + hand-written SQL instead of PostgreSQL/SQLAlchemy | Zero-setup for graders and CI | Single writer; no migrations | Move `repository.py` behind SQLAlchemy, add Alembic migrations; repository interface already isolates SQL | High |
| TD-2 | Authorization rules duplicated: Rego file + Python mirror | OPA sidecar not available in CI | Rules can drift | Add a CI job that runs `opa test` against shared JSON fixtures, then call OPA over HTTP | Medium |
| TD-3 | Rate limit and in-flight guard live in process memory | Simplest correct single-instance version | Bypassed with >1 replica; lost on restart | Redis counters with TTL | Medium |
| TD-4 | Local intent-matcher provider instead of a hosted LLM | No API keys in a public repo; deterministic tests | Narrow language coverage | Azure provider behind the existing `AIAdapter` interface with the same validation + deadline | Medium |
| TD-5 | Demo users and passwords seeded in code; default token secret | Reproducible demos | Unsafe if deployed as is | Refuse to start when `AQUAGUARD_SECRET` is the default outside `dev`; seed only with a `--demo` flag | High |
| TD-6 | Vanilla JS UI without a build or UI tests | Fast to ship; no toolchain | Harder to grow; untested UI | React/Vite + Playwright smoke tests in CI | Low |
| TD-7 | Detector evaluated only on synthetic data | No real sensor data yet | Real-world false alarms unknown | Use stored feedback + agent outcomes to re-run `evaluate_detector` on labelled real windows | Medium |
| TD-8 | Benchmarks are in-process | No staging environment | Understates latency | Run the benchmark against a deployed container with `httpx` | Low |
| TD-9 | CI actions pinned to Node 20-based majors (`checkout@v4`, `setup-python@v5`, `upload-artifact@v4`) | Stable, widely used versions at alpha time | GitHub deprecation notice; future runner breakage | Bump to the Node 24-based majors and pin by commit SHA; add Dependabot for `github-actions` | Low |

## Paid down during the alpha

- MAD floor bug in spike detection (false alarms on quantized data) — fixed with a regression test.
- Unanswerable questions with no readings silently opened cases in an idempotency test — test made explicit and a
  dedicated test added for automatic escalation.
- Lint: zip without `strict=`, lambda assignment, unused loop variable — fixed under ruff rules E, F, W, I, B.
