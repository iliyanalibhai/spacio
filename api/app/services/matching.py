"""Free-text listing matching.

This is a keyword-lookup heuristic, not semantic search. Phase 3 replaces it
with embeddings (sentence-transformers/all-MiniLM-L6-v2) over listing title
+ description, reranked by distance, price, and availability — see
docs/DOCUMENTATION.md §3 and §11. Ported from v1 largely as-is since it's
functionally honest about what it does (no fabricated "AI" claims to fix
here, unlike ai_pricing.py).
"""

import re
from typing import Dict, List

SizeBuckets = {"S": (0, 60), "M": (60, 150), "L": (150, 1_000)}

KEYWORD_SIZE_HINTS: Dict[str, float] = {
    "small": 40,
    "medium": 80,
    "large": 200,
    "box": 30,
    "boxes": 60,
    "bike": 50,
    "bikes": 70,
    "furniture": 180,
    "couch": 150,
    "sofa": 150,
    "bed": 120,
}


def _estimate_sqft_from_query(query: str) -> float:
    q = query.lower()
    estimate = 80.0
    for word, sqft in KEYWORD_SIZE_HINTS.items():
        if word in q:
            estimate = max(estimate, sqft)
    nums = re.findall(r"\d+", q)
    if nums:
        count = max(int(n) for n in nums)
        estimate = max(estimate, min(200, count * 8))
    return estimate


def _bucket_from_sqft(sqft: float) -> str:
    if sqft <= 60:
        return "S"
    if sqft <= 150:
        return "M"
    return "L"


def score_listing(
    listing: dict, target_bucket: str, target_zip: str | None, keywords: List[str]
) -> float:
    score = 0.0
    size = listing.get("size")
    if size == target_bucket:
        score += 2.0
    elif (size, target_bucket) in {("S", "M"), ("M", "S"), ("M", "L"), ("L", "M")}:
        score += 1.0

    if target_zip and listing.get("zipCode") == target_zip:
        score += 2.0

    desc = (listing.get("description") or "").lower() + " " + (listing.get("title") or "").lower()
    for kw in keywords:
        if kw in desc:
            score += 0.5

    price = listing.get("pricePerMonth") or 0
    if price > 0:
        score += 50 / price

    return score


def match_listings(
    listings: List[dict], query: str, zip_code: str | None = None
) -> tuple[List[dict], str]:
    sqft = _estimate_sqft_from_query(query)
    bucket = _bucket_from_sqft(sqft)
    keywords = [k for k in KEYWORD_SIZE_HINTS.keys() if k in query.lower()]

    scored = []
    for lst in listings:
        s = score_listing(lst, bucket, zip_code, keywords)
        scored.append((s, lst))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [lst for _, lst in scored[:5]]

    explanation = (
        f"Recommended {bucket}-size spaces"
        f"{' near ' + zip_code if zip_code else ''}"
        f" that fit your needs for {', '.join(keywords) if keywords else 'your described items'}."
    )
    return top, explanation
