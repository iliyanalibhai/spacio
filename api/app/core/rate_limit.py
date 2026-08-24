"""A single shared Limiter instance.

Defined here (not in main.py) so routers can import and apply `@limiter.limit(...)`
to individual endpoints without a circular import on `main`, which itself
imports the routers.

Storage is in-memory by default (per `slowapi`/`limits` defaults), which is
fine for Spacio's current single-process deployment. It would under-count
requests behind a multi-replica deployment, since each process would track
its own counts — a shared backend (e.g. Redis, via `limits`' storage URI
support) would be needed before scaling out horizontally.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
