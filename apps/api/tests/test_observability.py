"""Logs carry the active trace/span id so logs and traces can be pivoted together."""

from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider

from app.core.logging import _add_trace_correlation


def test_log_gets_trace_ids_inside_a_span() -> None:
    tracer = TracerProvider().get_tracer("test")
    with tracer.start_as_current_span("unit"):
        out = _add_trace_correlation(None, "info", {"event": "x"})
    assert len(out["trace_id"]) == 32
    assert len(out["span_id"]) == 16


def test_log_has_no_trace_ids_without_a_span() -> None:
    out = _add_trace_correlation(None, "info", {"event": "x"})
    assert "trace_id" not in out
    assert "span_id" not in out
