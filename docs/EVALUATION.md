# Evaluation and benchmarks

All numbers are produced by scripts in `scripts/` and re-checked on every CI run by `scripts/check_metrics.py`.

## Detector (aq-v1)

**Data.** `scripts/scenarios.py` generates 20-reading windows (one per minute, quantized to the 0.1 °C probe
resolution, per-scenario noise σ 0.03–0.08 °C, base temperature 24–26 °C):

| Scenario | Meaning | Should alarm? |
| --- | --- | --- |
| `stable` | noise only | no |
| `slow_drift` | normal day/night drift, ≤ 0.3 °C per 30 min | no |
| `gradual_rise` | stuck heater, 1.0–3.0 °C per hour | yes |
| `spike` | last reading jumps 1–3 °C | yes |

**Method.** Training seeds 0–199 were used to choose the rise threshold; the reported results use held-out seeds
1000–1999 (1,000 windows per scenario) that were never used for tuning.

**Training sweep** (`python -m scripts.evaluate_detector --sweep`):

| Rise threshold (°C/30 min) | Detection | False alarms |
| --- | --- | --- |
| 0.30 | 100% | 2.50% |
| 0.40 | 100% | 0.25% |
| **0.45 (chosen)** | 100% | 0.00% |
| 0.50 | 96.0% | 0.00% |
| 0.60 | 89.5% | 0.00% |
| 0.70 | 80.0% | 0.00% |
| 1.00 | 53.0% | 0.00% |

**Held-out results** ([metrics/detector.json](metrics/detector.json)):

| Metric | Target | Result |
| --- | --- | --- |
| Gradual-rise detection | ≥ 80% | **99.1%** |
| Spike detection | — | **100%** |
| False-alarm rate (stable + slow drift, n = 2,000) | ≤ 10% | **0.05%** |

**Threats to validity.** The scenarios are synthetic and the noise model is Gaussian. Real probes drift, drop
readings, and suffer biofilm. The very slow end of the "stuck heater" range (≈ 1 °C/hour) sits right at the
threshold, which is where the remaining misses are. Customer feedback ratings are stored so the detector can be
re-evaluated on real data.

### Bug found by evaluation

The first version floored the median absolute deviation (MAD) at 0.01 °C. With readings quantized to 0.1 °C,
a perfectly normal alternating series had MAD = 0 and the newest reading scored z ≈ 6.7, which is a false spike.
`test_stable_series_normal` caught it. The fix floors the MAD at the probe resolution (0.1 °C).

## Latency benchmark

`python -m scripts.benchmark --n 1000` (in-process FastAPI TestClient + SQLite file, no network):

| Metric | Result |
| --- | --- |
| Ingest p50 / p95 / p99 | 2.83 / 3.43 / 3.96 ms |
| Ingest → visible on GET, p95 | 6.5 ms |
| Readings within 2 s (target ≥ 95%) | 100% |
| Assistant p50 / p95 (local provider) | 3.09 / 3.90 ms |
| Sequential throughput | ≈ 343 readings/s |

These are lower bounds: real deployments add network, TLS, and (for a hosted model) seconds of inference, which
is why the assistant has an 8-second deadline with a human fallback.

## Test coverage

32 pytest tests (unit + API integration), **91% line coverage** of `app/` (CI fails under 85%).
See [metrics/coverage.txt](metrics/coverage.txt).

| Suite | Tests | Focus |
| --- | --- | --- |
| `test_auth_policy.py` | 7 | tokens, tampering, expiry, tenant isolation, fail-closed policy |
| `test_monitoring.py` | 7 | validation, idempotency, thresholds, pagination |
| `test_ai.py` | 7 | detector edge cases, adapter deadline/validation |
| `test_assistant_handoff.py` | 9 | answers, idempotent chat, escalation paths, agent replies, feedback |
| `test_policy_parity.py` | 2 | Rego file and Python mirror allow the same actions |
