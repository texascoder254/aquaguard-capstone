"""Evaluate the aq-v1 anomaly detector on synthetic scenarios.

Thresholds were chosen on TRAIN seeds (0-199) and are reported on HELD-OUT seeds (1000-1999)
so the published numbers are not tuned on the data they describe.

Usage: python -m scripts.evaluate_detector [--sweep] [--out docs/metrics/detector.json]
"""
from __future__ import annotations

import argparse
import json
from datetime import timedelta

from app import ai
from app.timeutil import iso, utcnow
from scripts.scenarios import KINDS, generate

TRAIN = range(0, 200)
HELD_OUT = range(1000, 2000)


def as_readings(temps):
    now, n = utcnow(), len(temps)
    return [{"observed_at": iso(now - timedelta(minutes=n - 1 - i)), "temperature_c": t} for i, t in enumerate(temps)]


def evaluate(seeds) -> dict:
    out = {}
    for kind in KINDS:
        flagged = sum(ai.detect_anomaly(as_readings(generate(kind, s)))[0] == "warning" for s in seeds)
        out[kind] = {"n": len(seeds), "flagged": flagged, "rate": round(flagged / len(seeds), 4)}
    neg = out["stable"]["flagged"] + out["slow_drift"]["flagged"]
    neg_n = out["stable"]["n"] + out["slow_drift"]["n"]
    out["summary"] = {
        "gradual_rise_detection_rate": out["gradual_rise"]["rate"],
        "spike_detection_rate": out["spike"]["rate"],
        "false_alarm_rate": round(neg / neg_n, 4),
        "targets": {"gradual_rise_detection_rate": ">= 0.80", "false_alarm_rate": "<= 0.10"},
    }
    return out


def sweep():
    rows = []
    for thr in (0.3, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 1.0):
        ai.RISE_THRESHOLD_C_PER_30MIN = thr
        s = evaluate(TRAIN)["summary"]
        rows.append({"rise_threshold": thr, "detect": s["gradual_rise_detection_rate"], "false_alarm": s["false_alarm_rate"]})
    ai.RISE_THRESHOLD_C_PER_30MIN = 0.45
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sweep", action="store_true")
    p.add_argument("--out", default="docs/metrics/detector.json")
    a = p.parse_args()
    result = {"model_version": ai.MODEL_VERSION, "rise_threshold_c_per_30min": ai.RISE_THRESHOLD_C_PER_30MIN,
              "spike_z": ai.SPIKE_Z, "held_out": evaluate(HELD_OUT)}
    if a.sweep:
        result["train_sweep"] = sweep()
    with open(a.out, "w") as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result["held_out"]["summary"], indent=2))
    if a.sweep:
        for r in result["train_sweep"]:
            print(r)


if __name__ == "__main__":
    main()
