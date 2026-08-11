"""Seed demo data for local development.

Fixes two v1 defects:
  - README credentials now match what this script actually creates
    (v1's README said host@example.com; the script seeded adivy001@ucr.edu).
  - Deletes are scoped to seeded data only, tagged with `seedSource: "seed.py"`.
    v1 ran `db.listings.delete_many({})`, wiping every listing in the
    database on every run, not just seeded ones.

Listings are set in the go-to-market college towns named in the business
brief (Austin, Dallas, San Antonio, College Station, TX) rather than the
v1 prototype's San Francisco / Riverside data, since that's where Spacio
actually plans to launch.
"""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.core.security import get_password_hash

SEED_SOURCE = "seed.py"

HOST_EMAIL = "host@spacio.dev"
RENTER_EMAIL = "renter@spacio.dev"
DEMO_PASSWORD = "password123"


async def seed() -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.database_name]

    # Scoped deletes: only ever remove documents this script created.
    await db.users.delete_many({"email": {"$in": [HOST_EMAIL, RENTER_EMAIL]}})
    await db.listings.delete_many({"seedSource": SEED_SOURCE})

    now = datetime.utcnow()

    host_id = str(uuid4())
    host = {
        "_id": host_id,
        "name": "Demo Host",
        "email": HOST_EMAIL,
        "hashed_password": get_password_hash(DEMO_PASSWORD),
        "zipCode": "78705",
        "isHost": True,
        "phone": "555-1000",
        "createdAt": now,
        "backgroundCheckAccepted": True,
        # Set directly here (not via the registration bypass in auth.py) —
        # this is a fixture, not a demonstration of the self-attestation
        # bug that bypass represents.
        "verificationStatus": "verified",
    }

    renter_id = str(uuid4())
    renter = {
        "_id": renter_id,
        "name": "Demo Renter",
        "email": RENTER_EMAIL,
        "hashed_password": get_password_hash(DEMO_PASSWORD),
        "zipCode": "78705",
        "isHost": False,
        "phone": "555-2000",
        "createdAt": now,
        "backgroundCheckAccepted": False,
        "verificationStatus": "pending",
    }

    available_from = now
    available_to = now + timedelta(days=180)

    listings = [
        {
            "title": "West Campus Garage Bay",
            "description": "Half of a two-car garage, walking distance to UT Austin. Great for a dorm move-out.",
            "size": "M",
            "sizeSqft": 120,
            "pricePerMonth": 45.0,
            "addressSummary": "West Campus, Austin, TX",
            "zipCode": "78705",
        },
        {
            "title": "Hyde Park Spare Closet",
            "description": "Climate-controlled hallway closet, great for boxes and documents.",
            "size": "S",
            "sizeSqft": 40,
            "pricePerMonth": 28.0,
            "addressSummary": "Hyde Park, Austin, TX",
            "zipCode": "78751",
        },
        {
            "title": "Riverside Storage Room",
            "description": "Spare room in a single-family home, ground floor, easy load-in.",
            "size": "L",
            "sizeSqft": 180,
            "pricePerMonth": 62.0,
            "addressSummary": "Riverside, Austin, TX",
            "zipCode": "78741",
        },
        {
            "title": "Richardson Garage Corner",
            "description": "Corner of an attached garage near UT Dallas, ideal for bins and a bike.",
            "size": "S",
            "sizeSqft": 55,
            "pricePerMonth": 32.0,
            "addressSummary": "Richardson, TX",
            "zipCode": "75080",
        },
        {
            "title": "UTSA Area Carport Spot",
            "description": "Covered carport space near UTSA, good for a compact car or gear.",
            "size": "M",
            "sizeSqft": 130,
            "pricePerMonth": 48.0,
            "addressSummary": "Near UTSA, San Antonio, TX",
            "zipCode": "78249",
        },
        {
            "title": "College Station Spare Bedroom",
            "description": "Extra bedroom for clean, indoor storage near Texas A&M.",
            "size": "M",
            "sizeSqft": 140,
            "pricePerMonth": 50.0,
            "addressSummary": "College Station, TX",
            "zipCode": "77840",
        },
        {
            "title": "North Austin Basement Nook",
            "description": "Small basement nook, great for seasonal items and suitcases.",
            "size": "S",
            "sizeSqft": 35,
            "pricePerMonth": 25.0,
            "addressSummary": "North Austin, TX",
            "zipCode": "78758",
        },
        {
            "title": "East Dallas Attic Space",
            "description": "Insulated attic space, accessible by pull-down stairs.",
            "size": "L",
            "sizeSqft": 160,
            "pricePerMonth": 55.0,
            "addressSummary": "East Dallas, TX",
            "zipCode": "75218",
        },
    ]

    listing_docs = [
        {
            "_id": str(uuid4()),
            "hostId": host_id,
            "images": [],
            "availability": True,
            "availableFrom": available_from,
            "availableTo": available_to,
            "bookingDeadline": None,
            # Honest: no review system exists yet (Phase 4), so no
            # fabricated rating like v1's hardcoded 4.7.
            "rating": None,
            "createdAt": now,
            "seedSource": SEED_SOURCE,
            **listing,
        }
        for listing in listings
    ]

    await db.users.insert_one(host)
    await db.users.insert_one(renter)
    await db.listings.insert_many(listing_docs)

    print("Seed complete.")
    print(f"Host login:   {HOST_EMAIL} / {DEMO_PASSWORD}")
    print(f"Renter login: {RENTER_EMAIL} / {DEMO_PASSWORD}")
    print(f"Seeded {len(listing_docs)} listings across Texas college towns.")


if __name__ == "__main__":
    asyncio.run(seed())
