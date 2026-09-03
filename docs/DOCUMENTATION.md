# Spacio — Engineering Documentation

This is a living engineering log and decision record. It is updated in the
same commit as any change it describes — if you find a stale section, that's
a bug, not a style choice.

## 1. Overview

Spacio is a peer-to-peer storage marketplace: people with unused space
(garages, closets, spare bedrooms) list it, and people who need storage rent
exactly the square footage they need, for exactly the dates they need it,
from a verified host nearby. See the [README](../README.md) for setup and
project structure. The full business thesis and customer research are
summarized in the decision log (§10) where they first became relevant to a
technical choice.

## 2. Architecture

```mermaid
flowchart LR
    subgraph Client
        Web["web (React + Vite + TS)"]
    end

    subgraph Backend
        API["api (FastAPI)"]
        Pricing["pricing model<br/>(app/ml/, LightGBM)"]
        Matching["matching<br/>(app/ml/, MiniLM embeddings)"]
    end

    subgraph Data
        Mongo[(MongoDB)]
    end

    subgraph ThirdParty["Third party"]
        Stripe["Stripe Identity<br/>(host verification)"]
        StripeConnect["Stripe Connect<br/>(host payout accounts)"]
        StripeCheckout["Stripe Checkout<br/>(renter payments)"]
    end

    Web -- "JSON over HTTPS, JWT bearer" --> API
    API -- "Motor (async)" --> Mongo
    API -- "verification sessions + webhooks" --> Stripe
    API -- "Express account + onboarding link, account.updated webhook" --> StripeConnect
    API -- "Checkout session (manual capture), checkout.session.* webhook" --> StripeCheckout
    API -- "price suggestion request" --> Pricing
    API -- "free-text Smart Match query" --> Matching
    Matching -- "reads / backfills listing embeddings" --> Mongo
```

### Request flow: creating a booking

```mermaid
sequenceDiagram
    participant R as Renter (web)
    participant A as API
    participant M as MongoDB

    R->>A: POST /reservations {listingId, sqftRequested, startDate, endDate, ...}
    A->>M: find listing by id
    A->>M: find overlapping reservations (status in [pending, confirmed])
    A->>A: sum reserved sqft; check sqftRequested <= totalSqft - reserved
    A->>A: calculate cost (base + service fee + box + insurance)
    A->>M: insert reservation (status=pending_host_confirmation, paymentStatus=pending_payment, holdExpiresAt=+24h)
    A-->>R: 201 ReservationPublic
    R->>A: POST /payments/checkout/{id} -> Stripe Checkout (card authorized, not charged)
    Note over A,M: Host later calls POST /reservations/{id}/approve (captures the card)<br/>or /decline (releases the hold). No action within 24h -> expired (scheduled job, Phase 4).
```

### Request flow: price suggestion (host creating a listing)

```mermaid
sequenceDiagram
    participant H as Host (web)
    participant A as API
    participant P as Pricing service

    H->>A: POST /pricing/suggest {size, zipCode, indoor, ...}
    A->>P: suggest_price(...)
    Note over P: Phase 0-2: deterministic heuristic, clearly labeled as a placeholder.<br/>Phase 3: real gradient-boosted quantile model trained on synthetic comps.
    P-->>A: {suggestedPrice, minPrice, maxPrice, explanation}
    A-->>H: 200 PriceSuggestionResponse
```

## 3. Tech stack decisions

### FastAPI

**What:** Python async web framework for the `api/` service.
**Why:** Native async support pairs naturally with Motor's async MongoDB
driver, so a slow database call doesn't block the event loop. Pydantic
integration gives us request/response validation and OpenAPI docs for free,
which matters when the frontend and ML service both consume this API.
**Alternatives considered:** Django REST Framework — more batteries included
(admin, ORM), but the ORM assumes a relational model we're deliberately not
using yet, and DRF's sync-by-default views fight async Mongo drivers. Flask —
lighter, but no built-in validation or async story as clean as FastAPI's.
**Tradeoffs accepted:** Smaller ecosystem than Django for things like admin
panels; we don't need one yet.
**Revisit if:** We need a full admin/back-office UI, at which point Django's
batteries might outweigh FastAPI's async-first design.

### MongoDB (via Motor, the async driver)

**What:** Document database, accessed via Motor.
**Why:** Listings have heterogeneous, evolving attributes (size, boxes,
insurance, future geo fields), and a document model avoids migrations during
rapid iteration. The v1 prototype was already built on Mongo, and there was
no correctness reason to force a rewrite before Phase 0 shipped.
**Alternatives considered:** Postgres + PostGIS + pgvector — stronger
relational integrity and real multi-document transactions, which matter for
bookings. Rejected for now because the rewrite cost isn't justified before
the product has real users or real bookings to migrate.
**Tradeoffs accepted:** No multi-document transactions by default, so the
reservation capacity check (read overlapping reservations, then insert) has a
theoretical race under concurrent writes — two renters could both pass the
capacity check for the last available square footage before either insert
commits. This is documented as a known limitation (§11); a
`findOneAndUpdate`-based reservation counter or a move to a transactional
store is the fix if booking volume ever makes this a real risk.
**Revisit if:** Bookings need real ACID transactions, or reporting queries
get relationally complex enough that Mongo's aggregation pipeline becomes
harder to reason about than SQL joins.

### React + Vite + TypeScript

**What:** Frontend framework, build tool, and type system for `web/`.
**Why:** Vite's dev server is fast enough to not think about; TypeScript
catches an entire class of "field renamed on the backend, frontend still
reads the old name" bugs that a JS-only prototype like v1 was exposed to.
**Alternatives considered:** Next.js — server-side rendering isn't a
requirement for an authenticated marketplace app behind a login wall, and it
adds a Node server we'd have to operate. Plain Vite + React keeps deployment
to a static host (Vercel) simple.
**Tradeoffs accepted:** No SSR means no meaningful SEO for listing pages if
that ever matters for organic discovery; acceptable for a college-town launch
that leans on ambassador-driven distribution, not search traffic.
**Revisit if:** Organic/SEO traffic becomes a real acquisition channel.

