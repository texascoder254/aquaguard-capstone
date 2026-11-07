# Changelog

## 0.5.0-alpha (Unit 5 Alpha release)

### Added
- Reading ingestion with validation, idempotency, per-tank thresholds, cursor history
- Signed bearer tokens, PBKDF2 passwords, deny-by-default role/tenant policy (Rego + mirror)
- `aq-v1` anomaly detector (trend + robust spike) and scoped assistant behind `AIAdapter`
- Human handoff: explicit, out-of-scope, timeout, and invalid-output escalation; agent console
- Feedback on assistant answers; customer dashboard with chart
- Simulator, detector evaluation (train/held-out), latency benchmark, CI quality gate
- GitHub Actions: ruff, pytest on Python 3.11/3.13, coverage ≥ 85%, metric gate, artifacts

### Fixed
- Spike detector false alarms on 0.1 °C-quantized readings (MAD floor)
- Rego policy missing customer `transcript:read` (drift from Python mirror); parity test added
