from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class StorageSize(str, Enum):
    small = "S"
    medium = "M"
    large = "L"


class ReservationStatus(str, Enum):
    pending = "pending_host_confirmation"
    confirmed = "confirmed"
    declined = "declined"
    expired = "expired"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    zipCode: str
    isHost: bool = False
    phone: Optional[str] = None
    backgroundCheckAccepted: bool = False


class UserPublic(BaseModel):
    id: str = Field(alias="_id")
    name: str
    email: EmailStr
    zipCode: str
    isHost: bool
    phone: Optional[str] = None
    createdAt: datetime
    verificationStatus: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ListingBase(BaseModel):
    title: str
    description: str
    size: StorageSize
    sizeSqft: Optional[float] = None
    pricePerMonth: float
    addressSummary: str
    zipCode: str
    images: List[str] = []
    availability: bool = True
    availableFrom: Optional[date] = None
    availableTo: Optional[date] = None
    bookingDeadline: Optional[date] = None
    rating: Optional[float] = None


class ListingCreate(ListingBase):
    sizeSqft: float
    availableFrom: date
    availableTo: date


class ListingPublic(ListingBase):
    id: str = Field(alias="_id")
    hostId: str
    hostVerified: Optional[bool] = None
    availableSqft: Optional[float] = None
    createdAt: datetime
    availableFrom: Optional[datetime] = None
    availableTo: Optional[datetime] = None
    bookingDeadline: Optional[datetime] = None

    model_config = ConfigDict(populate_by_name=True)


class ListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    size: Optional[StorageSize] = None
    pricePerMonth: Optional[float] = None
    addressSummary: Optional[str] = None
    zipCode: Optional[str] = None
    images: Optional[List[str]] = None
    availability: Optional[bool] = None
    availableFrom: Optional[date] = None
    availableTo: Optional[date] = None
    bookingDeadline: Optional[date] = None


class ReservationCreate(BaseModel):
    listingId: str
    startDate: date
    endDate: date
    sqftRequested: float
    numBoxes: int = Field(default=0, ge=0)
    insuranceDeclaredValue: Optional[float] = Field(default=None, ge=0)
    hasOwnInsurance: bool = False


class ReservationPublic(BaseModel):
    id: str = Field(alias="_id")
    listingId: str
    renterId: str
    startDate: date
    endDate: date
    sqftRequested: float = 0
    numBoxes: int = 0
    insuranceDeclaredValue: Optional[float] = None
    hasOwnInsurance: bool = False
    status: ReservationStatus
    basePrice: float = 0
    serviceFee: float
    boxCost: float = 0
    insuranceCost: float = 0
    totalPrice: float
    paymentStatus: str
    holdExpiresAt: datetime
    createdAt: datetime

    model_config = ConfigDict(populate_by_name=True)


class MessageCreate(BaseModel):
    reservationId: str
    content: str


class MessagePublic(BaseModel):
    id: str = Field(alias="_id")
    reservationId: str
    senderId: str
    content: str
    createdAt: datetime

    model_config = ConfigDict(populate_by_name=True)