### Tailwind CSS

**What:** Utility-first CSS framework.
**Why:** The v1 prototype already used it effectively and consistently; a
switch to CSS Modules or styled-components would be a pure rewrite cost with
no correctness or business benefit.
**Alternatives considered:** None seriously — inherited a working choice.
**Tradeoffs accepted:** Utility classes in JSX read as noisy to newcomers;
mitigated by keeping components small once `App.tsx` is split (Phase 4).

### React Query (`@tanstack/react-query`)

**What:** Server-state cache and data-fetching library.
**Why:** Reservation and listing data changes from multiple actors (host
approves, renter books) and needs to stay in sync across components without
manual cache invalidation code. React Query's `invalidateQueries` pattern
does this with far less code than hand-rolled `useEffect` fetching, which is
what a from-scratch rewrite would otherwise produce.
**Alternatives considered:** Redux Toolkit Query — comparable, but pulls in
Redux's mental model for what is otherwise a fairly simple app with no
complex client-only state.
**Tradeoffs accepted:** Another dependency and cache-key discipline to
maintain (query keys must match between the component that fetches and the
mutation that invalidates).
**Revisit if:** Client-side state (not server state) becomes complex enough
to need a dedicated state manager.

### JWT auth (not sessions, not OAuth)

**What:** Stateless JSON Web Tokens issued on login, delivered as an
`HttpOnly` cookie (with an `Authorization: Bearer` header accepted as a
fallback for non-browser callers), validated per-request via `python-jose`.
**Why:** No server-side session store to run or scale; a single `/auth/me`
lookup validates the token and loads the current user. This matches a
FastAPI + Mongo stack without adding Redis just to hold sessions.
**Alternatives considered:** Server-side sessions — simpler to revoke
instantly, but requires a shared session store the moment we run more than
one API instance. Full OAuth (Google/Apple sign-in) — good for reducing
signup friction, but adds a provider integration before we've validated the
core product; deferred, not rejected.
**Tradeoffs accepted:** JWTs can't be revoked before they expire without an
explicit denylist (we don't have one yet — see §11). The token used to live in
`localStorage` (inherited from v1), which was vulnerable to XSS token theft;
fixed by moving to an `HttpOnly` cookie plus a 401 interceptor — see §7.
Cookie-based auth in turn means CSRF is the relevant threat model instead of
XSS-token-theft; mitigated with `SameSite=Lax`, without a separate CSRF
token yet (tracked in §11 as a possible defense-in-depth addition).
**Revisit if:** We add social login, or need instant token revocation (e.g.,
"log out all devices").

### Stripe Identity (host verification)

**What:** Stripe's document + selfie identity verification product, used to
gate host listing creation.
**Why:** Customer research (n=16) found host verification is the single
biggest trust lever (93.8% cited security of belongings, 87.5% cited trusting
unknown people as top objections). Building ID verification in-house is a
compliance and liability burden Spacio shouldn't take on directly; Stripe
already handles document authenticity checks, selfie matching, and PII
storage.
**Alternatives considered:** Persona, Onfido — comparable identity
verification products. Stripe was chosen because Checkout and Connect are
also on the roadmap (now built — see below), and consolidating on one vendor
for identity + payments simplifies both integration and reconciliation.
**Tradeoffs accepted:** Vendor lock-in to Stripe's verification UX and
pricing. Webhook-based status updates mean verification status can lag by
seconds; the frontend polls `/verification/status` to compensate (see
`VerificationCard` in the web app).
**Revisit if:** Stripe Identity pricing or coverage becomes a blocker in a
target market.

### Stripe Connect (host payouts)

**What:** Each host gets a Stripe **Express** connected account, created and
onboarded through a redirect flow that mirrors the Identity one
(`POST /payments/connect/onboard` returns a Stripe-hosted `AccountLink` URL;
`GET /payments/connect/status` + the `account.updated` webhook track when the
account reaches `charges_enabled && payouts_enabled`). Creating a listing is
gated on `stripeConnectOnboarded` in addition to identity `verified` — a
listing Spacio can't pay out on is not worth publishing.
**Why Express (not Standard or Custom):** Standard requires an OAuth
connection flow and gives the host a full Stripe dashboard login Spacio
doesn't want to expose; Custom makes Spacio responsible for building and
maintaining every screen of the onboarding + compliance UI and for handling
disputes/KYC directly. Express is the middle option: Stripe hosts onboarding,
KYC, tax forms, and a limited payout dashboard, while Spacio controls the
money movement and keeps its `application`-side fee.
**Accounts API version:** built on Connect **Accounts v1**
(`stripe.Account.create(type="express")`), which requires the "Accounts v1
support" feature toggle to be enabled on the platform account. Stripe now
steers *new* integrations toward Accounts v2 (`POST /v2/core/accounts`), but
v2 needs a much newer SDK than the pinned `stripe==10.11.0` and a different
onboarding + webhook surface. v1 is still fully supported (no end-of-life
date) and keeps this change small and low-risk; a v2 migration is a possible
future item. See §10.
**Tradeoffs accepted:** onboarding completion is only known via webhook /
poll, so there's a short window where a returning host shows "in review";
`PayoutOnboardingCard` polls to compensate. A host whose account is later
restricted by Stripe keeps their listings visible until the next approval
attempt fails (§11).

### Stripe Checkout + manual-capture payments

**What:** `POST /payments/checkout/{reservation_id}` creates a Stripe
Checkout Session for the reservation's `totalPrice` and returns a
Stripe-hosted URL, same redirect shape as Identity/Connect. The Session's
PaymentIntent is created with `capture_method="manual"` — the renter's card
is *authorized* (funds held) when Checkout completes, not charged yet. The
host's approval is the actual charge:
`reservations.approve_reservation` calls
`services/reservation_payments.py::capture_reservation_payment`, which
raises rather than confirming the reservation if the capture fails, so a
"confirmed" reservation always means the renter was actually charged. A
decline, an abandoned/expired Checkout, or the renter cancelling their own
still-pending reservation instead calls `cancel_reservation_payment`, which
releases the hold via `PaymentIntent.cancel` (best-effort — a Stripe error
there must never block the decline itself). `GET
/payments/checkout/status/{reservation_id}` polls the live PaymentIntent
status, same pattern as `connect_status`/`get_verification_status`: never
500s on a Stripe error, falls back to the stored value.
**Money split:** the Session's `payment_intent_data` sets
`transfer_data.destination` to the host's Connect account and
`application_fee_amount` to the reservation's own `serviceFee` (already
20% of the base price — the same number already shown to the renter in the
booking quote). So Spacio's cut and the host's payout are read directly off
numbers the renter already saw, not recomputed separately at charge time.
**Why manual capture, not automatic:** the business flow requires a host
approval step *before* money moves — an automatically-captured charge would
mean the renter is billed for a reservation the host might still decline.
Manual capture lets Checkout authorize the card immediately (so the renter
commits at booking time, same as v1's Stripe checkout link) while deferring
the actual charge until the host acts, and cleanly maps decline/expiry to
"release the hold" instead of "charge then refund."
**`paymentStatus` values:** `pending_payment` (reservation created, no
successful Checkout yet) → `authorized` (Checkout completed,
`checkout.session.completed` webhook or the status-poll endpoint recorded
the PaymentIntent) → `captured` (host approved) **or** `canceled` (host
declined / renter cancelled while pending) **or** `payment_expired`
(Checkout Session expired unused — `checkout.session.expired`; the renter
can retry from "My Reservations").
**Tradeoffs accepted:** Stripe's own authorization hold on a card only
lasts about 7 days; since the 24-hour hold-expiry sweep still isn't wired to
a scheduled job (§11), a reservation the host never acts on can in
principle sit "authorized" past that window, at which point `approve` would
call `PaymentIntent.capture` on an authorization the issuing bank has
already released and get a Stripe error (surfaced as the existing 502, not
a silent failure) — real, but a narrower and more honestly-surfaced version
of a limitation that already existed before this PR. Checkout's amount and
the Connect destination are always read from the server-stored reservation
and listing documents, never from client input, so there's no path for a
renter to alter what they're charged or where it's sent.
**Revisit if:** the 24-hour hold-expiry sweep ships (Phase 4) — it should
also cancel any still-`authorized` PaymentIntent, not just flip
`status` to `expired`.

### Pricing model (real model as of Phase 2)

**What:** `/pricing/suggest` returns a suggested monthly price for a new
listing from a trained model — three LightGBM quantile regressors
(`api/app/services/ai_pricing.py`, `app/ml/`) — replacing the Phase 0/1
deterministic heuristic.
**Why a real model now:** Phase 0/1 shipped a deterministic heuristic
instead of a trained model because there was no booking history to train on
— a fabricated "AI" that silently randomizes its output (the v1 prototype's
behavior) is worse than an honestly-labeled placeholder. Phase 2 replaces
that placeholder with a real gradient-boosted quantile regressor trained on
a clearly-labeled *synthetic* comps dataset — still not real booking data
(there still isn't any), but a genuine trained model rather than a fixed
formula. Full write-up in §6.
**Alternatives considered:** Waiting for real booking history before
training anything. Rejected for the same reason the heuristic shipped early
in Phase 0/1: the create-listing flow benefits from a real estimate now, as
long as the synthetic training data is stated plainly and never described
as real comps.
**Tradeoffs accepted:** Real accuracy on actual bookings is unknown — the
model's evaluated MAE (§6) only measures how well it recovered a synthetic
formula, not real-world pricing behavior. Must be retrained on real booking
history once Spacio has enough of it.
**Revisit if:** Real booking/listing-price history accumulates (tracked in
§10 decision log).

### Embeddings / semantic search

**Built in Phase 2 (2026-08-27).** `POST /matching/recommend` ("Smart
Match") is now real semantic search, replacing the v1 prototype's ~12-word
keyword dictionary (`KEYWORD_SIZE_HINTS`).

**How it works:**

- **Model:** `sentence-transformers/all-MiniLM-L6-v2` — a 6-layer distilled
  BERT, ~22M params, 384-dimensional output. Small enough to run on CPU on
  a modest box; widely benchmarked. Loaded once per process, lazily, on
  first use (`app/ml/embeddings.py`).
- **Indexing:** each listing's `title` + `description` is embedded into a
  unit vector when the listing is created or edited (`app/routers/listings.py`),
  stored on the listing document as `embedding` (§4). Listings that predate
  the feature, or were written while the model was unavailable, are
  embedded and persisted lazily the first time `/matching/recommend` sees
  them (`_ensure_listing_embeddings`).
- **Query time:** the renter's free-text query is embedded the same way,
  then scored against every listing vector by **cosine similarity** — which,
  because all vectors are L2-normalized, is just a dot product. This is the
  dominant ranking signal.
- **Reranking:** the semantic score is then nudged by the structured
  signals — exact ZIP match (+0.15) or ZIP3-prefix match (+0.07), a small
  price term (≤0.08, favouring cheaper), and, if the caller passes dates, an
  availability-window fit bonus / miss penalty. Weights live as named
  constants at the top of `app/services/matching.py`; they're deliberately
  small so a far-away exact-text match never outranks a nearby near-match,
  but they break ties among similarly-relevant listings. Not formally tuned
  — there's no labelled relevance data to tune against (see limitations).
- **Why "bicycle" now finds "great for cyclists":** the keyword version
  matched substrings, so a query and a listing that meant the same thing
  but shared no words scored zero. Embeddings place text near other text
  with similar *meaning*, so synonyms, paraphrases and descriptions
  ("somewhere for my road bike") all land close to a listing that says
  "ideal for cyclists".

**Design choices:**

- `app/services/matching.py` is pure and model-free: it takes the query
  vector and listings that already carry an `embedding`, and does nothing
  but arithmetic. It never imports torch, so it unit-tests instantly with
  hand-built toy vectors (`tests/test_matching.py::TestRanking`). Producing
  the vectors is the router's job.
- **Brute-force comparison, no ANN index.** `/matching/recommend` loads all
  listings and scores them in a loop. At Spacio's scale (hundreds of
  listings) this is trivially fast and an approximate-nearest-neighbour
  index (FAISS, `pgvector`, Atlas Vector Search) would be premature. This is
  the obvious thing to revisit if the listing count grows by orders of
  magnitude.
- **Graceful degradation.** `EMBEDDINGS_ENABLED=false` (or any model
  load/download failure) makes `/matching/recommend` fall back to a
  non-semantic ranking (ZIP + price only), and its `explanation` string
  says so rather than pretending the results are semantically ranked. The
  test suite sets `EMBEDDINGS_ENABLED=false` so the ~90MB download and ~1s
  load don't happen for the ~76 tests that have nothing to do with
  matching; `tests/test_matching.py::TestRealEmbeddings` opts back in and
  exercises the real model end-to-end.
- **Dependency cost, accepted.** `sentence-transformers` pulls in `torch` +
  `transformers`. `requirements.txt` uses PyTorch's CPU wheel index so the
  install is the ~200MB CPU build, not the ~2.5GB CUDA one (see the comment
  at the top of that file); the Dockerfile bakes the model into the image
  so the first search after a deploy doesn't block on a download. A lighter
  ONNX-based embedder (`fastembed`) was considered; `sentence-transformers`
  was chosen as the more standard, recognizable API (see §10).

**Known limitations:**

- **No relevance evaluation.** We can show that "bicycle" now matches a
  "cyclists" listing (there's a test), but there's no labelled "good match"
  dataset, so there's no precision@k number here — same honesty caveat as
  the pricing model's synthetic-data MAE.
- Rerank weights are hand-set, not tuned.
- Brute-force scan; no ANN index (fine at current scale).
- The query is embedded on every request (~10–50ms on CPU); not cached.
- Matching still doesn't understand geography — ZIP is string matching, not
  distance (§11).

### Hosting

**Not yet implemented.** Planned for Phase 2: MongoDB Atlas, API on
Render/Fly.io, web on Vercel. Documented in full once deployed (§9).

## 4. Data model

All collections use a UUID4 string as `_id` (not Mongo's default ObjectId),
generated application-side. This keeps IDs opaque and consistent across
services without leaking Mongo internals into API responses.

### `users`

| Field | Type | Notes |
|---|---|---|
| `_id` | string (UUID4) | |
| `name` | string | |
| `email` | string | Unique — see index below |
| `hashed_password` | string | `pbkdf2_sha256` via passlib |
| `zipCode` | string | |
| `isHost` | bool | |
| `phone` | string \| null | |
| `createdAt` | datetime | |
| `backgroundCheckAccepted` | bool | Self-attested at registration; see §7 for why this must never by itself set `verificationStatus` to a verified state |
| `verificationStatus` | string | `pending` \| `processing` \| `verified` \| `requires_input` \| `cancelled` |
| `stripeVerificationSessionId` | string \| null | Set once a Stripe Identity session is created |

**Indexes:** unique index on `email`. The v1 prototype checked-then-inserted
without a unique constraint, which is a race condition (two concurrent
registrations with the same email could both pass the existence check). A
unique index makes the database reject the second insert instead of silently
creating a duplicate account.

### `listings`

| Field | Type | Notes |
|---|---|---|
| `_id` | string (UUID4) | |
| `hostId` | string | FK to `users._id` |
| `title`, `description` | string | |
| `size` | enum `S`\|`M`\|`L` | Derived bucket from `sizeSqft`, kept for backward-compatible filtering |
| `sizeSqft` | float | Total square footage of the space |
| `pricePerMonth` | float | Host-set monthly rate for the *whole* space, $25–70 realistic range |
| `addressSummary`, `zipCode` | string | |
| `images` | string[] | |
| `availability` | bool | |
| `availableFrom`, `availableTo` | datetime \| null | |
| `bookingDeadline` | datetime \| null | |
| `rating` | float \| null | **Fabricated in v1** (hardcoded 4.7 on every listing); Phase 4 replaces this with a real review system. Until then, new listings do not get a fake default (see §11). |
| `embedding` | float[384] \| null | Sentence embedding of `title` + `description` (`all-MiniLM-L6-v2`), used by `/matching/recommend` for semantic search (§3). Written on listing create/update; `null` if embeddings were disabled or the model was unavailable at write time, in which case `/matching/recommend` backfills it lazily on the next search. Never returned in API responses. |
| `createdAt` | datetime | |

### `reservations`

| Field | Type | Notes |
|---|---|---|
| `_id` | string (UUID4) | |
| `listingId`, `renterId` | string | |
| `startDate`, `endDate` | datetime | |
| `sqftRequested` | float | |
| `numBoxes` | int | Secure box add-on count, $10/box/month, prorated like the base price |
| `insuranceDeclaredValue` | float \| null | Drives the insurance tier (§5); `null` if no Spacio insurance was purchased |
| `hasOwnInsurance` | bool | If true, renter supplied proof of their own insurance instead of buying Spacio's |
| `status` | enum | `pending_host_confirmation` \| `confirmed` \| `declined` \| `expired` |
| `basePrice`, `serviceFee`, `boxCost`, `insuranceCost`, `totalPrice` | float | See §5 for the formula |
| `holdExpiresAt` | datetime | 24h from creation; nothing expires it yet — see §11 |
| `createdAt` | datetime | |
| `paymentStatus` | enum | `pending_payment` \| `authorized` \| `captured` \| `canceled` \| `payment_expired` — see §3's Checkout section |
| `stripeCheckoutSessionId` | string \| null | Set once the renter starts Checkout; never returned in API responses |
| `stripePaymentIntentId` | string \| null | Set by the `checkout.session.completed` webhook (or the status-poll fallback); what `capture`/`cancel` act on |

**Indexes:** compound index on `(listingId, status, startDate, endDate)` —
every capacity check and search-by-date query filters on exactly these
fields together.

### `messages`

| Field | Type | Notes |
|---|---|---|
| `_id` | string (UUID4) | |
| `reservationId` | string | Scopes the conversation to one reservation |
| `senderId` | string | |
| `content` | string | |
| `createdAt` | datetime | |

**Indexes:** index on `reservationId` (every read filters by it).

## 5. Business rules as implemented

This section must stay in exact sync with the business brief. If the code and
this section disagree, the code is wrong — file an issue against yourself.

### Pricing formula

```
base = hostMonthlyPrice × (sqftRequested / totalSqft) × (days / 30)
serviceFee = base × SERVICE_FEE_RATE
```

`SERVICE_FEE_RATE = 0.20` (20%). This was ambiguous across the v1 prototype's
own files — the business plan text said 10–15%, the financial model assumed
20%, `config.py` had `0.20`, and `env.example` had `0.10`. Resolved 2026-08-10
(see §10): **20%**, matching the financial model's reference unit economics
($40 host price → $8 to Spacio → $32 to host).

### Secure boxes (add-on)

`$10 per box per month`, prorated the same way as the base price:

```
boxCost = numBoxes × 10 × (days / 30)
```

Proration wasn't specified explicitly in the brief; it was chosen for
internal consistency with how every other price component in this formula is
time-prorated, rather than charging a flat $10 regardless of stay length.

### Insurance (declared-value tiers)

Priced by declared item value, not square footage — the v1 prototype charged
`sqftRequested × 0.15`, which was not the business model and has been
deleted.

| Declared value | Monthly cost |
|---|---|
| Up to $1,000 | $12 |
| $1,000–$3,000 | $20 |
| $3,000–$5,000 | $30 |
| $5,000–$10,000 | $45 |

Tier boundaries are treated as `(previous max, this max]` — a declared value
of exactly $1,000 falls in the first tier. Prorated by `days / 30` for the
same internal-consistency reason as box cost. Renters may instead set
`hasOwnInsurance = true` and supply proof of their own renter's insurance,
which waives the Spacio insurance charge entirely (no `insuranceDeclaredValue`
is charged in that case). Declared values above $10,000 are rejected — there
is no tier for them yet.

### Reservation total

```
total = base + serviceFee + boxCost + insuranceCost
```

### Capacity rule

A single listing can host multiple concurrent renters as long as the sum of
`sqftRequested` across all overlapping `confirmed` + `pending_host_confirmation`
reservations never exceeds the listing's `totalSqft`. "Overlapping" means the
date ranges intersect: `existingStart < newEnd AND newStart < existingEnd`.
This was already correct in the v1 prototype and is preserved, now as a pure,
independently unit-tested function (`app/services/capacity.py`) rather than
logic embedded in a route handler.

### Reservation state machine

```mermaid
stateDiagram-v2
    [*] --> pending_host_confirmation
    pending_host_confirmation --> confirmed: host approves
    pending_host_confirmation --> declined: host declines
    pending_host_confirmation --> expired: 24h hold elapses, no action
    confirmed --> [*]
    declined --> [*]
    expired --> [*]
```

`confirmed`, `declined`, and `expired` are terminal — a reservation cannot be
approved after it's been declined, for example. The v1 prototype did not
enforce this (you could call `/approve` on an already-declined reservation);
`app/services/reservation_state.py` now validates every transition.

The 24-hour auto-expiry is not yet wired to a scheduled job (see §11) — the
pure `is_hold_expired()` check exists and is tested, but nothing calls it on
a timer until Phase 4.

## 6. The pricing model

**Built in Phase 2 (2026-08-27).** `POST /pricing/suggest` is now served by
`app/services/ai_pricing.py`, backed by a real trained model rather than the
Phase 0/1 deterministic heuristic (`BASE_PRICES_BY_SIZE` etc., retired — see
git history if you need it).

**Training data provenance — synthetic, stated plainly.** Spacio has no real
booking or listing-price history yet, so there is nothing real to train on.
`app/ml/synthetic_pricing_data.py` generates 8,000 synthetic comp rows from
an explicit, documented generative formula (per-tier $/sqft rate, sublinear
sqft scaling, an indoor multiplier, log-normal noise, and a 5% chance of a
±25% outlier), seeded (`seed=42`) for full reproducibility. This formula is
deliberately *not* the same as the old heuristic it replaces — if it were,
the model would just be re-deriving a formula it was implicitly handed,
which would make the baseline comparison below circular. Every user-facing
`explanation` string returned by `/pricing/suggest` says "trained on
synthetic data, not real booking history" — this must never be softened to
imply the model is trained on real comps.

**Feature list and rationale** (`app/ml/features.py`, the single source of
truth for encoding — shared by training and inference so they can't drift
apart):

| Feature | Type | Rationale |
|---|---|---|
| `size` | categorical (S/M/L) | The bucket the host picks in `CreateListingForm`; kept even though `sizeSqft` is more granular because it's still part of the request contract and the frontend derives it from sqft either way. |
| `sizeSqft` | numeric | The real driver of cost. Previously collected in the create-listing form but never sent to `/pricing/suggest` — now included in `PriceSuggestionRequest`. |
| `zip_demand_tier` | categorical (low/mid/high) | Derived from the ZIP3 prefix via a hand-labeled table in `features.py`, expanding the old heuristic's binary `HIGH_DEMAND_ZIP_PREFIXES` flag into 3 tiers. Still not real demand data (no bookings to derive it from) — same honesty caveat as before, just less crude. |
| `indoor` | boolean | Collected in the create-listing form (`indoor` state in `CreateListingForm.tsx`), not persisted on the listing itself — a transient pricing-suggestion input only. |

`title`/`description` are accepted by `PriceSuggestionRequest` but not used
as model features. Free text is turned into a numeric signal by the Phase 2
matching model (§3, sentence embeddings) — but that's for ranking listings
against a query, not pricing. Feeding raw text embeddings into this
regressor without a reason to think description wording predicts price
would just add noise; revisit if real data shows otherwise.

**Model type and why:** three independent LightGBM quantile regressors
(`objective="quantile"`, `alpha` = 0.15 / 0.5 / 0.85), trained via
`app/ml/train_pricing_model.py`. Quantile regression was chosen over a
single point-estimate model because the product needs a `min`/`suggested`/
`max` spread, not just one number — the old heuristic faked that spread with
a fixed ±15% multiplier; the real model produces genuine p15/p50/p85
estimates instead. Gradient-boosted trees (vs. e.g. linear regression) were
chosen because the generative formula has a real nonlinearity (sublinear
sqft scaling) and a tier × indoor interaction that a linear model can't
capture, and because LightGBM handles the categorical features (`size`,
`zip_demand_tier`) natively without one-hot encoding. Hyperparameters
(`n_estimators=300`, `num_leaves=15`, `max_depth=5`, `learning_rate=0.05`)
are a reasonable default for a dataset this size, not results of formal
tuning — worth revisiting once real data replaces the synthetic set.

**Evaluation against a naive baseline, real numbers** (from the training run
that produced the committed artifact; reproduce with `python -m
app.ml.train_pricing_model` from `api/`):

| | MAE (held-out 1,600 rows) |
|---|---|
| Naive per-ZIP-tier $/sqft baseline | $10.28 |
| Trained model (median/p50) | $2.36 |
| Improvement | 77.1% |

The naive baseline (`_naive_baseline_mae` in `train_pricing_model.py`)
predicts `price = (mean training $/sqft for that ZIP tier) × sqft` — it
captures the ZIP/tier signal but none of the sqft-scaling, indoor premium,
or interaction effects, so a large model win here mostly confirms the
synthetic data actually has learnable structure beyond a flat per-sqft rate,
not that the model would perform this well on real bookings.

**Artifact versioning:** the trained bundle (all three quantile models plus
metadata: feature columns, training timestamp, seed, LightGBM version, and
the metrics table above) is serialized with `joblib` to
`app/ml/artifacts/pricing_model_v1.joblib` and **committed to the repo** —
training is fully deterministic given the fixed seed, so committing the
artifact (rather than training at deploy time) keeps `docker compose up` and
a fresh clone working out of the box. `ai_pricing.py` loads a pinned
filename (`pricing_model_v1.joblib`); bump `VERSION` in
`train_pricing_model.py` and the loaded filename in `ai_pricing.py` together
whenever a feature-set or encoding change would make an old artifact
incompatible, so the two files can't silently drift onto different
contracts.

**Known limitations:**
- Trained entirely on synthetic data — real predictive accuracy on actual
  bookings is unknown and likely worse than the $2.36 MAE above, which only
  measures how well the model recovered a formula we wrote ourselves.
  Retrain on real booking history once Spacio has enough of it.
- The `zip_demand_tier` table is still a small hand-labeled list of Texas
  metro ZIP3 prefixes, same limitation as the old heuristic's ZIP list, just
  less coarse.
- No hyperparameter tuning; no cross-validation, just a single train/test
  split.
- Output is no longer clipped to the old fixed $25–70 heuristic band (see
  §11) — a small, low-demand, outdoor unit can now legitimately be
  suggested below $25/mo, which is more honest than an artificially fixed
  floor but is a behavior change worth knowing about.
- `title`/`description` are accepted by the endpoint but unused by the
  model (see feature table above).

## 7. Security

### Auth model

- Passwords hashed with `pbkdf2_sha256` (passlib), never stored or logged in
  plaintext.
- JWTs signed with HS256, `sub` claim = user ID, expiry from
  `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Every protected route depends on `get_current_user`, which decodes the
  token and loads the user from the database — a forged or expired token is
  rejected with 401 before any handler code runs.
- Host-only actions (`create_listing`, `approve`/`decline` reservations)
  additionally check `isHost` and `verificationStatus == "verified"` /
  listing ownership in the handler.

### Known vulnerabilities inherited from v1, and their status

This table will be completed as each is fixed in Phase 1. Tracking it here
now so nothing gets silently forgotten between phases.

| Vulnerability | Status |
|---|---|
| Stripe webhook signature not verified (`stripe.Event.construct_from` on raw body) | Fixed — see below |
| `verificationStatus = "verified-mock"` self-attestation bypass at registration | Fixed — see below |
| `cors_origins` defaults to `["*"]` with `allow_credentials=True` | Fixed — see below |
| `jwt_secret` defaults to a literal string instead of failing fast when unset | Fixed — see below |
| JWT in `localStorage`, no expiry handling, no 401 interceptor | Fixed — see below |
| Upload endpoint trusts client-supplied `Content-Type`, no size limit | Fixed — see below |
| `GET /listings` returns raw Mongo documents instead of a response model | Fixed in Phase 0 — see below |
| No rate limiting on `/auth/login` or `/pricing/suggest` | Fixed — see below |

`GET /listings` now returns a typed response instead of raw documents so
undocumented fields never leak to unauthenticated callers.

The Stripe webhook now verifies the `stripe-signature` header via
`stripe.Webhook.construct_event` against `STRIPE_WEBHOOK_SECRET`, rejecting
forged and unsigned requests with a 400 — see
`api/tests/test_verification_webhook.py`.

`jwt_secret` and `cors_origins` (`app/core/config.py`) no longer have
defaults, so an unset `JWT_SECRET` or `CORS_ORIGINS` now fails startup
instead of silently signing tokens with a well-known key or opening the API
to any origin. `cors_origins` also has a validator that explicitly rejects
`"*"`, since that combined with `allow_credentials=True` (`main.py`) would
let any website read authenticated responses from a logged-in user's
browser.

`POST /listings/upload` (`app/routers/listings.py`) now: caps the read at
5MB (rejecting larger uploads with 413 without buffering the whole file);
decodes the bytes with Pillow and checks the real detected format instead of
trusting the client's `Content-Type` or filename extension; and writes back
the re-decoded pixel data rather than the raw uploaded bytes, which strips
EXIF metadata and any non-image bytes appended after the image data. See
`api/tests/test_listing_upload.py`.

`POST /auth/login` (5/minute) and `POST /pricing/suggest` (20/minute) are now
rate limited per caller IP via `slowapi`, returning 429 once exceeded — a
shared `Limiter` (`app/core/rate_limit.py`) is wired into `main.py` and
applied per-endpoint with `@limiter.limit(...)`. Login gets the stricter
limit since it's the brute-force/credential-stuffing target; pricing/suggest
just needs enough headroom for normal debounced typing in the host listing
form. Storage is in-memory, which is correct for the current single-process
deployment but would need a shared backend (e.g. Redis) before running
multiple API replicas. See `api/tests/test_rate_limiting.py`.

`POST /auth/register` (`app/routers/auth.py`) no longer accepts a client-
supplied `backgroundCheckAccepted` flag or sets `verificationStatus:
"verified-mock"` from it — every new user now always starts at `"pending"`,
regardless of request body. `"verified"` is only ever set by the real Stripe
Identity flow (`app/routers/verification.py`, driven by the signed webhook).
The dead `backgroundCheckAccepted` field was removed from `UserCreate`
(`app/models/schemas.py`), `seed.py`'s fixtures, and the frontend's register
form/payload type, since it never did anything the UI surfaced. See
`api/tests/test_api_authorization.py::test_registration_cannot_self_attest_verification`.

The JWT no longer lives in `localStorage`. `POST /auth/login`
(`app/routers/auth.py`) sets it as an `HttpOnly` cookie (`Secure` gated by
the new `COOKIE_SECURE` setting, `SameSite=Lax`) instead of returning it in
the JSON body — page JS can no longer read the session token at all, closing
the XSS-token-theft path the old `localStorage` model was exposed to.
`app/deps/auth.py`'s `get_current_user` reads the cookie first, falling back
to an `Authorization: Bearer` header for non-browser callers (scripts, this
test suite). A new `POST /auth/logout` clears the cookie (JS can't clear an
`HttpOnly` cookie itself). On the frontend, `api/client.ts` sets
`withCredentials: true` and drops the old manual header-attaching
interceptor, and adds a response interceptor that redirects to `/login` on
any 401 other than the initial `/auth/me` session check — the "no expiry
handling" half of this issue. Verified against a real browser (login →
`localStorage`/`document.cookie` both confirmed empty, cookie survives a
hard reload, logout invalidates the session immediately, and a live 401 on
an authenticated call triggers the redirect) in addition to the backend
test suite (`api/tests/test_api_authorization.py`,
`test_register_then_login_sets_httponly_cookie_and_authenticates` and
`test_bearer_header_still_works_as_a_fallback`).

### Rate limits

`POST /auth/login`: 5/minute per IP. `POST /pricing/suggest`: 20/minute per
IP. Both via `slowapi`, in-memory storage — see §7's vulnerability table
above for detail. No other endpoints are rate limited yet.

### Secrets

`.env` is gitignored; `env.example` documents every variable without real
values. Stripe keys are supplied by whoever runs the stack locally or in CI
secrets — never committed.

## 8. Local development

See the [README](../README.md#local-development) — kept there so there's one
canonical quickstart, not two documents that can drift apart.

## 9. Deployment

Not yet implemented. Planned for Phase 2 (MongoDB Atlas, API on Render/Fly.io,
web on Vercel). Will be documented here with environments, env vars, CI/CD,
and rollback steps once real.

## 10. Decision log

Append-only. Never delete an entry; if a decision is reversed, add a new one
that supersedes it and say why.

- **2026-08-10** — Chose a from-scratch rewrite over continuing
  `saachiraju/Team-07-Spacio` because the old repo doesn't run (Tier 1
  defects), has unverified webhook signatures and a trust-gate bypass (Tier 2),
  and the "AI" features are fabricated (Tier 3). A clean repo with real tests
  and CI from commit 1 was judged cheaper than untangling those in place.
- **2026-08-10** — Resolved the service fee ambiguity (business plan said
  10–15%, financial model assumed 20%, `config.py` had 0.20, `env.example`
  had 0.10) as **20%**, matching the financial model's reference unit
  economics. Single source of truth is `Settings.service_fee_rate` in
  `api/app/core/config.py`.
- **2026-08-10** — Chose to keep Stripe Identity wiring behind real test-mode
  keys supplied by the project owner rather than building a dev-mode stub
  that bypasses real API calls, so that the verification flow is exercised
  against the real Stripe API (in test mode) from day one instead of a
  second, divergent code path that would need its own maintenance.
- **2026-08-10** — Box and insurance costs are prorated by `days / 30`,
  matching the base price formula. Not explicit in the business brief;
  chosen for internal consistency rather than flat monthly charges
  regardless of stay length.
- **2026-08-10** — Ported `web/` deliberately rather than bulk-copying v1's
  2297-line `App.tsx`: split into `pages/`/`components/`/`lib/` (one file per
  page, not yet the full one-component-per-file split — that's Phase 4).
  Made three related calls while doing so, none dictated by the brief but
  each following directly from a ground rule already in it: (1) dropped v1's
  post-reservation redirect to a real Stripe checkout link (its own, from the
  old team's account) — `paymentStatus` is `mocked-success` server-side, so
  sending a user to a real payment page there would be dishonest, not just
  unnecessary; (2) dropped the `?? 4.7` fake-rating fallback in the UI to
  match the backend's genuine `null`; (3) relabeled "AI Match"/"AI
  suggestion" to "Smart Match"/"Price suggestion" to match what
  `services/matching.py` and `services/ai_pricing.py` actually are —
  heuristics, not AI — per the "never misrepresent in user-facing strings"
  rule.
- **2026-08-12** — Added `docker-compose.yml` plus a `Dockerfile` for each of
  `api/` and `web/`, completing the Docker quickstart the README already
  documented. Both services run in dev mode inside containers (`uvicorn
  --reload`, `vite --host 0.0.0.0`) with the source tree bind-mounted for hot
  reload, matching how they're run natively — this is a dev compose file, not
  a production build. `api/.dockerignore` excludes `.env` and `.venv` so
  secrets and the host virtualenv are never baked into the image layer.
- **2026-08-27** — Phase 2 (real pricing model): chose LightGBM over
  scikit-learn's built-in gradient boosting for the quantile regressors —
  both would have been legitimate, sklearn's `HistGradientBoostingRegressor`
  keeps the dependency footprint lighter, but LightGBM is the more
  industry-standard answer and its native categorical-feature handling fit
  `size`/`zip_demand_tier` cleanly. Also decided to commit the trained model
  artifact (`app/ml/artifacts/pricing_model_v1.joblib`) to the repo rather
  than training it at deploy time, since training is fully deterministic
  given the fixed seed — same reasoning as committing `docker-compose.yml`:
  keep a fresh clone working out of the box. Also locked in **Phase 5:
  deployment infra (EC2 running the API, S3 for listing/verification
  images)**, scheduled after Phase 2/3 feature work rather than before, so
  infra spend doesn't start while the feature set is still moving.
- **2026-08-28** — Phase 2 (semantic matching): replaced the keyword
  dictionary in `services/matching.py` with sentence-embedding search
  (§3). Chose `sentence-transformers` + `all-MiniLM-L6-v2` over the lighter
  ONNX-based `fastembed` (same model family, ~20MB of deps vs ~1GB) and
  over static-embedding `model2vec`: the heavier option was taken for the
  more standard, widely-recognized API, mitigated by pinning the CPU-only
  torch build (`requirements.txt` extra index) and baking the model into
  the Docker image. Kept `matching.py` a pure function of precomputed
  vectors (no torch import) so it stays fast to unit-test. Did **not** add
  an ANN index — brute-force scan is fine at hundreds of listings; revisit
  at scale. Embeddings stored per-listing on write, backfilled lazily on
  read; `EMBEDDINGS_ENABLED=false` disables the model for the test suite
  and degrades `/matching/recommend` to a ZIP+price ranking rather than
  failing.
- **2026-09-02** — Phase 4, PR-B: Stripe Checkout for renter payments,
  replacing `paymentStatus: "mocked-success"`. Chose manual-capture
  (`capture_method="manual"`) over an automatic charge specifically because
  the business flow requires host approval *before* money moves — see §3
  for the full reasoning. Split the money at the Checkout layer via Connect
  destination charges (`transfer_data.destination` = host's account,
  `application_fee_amount` = the reservation's own `serviceFee`) rather than
  charging Spacio's platform account and doing a manual transfer afterward,
  since the split is then computed once (in `reservation_pricing.py`) and
  reused everywhere instead of recomputed at charge time. Put the
  capture/cancel Stripe calls in a new `services/reservation_payments.py`
  rather than importing `routers/payments.py` from `routers/reservations.py`
  — small module, but keeps routers from importing each other. This
  followed **Phase 4, PR-A: Stripe Connect Express onboarding** for host
  payouts (`routers/payments.py`'s `/connect/*` endpoints, gating listing
  creation on `stripeConnectOnboarded`), which shipped first since Checkout
  needs a destination account to pay out to.

Honest, current as of Phase 0:

- **Payments are real (test-mode Stripe), but only for the manual-capture
  authorize/capture/cancel path.** No refund flow exists yet for a renter
  who cancels *after* a host has already approved (`paymentStatus:
  "captured"`) — `DELETE /reservations/{id}` deliberately leaves a captured
  payment untouched rather than mislabeling it, but doesn't issue a Stripe
  refund either. See §3.
- **No scheduled job expires 24-hour holds.** The logic to detect an expired
  hold exists and is tested; nothing calls it on a timer yet (Phase 4). Now
  that Checkout is live, this also means a reservation the host never acts
  on can leave a renter's card authorized past Stripe's own ~7-day
  authorization window — see §3's Checkout tradeoffs.
- **No review system.** Listings no longer get a fabricated `4.7` rating
  (the v1 default), but there's also no way to earn a real one yet — `rating`
  is `null` until Phase 4 ships reviews.
- **Pricing suggestions are a real trained model, but trained entirely on
  synthetic data** — there's still no real booking history. See §6 for the
  full limitations list; must be retrained once real data exists.
- **Search is ZIP-prefix matching, not real geography.** No map, no
  `$near` queries. This applies to the Smart Match reranker too — it boosts
  exact/ZIP3 matches but has no notion of distance.
- **Smart Match has no relevance evaluation.** It's real semantic search as
  of Phase 2 (§3), but there's no labelled match-quality dataset, so its
  rerank weights are hand-set and there's no precision@k number — same
  honesty caveat as the pricing model's synthetic MAE.
- **Theoretical race condition in the capacity check** under concurrent
  bookings for the same listing and overlapping dates, due to MongoDB's lack
  of default multi-document transactions. See §3 (MongoDB tradeoffs).
- **Several Tier 2 security issues from the v1 audit are still open** — see
  §7's table. Phase 1 closes these before anything is deployed publicly.
- **No explicit CSRF token.** Login now uses an `HttpOnly` cookie
  (§3/§7), mitigated with `SameSite=Lax`, which blocks most forged
  cross-site requests but isn't as strong as a dedicated CSRF token on
  state-changing routes. Worth adding before this handles real payments.
- **No JWT denylist/revocation.** A stolen-but-not-yet-expired token, or a
  user who wants to "log out everywhere," can't be invalidated early — the
  token is just valid until its `exp` claim passes. See §3.
- **No pagination anywhere yet.** Listing and reservation queries use a fixed
  `to_list(length=...)` cap. Fine at seed-data scale, not fine at real scale.
  Phase 5.
