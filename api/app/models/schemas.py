from datetime import date, datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class StorageSize(str, Enum):
    small = "S"
    medium = "M"
    large = "L"


class ReservationStatus(str, Enum):
    pending = "pending_host_confirmation"
    confirmed = "confirmed"
    declined = "declined"
    expired = "expired"
    cancelled = "cancelled"


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    zipCode: str
    isHost: bool = False
    phone: Optional[str] = None


class UserPublic(BaseModel):
    id: str = Field(alias="_id")
    name: str
    email: EmailStr
    zipCode: str
    isHost: bool
    phone: Optional[str] = None
    createdAt: datetime
    verificationStatus: Optional[str] = None
    # Stripe Connect (host payouts). `stripeConnectOnboarded` is set True
    # only by the account.updated webhook / the /payments/connect/status
    # refresh, when the connected account has charges_enabled AND
    # payouts_enabled. Absent on non-host users. See docs/DOCUMENTATION.md §3.
    stripeConnectAccountId: Optional[str] = None
    stripeConnectOnboarded: bool = False

    model_config = ConfigDict(populate_by_name=True)


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
    # Unlike `rating` (genuinely null until the first review — see below),
    # reviewCount is a real count from the moment a listing exists, so it
    # defaults to 0 rather than None.
    reviewCount: int = 0
    # ZIP-centroid coordinates, projected from the stored `location` GeoJSON
    # Point (see the validator below). `distanceMiles` is only populated by the
    # radius-search path in GET /listings and by /matching/recommend when the
    # request carries an origin. See app/services/geo.py, docs/DOCUMENTATION.md §3.
    lat: Optional[float] = None
    lng: Optional[float] = None
    distanceMiles: Optional[float] = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def _lift_location(cls, data: object) -> object:
        """Expose the stored `location` GeoJSON Point as flat `lat`/`lng`.

        Mongo stores `location` as `{"type": "Point", "coordinates": [lng, lat]}`
        (the 2dsphere / $geoNear format). Callers do
        `ListingPublic.model_validate(doc)` on the raw document, so unpack it
        here rather than at every call site. Never mutates the input dict.
        """
        if not isinstance(data, dict):
            return data
        location = data.get("location")
        if (
            isinstance(location, dict)
            and data.get("lat") is None
            and data.get("lng") is None
        ):
            coordinates = location.get("coordinates")
            if isinstance(coordinates, (list, tuple)) and len(coordinates) == 2:
                return {**data, "lat": coordinates[1], "lng": coordinates[0]}
        return data


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
    refundedAmount: Optional[float] = None
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


class ReviewCreate(BaseModel):
    reservationId: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=1000)


class ReviewPublic(BaseModel):
    id: str = Field(alias="_id")
    listingId: str
    reservationId: str
    renterId: str
    rating: int
    comment: Optional[str] = None
    createdAt: datetime

    model_config = ConfigDict(populate_by_name=True)
