from app.observability.metrics import get_metrics, _get_conn
from datetime import datetime, timezone

def _line(name: str, value, labels: str = "") -> str:
    """Emit a single Prometheus-format line."""
    if labels:
        return f"{name}{{{labels}}} {value}"
    return f"{name} {value}"

def get_prometheus_metrics() -> str:
    """
    Return metrics in Prometheus text exposition format.
    https://prometheus.io/docs/instrumenting/exposition_formats/
    """
    m = get_metrics(window="all")
    lines = []

    # HELP + TYPE headers
    lines.append("# HELP copilot_requests_total Total requests processed")
    lines.append("# TYPE copilot_requests_total counter")
    lines.append(_line("copilot_requests_total", m["total_requests"]))

    lines.append("# HELP copilot_blocked_total Blocked requests")
    lines.append("# TYPE copilot_blocked_total counter")
    lines.append(_line("copilot_blocked_total", m["blocked_count"]))

    lines.append("# HELP copilot_block_rate_pct Block rate as percentage")
    lines.append("# TYPE copilot_block_rate_pct gauge")
    lines.append(_line("copilot_block_rate_pct", m["block_rate_pct"]))

    lines.append("# HELP copilot_latency_ms Request latency in milliseconds")
    lines.append("# TYPE copilot_latency_ms gauge")
    lines.append(_line("copilot_latency_ms", m["latency_ms"]["avg"], 'quantile="avg"'))
    lines.append(_line("copilot_latency_ms", m["latency_ms"]["p50"], 'quantile="0.5"'))
    lines.append(_line("copilot_latency_ms", m["latency_ms"]["p95"], 'quantile="0.95"'))
    lines.append(_line("copilot_latency_ms", m["latency_ms"]["p99"], 'quantile="0.99"'))

    lines.append("# HELP copilot_cost_usd_total Total cost in USD")
    lines.append("# TYPE copilot_cost_usd_total counter")
    lines.append(_line("copilot_cost_usd_total", m["cost_usd"]["total"]))

    lines.append("# HELP copilot_tokens_input_total Total input tokens")
    lines.append("# TYPE copilot_tokens_input_total counter")
    lines.append(_line("copilot_tokens_input_total", m["tokens"]["input"]))

    lines.append("# HELP copilot_tokens_output_total Total output tokens")
    lines.append("# TYPE copilot_tokens_output_total counter")
    lines.append(_line("copilot_tokens_output_total", m["tokens"]["output"]))

    lines.append("# HELP copilot_avg_retrieved_docs Average docs per query")
    lines.append("# TYPE copilot_avg_retrieved_docs gauge")
    lines.append(_line("copilot_avg_retrieved_docs", m["avg_retrieved_docs"]))

    # Per-reason block counters
    if m["block_reasons"]:
        lines.append("# HELP copilot_block_reasons_total Block counts by reason")
        lines.append("# TYPE copilot_block_reasons_total counter")
        for reason, count in m["block_reasons"].items():
            lines.append(_line("copilot_block_reasons_total", count, f'reason="{reason}"'))

    return "\n".join(lines) + "\n"

