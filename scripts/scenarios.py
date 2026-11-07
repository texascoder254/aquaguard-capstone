"""Synthetic tank-temperature scenarios shared by the simulator and the detector evaluation.

Readings are one per minute, quantized to the 0.1 °C resolution of a typical aquarium probe.
"""
from __future__ import annotations

import random

KINDS = ("stable", "gradual_rise", "spike", "slow_drift")


def generate(kind: str, seed: int, n: int = 20, base: float = 25.0) -> list[float]:
    rng = random.Random(f"{kind}-{seed}")
    noise = rng.uniform(0.03, 0.08)
    start = base + rng.uniform(-1.0, 1.0)
    temps = []
    if kind == "stable":
        temps = [start + rng.gauss(0, noise) for _ in range(n)]
    elif kind == "slow_drift":  # normal day/night drift: <= 0.3 °C per 30 min, should NOT alarm
        rate = rng.uniform(-0.3, 0.3) / 30.0
        temps = [start + rate * i + rng.gauss(0, noise) for i in range(n)]
    elif kind == "gradual_rise":  # stuck heater: 1.0-3.0 °C per hour
        rate = rng.uniform(1.0, 3.0) / 60.0
        temps = [start + rate * i + rng.gauss(0, noise) for i in range(n)]
    elif kind == "spike":  # sudden jump on the latest reading (probe moved / heater burst)
        temps = [start + rng.gauss(0, noise) for _ in range(n - 1)]
        temps.append(start + rng.choice([-1, 1]) * rng.uniform(1.0, 3.0))
    else:
        raise ValueError(kind)
    return [round(t, 1) for t in temps]


def is_anomalous(kind: str) -> bool:
    return kind in ("gradual_rise", "spike")
