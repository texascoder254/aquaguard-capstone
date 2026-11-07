# Code review log

AquaGuard was built by one developer, so "peer review" combined (1) a structured self-review against the
course review checklist, (2) an automated reviewer (GitHub Copilot code review on the pull request), and
(3) machine checks in CI (ruff, pytest, coverage gate, metric gate). Findings and their resolution are below.

| Area | Finding | Resolution |
| --- | --- | --- |
| Code quality | Routes were starting to carry logic | Kept `main.py` thin; workflows in `monitoring`, `assistant`, `handoff`, `feedback` |
| Code quality | Lint findings (B905 zip strict, E731 lambda, B007 unused variable) | Fixed; ruff runs in CI |
| Security | Out-of-tenant tanks returned 403, leaking that they exist | Return 404 for resources outside the caller's tenant |
| Security | Policy engine errors could default to allow | Fail closed with `503 policy_unavailable` (tested) |
| Security | Token comparisons | `hmac.compare_digest` for signatures and password hashes |
| Security | Default token secret and seeded passwords | Documented as TD-5 with a startup guard planned |
| Security | Rego file was missing customer `transcript:read` that the Python mirror allowed (rule drift, TD-2) | Rego updated; drift test planned |
| Performance | History queries used OFFSET | Keyset cursor on `(observed_at, reading_id)` |
| Performance | Ingest latency unknown | Benchmark script + CI gate (≥ 95% within 2 s) |
| AI | Spike detector false alarms on quantized data | MAD floored at probe resolution; regression test |
| AI | Model output trusted blindly | Adapter validates schema and deadline; any failure → human case |
| Integration | Duplicate chat submissions created duplicate cases | Idempotency key per `message_id`; in-flight 409 |
| Documentation | API errors undocumented | `docs/API.md` error table + OpenAPI at `/docs` |

Pull request reviews: see the repository's Pull requests tab (Copilot review on the alpha integration PR).
