import hashlib
import hmac
import time


def sign(body: bytes, secret: str, timestamp: int | None = None) -> str:
    """`t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<body>">`."""
    t = int(time.time()) if timestamp is None else timestamp
    mac = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={t},v1={mac}"
