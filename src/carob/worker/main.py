"""The worker: delivers outbox messages and keeps operational gauges current.

    carob-worker                 # run forever
    carob-worker --once          # deliver what is due now, then exit (tests, drills)

Several workers can run at once: each claims messages with
`FOR UPDATE SKIP LOCKED`, so no message is delivered twice at the same time.
"""

import argparse
import logging
import signal
import time
from datetime import UTC, datetime, timedelta

from prometheus_client import start_http_server
from sqlalchemy import func, select, text

from carob.db import session_scope
from carob.logging import configure_logging
from carob.metrics import (
    OUTBOX_DELIVERED,
    OUTBOX_DUE,
    OUTBOX_ERRORS,
    OUTBOX_OLDEST,
    TOPUPS_PENDING,
    TOPUPS_PENDING_OLDEST,
)
from carob.models import OutboxMessage, Topup
from carob.worker.handlers import HANDLERS

log = logging.getLogger("carob.worker")

BATCH = 20
MAX_ATTEMPTS = 10
_stopping = False


def _stop(_signum: int, _frame: object) -> None:
    global _stopping
    _stopping = True


def backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(2**attempts, 3600))


def deliver_due() -> int:
    """Claim and deliver one batch of due messages. Returns how many were attempted."""
    with session_scope() as session:
        messages = list(
            session.scalars(
                select(OutboxMessage)
                .where(
                    OutboxMessage.delivered_at.is_(None),
                    OutboxMessage.failed_at.is_(None),
                    OutboxMessage.available_at <= func.now(),
                )
                .order_by(OutboxMessage.id)
                .limit(BATCH)
                .with_for_update(skip_locked=True)
            )
        )
        for message in messages:
            handler = HANDLERS.get(message.topic)
            try:
                if handler is None:
                    raise LookupError(f"no handler for {message.topic}")
                with session.begin_nested():
                    handler(session, message.payload)
                message.delivered_at = datetime.now(UTC)
                OUTBOX_DELIVERED.labels(message.topic).inc()
                log.info(
                    "outbox delivered", extra={"fields": {"outbox_id": message.id, "topic": message.topic}}
                )
            except Exception as exc:
                message.attempts += 1
                message.last_error = f"{type(exc).__name__}: {exc}"[:500]
                if message.attempts >= MAX_ATTEMPTS:
                    message.failed_at = datetime.now(UTC)
                else:
                    message.available_at = datetime.now(UTC) + backoff(message.attempts)
                OUTBOX_ERRORS.labels(message.topic).inc()
                log.warning(
                    "outbox delivery failed",
                    extra={
                        "fields": {
                            "outbox_id": message.id,
                            "topic": message.topic,
                            "attempts": message.attempts,
                        }
                    },
                )
        return len(messages)


def housekeeping() -> None:
    """Refresh the gauges the on-call alerts use."""
    now = datetime.now(UTC)
    with session_scope() as session:
        pending, oldest = session.execute(
            select(func.count(), func.min(Topup.created_at)).where(Topup.status == "pending")
        ).one()
        TOPUPS_PENDING.set(pending)
        TOPUPS_PENDING_OLDEST.set((now - oldest).total_seconds() if oldest else 0)
        due, oldest_due = session.execute(
            text(
                "SELECT count(*), min(available_at) FROM outbox "
                "WHERE delivered_at IS NULL AND failed_at IS NULL AND available_at <= now()"
            )
        ).one()
        OUTBOX_DUE.set(due)
        OUTBOX_OLDEST.set((now - oldest_due).total_seconds() if oldest_due else 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Carob worker")
    parser.add_argument("--once", action="store_true", help="deliver what is due, then exit")
    parser.add_argument("--metrics-port", type=int, default=9101)
    parser.add_argument("--poll-seconds", type=float, default=1.0)
    args = parser.parse_args()
    configure_logging()

    if args.once:
        while deliver_due():
            pass
        housekeeping()
        return

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    start_http_server(args.metrics_port)
    log.info("worker started", extra={"fields": {"metrics_port": args.metrics_port}})
    last_housekeeping = 0.0
    while not _stopping:
        try:
            worked = deliver_due()
            if time.monotonic() - last_housekeeping > 30:
                housekeeping()
                last_housekeeping = time.monotonic()
        except Exception:
            log.exception("worker loop error")
            worked = 0
        if not worked:
            time.sleep(args.poll_seconds)
    log.info("worker stopped")


if __name__ == "__main__":
    main()
