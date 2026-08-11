from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.security import create_access_token, get_password_hash, verify_password
from app.db import get_db
from app.deps.auth import get_current_user
from app.models.schemas import TokenResponse, UserCreate, UserPublic

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
        "backgroundCheckAccepted": user.backgroundCheckAccepted,
        # NOTE: this self-attestation bypass ("verified-mock" on a checkbox)
        # defeats the entire point of the Stripe Identity gate on listing
        # creation. It is a known Tier 2 issue, deleted in Phase 1 — see
        # docs/DOCUMENTATION.md §7. Not removed here to keep Phase 0 scoped
        # to "the repo runs", not security fixes.
        "verificationStatus": "verified-mock" if user.backgroundCheckAccepted else "pending",
    }
    try:
        await db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    return UserPublic(**doc)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user = await db.users.find_one({"email": form_data.username})
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token(subject=user["_id"])
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserPublic)
async def me(current_user: dict = Depends(get_current_user)):
    return UserPublic(**current_user)
