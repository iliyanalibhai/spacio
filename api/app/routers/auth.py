from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db import get_db
from app.deps.auth import ACCESS_TOKEN_COOKIE, get_current_user
from app.models.schemas import UserCreate, UserPublic

router = APIRouter()


@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: AsyncIOMotorDatabase = Depends(get_db)):
    user_id = str(uuid4())
    now = datetime.utcnow()
    doc = {
        "_id": user_id,
        "name": user.name,
        "email": user.email,
        "hashed_password": get_password_hash(user.password),
        "zipCode": user.zipCode,
        "isHost": user.isHost,
        "phone": user.phone,
        "createdAt": now,
        # The only way this ever becomes "verified" is the real Stripe
        # Identity flow (app/routers/verification.py: a session started via
        # POST /verification/create-session, confirmed by the
        # POST /verification/webhook handler). Registration can never set it
        # directly — see docs/DOCUMENTATION.md §7.
        "verificationStatus": "pending",
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    return UserPublic.model_validate(doc)


@router.post("/login", response_model=UserPublic)
@limiter.limit("5/minute")
async def login(
    request: Request,  # required by @limiter.limit, which reads the caller's IP off it
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(subject=user["_id"])
    # httpOnly: page JS can never read this, so an XSS bug can no longer
    # steal the session by reading it out of localStorage (the old model —
    # see docs/DOCUMENTATION.md §7). The browser still attaches it
    # automatically on every request to this API.
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return UserPublic.model_validate(user)


@router.post("/logout")
async def logout(response: Response):
    # JS can't clear an httpOnly cookie itself (that's the point of
    # httpOnly), so logging out has to be a real request the server
    # answers by telling the browser to drop it.
    response.delete_cookie(key=ACCESS_TOKEN_COOKIE, path="/")
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)):
    return UserPublic.model_validate(current_user)
