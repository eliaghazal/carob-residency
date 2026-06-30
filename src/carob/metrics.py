"""Prometheus metrics.

Route labels use the route template ("/v1/transfers/{transfer_id}"), never raw paths.
"""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter("carob_http_requests_total", "HTTP requests", ["method", "route", "status"])
HTTP_LATENCY = Histogram(
    "carob_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
WEBHOOKS = Counter("carob_webhooks_total", "Paystub webhook deliveries by result", ["result"])
TRANSFERS = Counter("carob_transfers_total", "Completed transfers", ["currency"])

# Updated by the worker every 30 seconds (it serves its own /metrics).
TOPUPS_PENDING = Gauge("carob_topups_pending", "Top-ups waiting for the provider")
TOPUPS_PENDING_OLDEST = Gauge("carob_topups_pending_oldest_seconds", "Age of the oldest pending top-up")
OUTBOX_DUE = Gauge("carob_outbox_due", "Outbox messages due for delivery")
OUTBOX_OLDEST = Gauge("carob_outbox_oldest_due_seconds", "Age of the oldest undelivered outbox message")
OUTBOX_DELIVERED = Counter("carob_outbox_delivered_total", "Outbox messages delivered", ["topic"])
OUTBOX_ERRORS = Counter("carob_outbox_errors_total", "Outbox delivery errors", ["topic"])
