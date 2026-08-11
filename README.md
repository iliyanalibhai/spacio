# Spacio

Spacio is a peer-to-peer storage marketplace — "Airbnb for storage." People with
unused space (garages, closets, spare bedrooms, basements) list it. People who
need storage rent part of it, for the dates they need, paying only for the
square footage they actually use.

The full product thesis, business rules, and engineering decisions live in
[`docs/DOCUMENTATION.md`](docs/DOCUMENTATION.md) — read that first if you want
to understand *why* something works the way it does, not just how to run it.

## Credit

This project is a from-scratch rewrite of a prototype originally built for a
university entrepreneurship class by **Saachi Raju**, **Akanksha Divya**, and
**Ali Bhai** (Team 07). The original prototype (domain model, pro-rated
pricing math, and partial-space concurrent booking logic) is referenced —
never copied wholesale — from
[`saachiraju/Team-07-Spacio`](https://github.com/saachiraju/Team-07-Spacio).
This repository is an independent rewrite, not a fork, and is not affiliated
with that repository going forward.

## Monorepo structure

```
spacio/
  api/          FastAPI backend (Python, MongoDB via Motor)
  web/          React + Vite + TypeScript frontend
  ml/           Pricing model: training, evaluation, artifacts (see ml/README.md)
  docs/         DOCUMENTATION.md and deep-dives
  .github/      CI workflows
  docker-compose.yml
```

## Status

This project is under active, phased development. See
[`docs/DOCUMENTATION.md` §11](docs/DOCUMENTATION.md#11-known-limitations--next-steps)
for exactly what's finished versus stubbed. Nothing in this README claims more
than what's actually implemented — if a feature isn't listed below, assume
it's not built yet.

Currently implemented (Phase 0): user auth, listings, pro-rated bookings with
concurrent-capacity enforcement, reservation-scoped messaging, Stripe Identity
host verification, and a seed script with working demo accounts.

## Local development

### Prerequisites

- Docker and Docker Compose (recommended — brings up Mongo, API, and web with
  one command), **or** Python 3.11+, Node.js 20+, and a local MongoDB instance
  if you'd rather run services natively.

### Quickstart (Docker)

```bash
git clone <this-repo-url> spacio
cd spacio
cp api/env.example api/.env   # fill in Stripe test keys if you have them; safe to leave blank otherwise
docker compose up --build
```

- API: http://localhost:8000 (docs at http://localhost:8000/docs)
- Web: http://localhost:5173

Seed demo data (in a second terminal, once the stack is up):

```bash
docker compose exec api python seed.py
```

### Demo accounts

After seeding:

- Host: `host@spacio.dev` / `password123`
- Renter: `renter@spacio.dev` / `password123`

### Running without Docker

```bash
# API
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp env.example .env   # edit as needed; a local MongoDB must be running
uvicorn main:app --reload

# Web (separate terminal)
cd web
npm install
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

### Running tests

```bash
cd api && pytest
cd web && npm test
```

## License

MIT — see [`LICENSE`](LICENSE).
