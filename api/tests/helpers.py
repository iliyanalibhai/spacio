"""Shared test helpers."""

import hmac
import time
from hashlib import sha256


def sign_stripe_payload(payload: bytes, secret: str, timestamp: int | None = None) -> str:
    """Build a Stripe-scheme `stripe-signature` header value for `payload`.

    Lets webhook tests exercise the real `stripe.Webhook.construct_event`
    signature check instead of mocking the stripe library. Signing with a
    wrong `secret` produces a header that verification rejects (400).
    """
    timestamp = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{timestamp}.".encode() + payload
    signature = hmac.new(secret.encode(), signed_payload, sha256).hexdigest()
    return f"t={timestamp},v1={signature}"
