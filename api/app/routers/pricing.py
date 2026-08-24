from typing import Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.rate_limit import limiter
from app.services.ai_pricing import suggest_price

router = APIRouter()


class PriceSuggestionRequest(BaseModel):
    size: Literal["S", "M", "L"] = Field(..., description="Size bucket")
    zipCode: str
    indoor: Optional[bool] = False
    title: Optional[str] = None
    description: Optional[str] = None


class PriceSuggestionResponse(BaseModel):
    suggestedPrice: float
    minPrice: float
    maxPrice: float
    explanation: str


@router.post("/suggest", response_model=PriceSuggestionResponse)
@limiter.limit("20/minute")
async def pricing_suggest(request: Request, payload: PriceSuggestionRequest):
    if payload.size is None:
        raise HTTPException(status_code=400, detail="size is required")
    suggested, min_price, max_price, explanation = suggest_price(
        size=payload.size,
        zip_code=payload.zipCode,
        indoor=payload.indoor,
    )
    return PriceSuggestionResponse(
        suggestedPrice=suggested,
        minPrice=min_price,
        maxPrice=max_price,
        explanation=explanation,
    )
