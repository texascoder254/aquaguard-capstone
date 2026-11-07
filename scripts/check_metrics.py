"""CI quality gate: fail the build if detector or latency metrics miss the design targets."""
import json
import sys
from pathlib import Path


def load(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"FAIL {path} is missing; run scripts.evaluate_detector and scripts.benchmark first")
    with p.open() as f:
        return json.load(f)


det = load("docs/metrics/detector.json")["held_out"]["summary"]
bench = load("docs/metrics/benchmark.json")
checks = {
    "gradual-rise detection >= 0.80": det["gradual_rise_detection_rate"] >= 0.80,
    "false alarms <= 0.10": det["false_alarm_rate"] <= 0.10,
    "95% of readings within 2 s": bench["within_2s_rate"] >= 0.95,
}
for name, ok in checks.items():
    print(("PASS " if ok else "FAIL ") + name)
sys.exit(0 if all(checks.values()) else 1)
