"""Cycle 9 observability and operations guards."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_http_request_telemetry_has_correlation_and_latency():
    source = (ROOT / "backend/app/main.py").read_text()

    assert "request_telemetry" in source
    assert "x-request-id" in source
    assert "duration_ms" in source
    assert "http.request_failed" in source
    assert "http.request" in source


def test_ops_runbook_covers_required_incidents():
    runbook = (ROOT / "docs/production-readiness/cycle9-operations-runbook.md").read_text().lower()

    for phrase in [
        "failed import",
        "stuck worker",
        "bad fee config",
        "ai outage",
        "email/push failure",
        "backup",
        "restore",
    ]:
        assert phrase in runbook


def test_runbook_defines_alert_thresholds_and_business_metrics():
    runbook = (ROOT / "docs/production-readiness/cycle9-operations-runbook.md").read_text()

    assert "p95 API latency" in runbook
    assert "import failure rate" in runbook
    assert "AI budget rejection" in runbook
    assert "weekly receipt delivery failure" in runbook
