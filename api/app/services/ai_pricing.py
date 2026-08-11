"""Host-facing price suggestion service.

Despite the "AI pricing" label in the UI, this is a deterministic heuristic,
not a trained model — Spacio has no booking history yet to train one on. It
exists so the create-listing flow has *some* starting suggestion, honestly
described as an estimate.

The v1 prototype's version of this file was dishonest: it multiplied its
output by `random.uniform(0.95, 1.05)` and told users "a slight variation is
applied so suggestions feel more human." That string described noise as a
feature. This version is deterministic — same input, same output — and every
user-facing string says plainly that it's a placeholder.

Phase 3 replaces this with a real gradient-boosted quantile regressor
trained on a clearly-labeled synthetic comps dataset (see
docs/DOCUMENTATION.md §6). Nothing here should be read as, or described as,
that model.
"""

from typing import Literal, Optional

# Chosen to land within the $25-70/month business range (see
# docs/DOCUMENTATION.md §5), unlike the v1 prototype's $60/$100/$140, which
# didn't match the business model at all.
BASE_PRICES_BY_SIZE: dict[str, float] = {"S": 28.0, "M": 42.0, "L": 58.0}

# Placeholder demand signal keyed on the go-to-market college towns (Austin,
# Dallas, San Antonio, College Station). Not derived from any real demand
# data — Phase 3's real model replaces this with an actual ZIP-level signal.
HIGH_DEMAND_ZIP_PREFIXES = {"787", "750", "782", "778"}

INDOOR_PREMIUM = 5.0
MIN_PRICE = 25.0
MAX_PRICE = 70.0


def suggest_price(
    size: Literal["S", "M", "L"],
    zip_code: str,
    indoor: Optional[bool] = None,
) -> tuple[float, float, float, str]:
    size = size.upper()
    base = BASE_PRICES_BY_SIZE.get(size, BASE_PRICES_BY_SIZE["M"])
    factors: list[str] = []

    demand_factor = 1.0
    if zip_code and zip_code[:3] in HIGH_DEMAND_ZIP_PREFIXES:
        demand_factor = 1.1
        factors.append("+10% high-demand college-town adjustment")

    indoor_premium = INDOOR_PREMIUM if indoor else 0.0
    if indoor:
        factors.append(f"+${INDOOR_PREMIUM:.0f} indoor premium")

    raw = base * demand_factor + indoor_premium
    suggested = round(min(MAX_PRICE, max(MIN_PRICE, raw)), 2)
    min_price = round(min(MAX_PRICE, max(MIN_PRICE, suggested * 0.85)), 2)
    max_price = round(min(MAX_PRICE, max(MIN_PRICE, suggested * 1.15)), 2)

    factor_text = " ".join(factors) if factors else "no adjustments"
    explanation = (
        f"Placeholder estimate for a {size}-size space in {zip_code or 'your area'}: "
        f"base ${base:.0f}, {factor_text}. This is a fixed heuristic, not a "
        f"trained model — Spacio doesn't have booking history yet. A real "
        f"pricing model trained on comparable data is planned; see the "
        f"project documentation for status."
    )
    return suggested, min_price, max_price, explanation
