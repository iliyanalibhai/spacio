import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.paths import IMAGES_DIR, UPLOAD_DIR
from app.core.rate_limit import limiter
from app.db import ensure_indexes, get_db
from app.routers import (
    auth,
    listings,
    reservations,
    messages,
    payments,
    pricing,
    matching,
    verification,
)
from app.services.hold_expiry import run_forever as run_hold_expiry_sweep


@asynccontextmanager
async def lifespan(app: FastAPI):
    await ensure_indexes()

    # Without Stripe configured, no host can finish Connect onboarding, so
    # no listing (and therefore no reservation) can exist yet — see
    # Settings.stripe_configured and app/services/hold_expiry.py.
    sweep_task = asyncio.create_task(run_hold_expiry_sweep(get_db())) if settings.stripe_configured else None

    yield

    if sweep_task is not None:
        sweep_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sweep_task


app = FastAPI(
    title="Spacio API",
    version="0.1.0",
    description="Peer-to-peer storage marketplace API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
# slowapi's handler is typed for its own RateLimitExceeded, narrower than the
# generic Exception Starlette's add_exception_handler expects — a known
# slowapi/mypy friction point, not a real type error.
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]
app.add_middleware(SlowAPIMiddleware)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(listings.router, prefix="/listings", tags=["listings"])
app.include_router(reservations.router, prefix="/reservations", tags=["reservations"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(pricing.router, prefix="/pricing", tags=["pricing"])
app.include_router(matching.router, prefix="/matching", tags=["matching"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(verification.router, prefix="/verification", tags=["verification"])

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

IMAGES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")
