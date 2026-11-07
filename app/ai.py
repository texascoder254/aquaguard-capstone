"""AI adapter: anomaly detection plus a scoped aquarium-support assistant.

The adapter hides provider details behind analyze(context) -> AIResult. The alpha ships a
local provider ("aq-v1"): a least-squares trend + robust z-score detector and an intent
matcher grounded in the tank's own readings. An Azure provider can be swapped in later
through the same interface. Output is advisory only; it never controls equipment.
"""
from __future__ import annotations

import concurrent.futures
import math
import re
from dataclasses import dataclass
from datetime import datetime
from statistics import median

MODEL_VERSION = "aq-v1"
MIN_READINGS = 20
WINDOW_MINUTES = 30.0
# Tuned on training seeds in scripts/evaluate_detector.py, reported on held-out seeds.
RISE_THRESHOLD_C_PER_30MIN = 0.45
SPIKE_Z = 4.0
MAD_FLOOR_C = 0.1


class AIUnavailable(Exception):
    """Raised on provider timeout or invalid output; caller falls back to a human."""


@dataclass
class AIResult:
    answer: str
    anomaly_status: str  # normal | warning | insufficient_data
    resolved: bool
    model_version: str


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def detect_anomaly(readings: list[dict]) -> tuple[str, dict]:
    """Return (status, details) for readings ordered oldest first."""
    pts = [(r["observed_at"], r["temperature_c"]) for r in readings
           if isinstance(r.get("temperature_c"), (int, float)) and math.isfinite(r["temperature_c"])]
    pts = pts[-MIN_READINGS:]
    if len(pts) < MIN_READINGS:
        return "insufficient_data", {"count": len(pts)}
    t0 = _parse(pts[0][0])
    xs = [(_parse(t) - t0).total_seconds() / 60.0 for t, _ in pts]
    if xs[-1] - xs[0] > WINDOW_MINUTES or xs[-1] <= 0:
        return "insufficient_data", {"count": len(pts), "span_min": round(xs[-1], 1)}
    ys = [y for _, y in pts]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    rise_30 = slope * WINDOW_MINUTES
    base = ys[:-1]
    med = median(base)
    # Floor the MAD at the sensor resolution (0.1 °C) so quantized noise is not a "spike".
    mad = max(median(abs(y - med) for y in base), MAD_FLOOR_C)
    z_last = 0.6745 * (ys[-1] - med) / mad
    details = {"count": n, "rise_c_per_30min": round(rise_30, 3), "spike_z": round(z_last, 2),
               "latest_c": ys[-1]}
    if rise_30 >= RISE_THRESHOLD_C_PER_30MIN or abs(z_last) >= SPIKE_Z:
        return "warning", details
    return "normal", details


INTENTS = {
    "temperature": ["temperature", "temp", "hot", "warm", "cold", "heater", "rising", "heat", "degrees"],
    "ph": ["ph", "acid", "alkaline", "acidity"],
    "water_level": ["level", "evaporat", "top off", "topoff", "water low", "leak"],
    "status": ["status", "how is", "ok", "okay", "healthy", "summary", "doing"],
}
HUMAN_REQUEST = re.compile(r"\b(human|agent|person|representative|someone|call me)\b", re.I)


def _intent(question: str) -> str | None:
    q = question.lower()
    scores = {name: sum(1 for k in keys if k in q) for name, keys in INTENTS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else None


def local_provider(context: dict) -> dict:
    question = context["question"]
    readings = context["readings"]
    status, d = detect_anomaly(readings)
    if HUMAN_REQUEST.search(question):
        return {"answer": "I'll ask a human agent to review this conversation.",
                "anomaly_status": status, "resolved": False, "model_version": MODEL_VERSION}
    intent = _intent(question)
    latest = readings[-1] if readings else None
    if intent is None or latest is None:
        return {"answer": "I can only answer questions about this tank's temperature, pH, water level, or overall status. "
                          "A human agent can help with anything else.",
                "anomaly_status": status, "resolved": False, "model_version": MODEL_VERSION}
    if intent == "temperature":
        if status == "warning":
            answer = (f"A rising or unusual temperature pattern was detected: about {d['rise_c_per_30min']:+.2f} °C "
                      f"over 30 minutes, latest {d['latest_c']:.1f} °C. Check the heater and room temperature, "
                      "and contact support if it keeps climbing.")
        elif status == "insufficient_data":
            answer = (f"The latest temperature is {latest['temperature_c']:.1f} °C, but there are not enough recent "
                      "readings (20 within 30 minutes) to judge the trend yet.")
        else:
            answer = f"Temperature looks stable. The latest reading is {latest['temperature_c']:.1f} °C."
    elif intent == "ph":
        answer = f"The latest pH reading is {latest.get('ph', float('nan')):.2f}. Compare it with your tank's safe range on the dashboard."
    elif intent == "water_level":
        answer = f"The water level is at {latest.get('water_level_pct', float('nan')):.0f}%. Top off with conditioned water if it is below your normal mark."
    else:
        answer = (f"Latest readings: {latest['temperature_c']:.1f} °C, pH {latest.get('ph', float('nan')):.2f}, "
                  f"level {latest.get('water_level_pct', float('nan')):.0f}%. Trend check: {status.replace('_', ' ')}.")
    return {"answer": answer, "anomaly_status": status, "resolved": True, "model_version": MODEL_VERSION}


class AIAdapter:
    """Validates provider output and enforces the total deadline."""

    def __init__(self, provider=local_provider, deadline: float = 8.0):
        self.provider = provider
        self.deadline = deadline
        self._pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)

    def analyze(self, context: dict) -> AIResult:
        future = self._pool.submit(self.provider, context)
        try:
            raw = future.result(timeout=self.deadline)
        except concurrent.futures.TimeoutError as exc:
            raise AIUnavailable("timeout") from exc
        except Exception as exc:  # provider crashed
            raise AIUnavailable(str(exc)) from exc
        return self._validate(raw, context)

    @staticmethod
    def _validate(raw, context) -> AIResult:
        if not isinstance(raw, dict):
            raise AIUnavailable("invalid output")
        answer, status = raw.get("answer"), raw.get("anomaly_status")
        resolved, version = raw.get("resolved"), raw.get("model_version")
        if not isinstance(answer, str) or not 1 <= len(answer) <= 4000:
            raise AIUnavailable("invalid answer")
        if status not in ("normal", "warning", "insufficient_data"):
            raise AIUnavailable("invalid status")
        if not isinstance(resolved, bool) or not isinstance(version, str) or not version:
            raise AIUnavailable("invalid fields")
        if len(context["readings"]) < MIN_READINGS:
            status = "insufficient_data"
        return AIResult(answer, status, resolved, version)
