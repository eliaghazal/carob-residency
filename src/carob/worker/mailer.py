"""Email. In development and staging, SMTP goes to Mailpit (http://localhost:8025)."""

import logging
import smtplib
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from carob.config import get_settings

log = logging.getLogger(__name__)


class Mailer(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpMailer:
    def __init__(self, host: str, port: int, sender: str) -> None:
        self.host, self.port, self.sender = host, port, sender

    def send(self, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.sender, to, subject
        message.set_content(body)
        with smtplib.SMTP(self.host, self.port, timeout=5) as smtp:
            smtp.send_message(message)


class LogMailer:
    """For tests and drills: records mail in the log instead of sending it."""

    def send(self, to: str, subject: str, body: str) -> None:
        log.info("mail", extra={"fields": {"to": to, "subject": subject}})


@lru_cache
def get_mailer() -> Mailer:
    settings = get_settings()
    if settings.mailer == "log":
        return LogMailer()
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.mail_from)
