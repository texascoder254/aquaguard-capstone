from datetime import timedelta

from app.ai import AIAdapter, AIUnavailable, detect_anomaly, local_provider
from app.timeutil import iso, utcnow


def series(temps, step=1.0):
    n = len(temps)
    return [{"observed_at": iso(utcnow() - timedelta(minutes=(n - 1 - i) * step)), "temperature_c": t}
            for i, t in enumerate(temps)]


def test_insufficient_data_under_20():
    assert detect_anomaly(series([25.0] * 19))[0] == "insufficient_data"


def test_window_longer_than_30_minutes_is_insufficient():
    assert detect_anomaly(series([25.0] * 20, step=2.0))[0] == "insufficient_data"


def test_stable_series_normal():
    temps = [25.0 + (0.05 if i % 2 else -0.05) for i in range(20)]
    assert detect_anomaly(series(temps))[0] == "normal"


def test_gradual_rise_warning():
    temps = [25.0 + 0.05 * i for i in range(20)]
    status, d = detect_anomaly(series(temps))
    assert status == "warning" and d["rise_c_per_30min"] > 1.0


def test_sudden_spike_warning():
    temps = [25.0] * 19 + [27.5]
    assert detect_anomaly(series(temps))[0] == "warning"


def test_adapter_rejects_invalid_output():
    adapter = AIAdapter(provider=lambda ctx: {"answer": "", "anomaly_status": "normal"}, deadline=1)
    try:
        adapter.analyze({"question": "hi", "readings": [], "history": []})
        raise AssertionError("expected AIUnavailable")
    except AIUnavailable:
        pass


def test_out_of_scope_question_is_unresolved():
    out = local_provider({"question": "What stocks should I buy?", "readings": series([25.0] * 20)})
    assert out["resolved"] is False
