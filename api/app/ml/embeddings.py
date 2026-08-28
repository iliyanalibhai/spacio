"""Sentence-embedding wrapper for semantic listing matching.

Loads `sentence-transformers/all-MiniLM-L6-v2` (a 6-layer distilled BERT,
384-dimensional output) once per process and turns listing / query text into
unit vectors. Because the vectors are L2-normalized, cosine similarity
between any two of them is just their dot product, so
`app/services/matching.py` can rank with a plain dot product and never has
to import this module (or torch).

Why this lives apart from matching.py:
  - matching.py stays a pure, fast, torch-free function of precomputed
    vectors — trivially unit-testable with hand-built arrays.
  - the model (~90 MB one-time download, ~1 s load) is imported and loaded
    lazily on first use, so importing the app — or running the pricing /
    booking-flow tests — never pays for it.

When `settings.embeddings_enabled` is False the model is never touched and
every `embed*` call raises `EmbeddingsDisabled`; callers are expected to
catch that and fall back to a non-semantic ranking. The test suite sets
`EMBEDDINGS_ENABLED=false` for exactly this reason.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING, Optional

import numpy as np

from app.core.config import settings

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Small, fast, widely-benchmarked general-purpose sentence encoder. 384-dim
# output, ~22 M params, runs comfortably on CPU. If this is ever bumped,
# every stored listing embedding must be recomputed (old vectors from a
# different model are not comparable) — bump a version marker and backfill.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


class EmbeddingsDisabled(RuntimeError):
    """Raised by embed*/ when settings.embeddings_enabled is False."""


@lru_cache(maxsize=1)
def _model() -> "SentenceTransformer":
    # Imported here, not at module scope: sentence-transformers drags in
    # torch + transformers (hundreds of MB, ~1 s import), and most of the
    # app never needs it.
    from sentence_transformers import SentenceTransformer

    logger.info("loading sentence-transformers model %s", MODEL_NAME)
    return SentenceTransformer(MODEL_NAME)


def listing_text(listing: dict) -> str:
    """Canonical text representation of a listing for embedding.

    Single source of truth: listing creation, updates, seeding, and search
    must all embed this exact string, or a stored listing vector won't be
    comparable to a freshly embedded query vector.
    """
    title = (listing.get("title") or "").strip()
    description = (listing.get("description") or "").strip()
    return f"{title}. {description}".strip(" .")


def embed(texts: list[str]) -> np.ndarray:
    """Embed a batch of texts into L2-normalized row vectors.

    Returns an array of shape ``(len(texts), EMBEDDING_DIM)``, dtype
    float32. Raises ``EmbeddingsDisabled`` if embeddings are turned off.
    """
    if not settings.embeddings_enabled:
        raise EmbeddingsDisabled(
            "Embeddings are disabled (EMBEDDINGS_ENABLED=false); "
            "semantic matching is unavailable."
        )
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    vectors = _model().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def embed_one(text: str) -> list[float]:
    """Embed a single string into a plain ``list[float]`` (JSON- and
    Mongo-storable). Raises ``EmbeddingsDisabled`` if embeddings are off."""
    return embed([text])[0].tolist()


def safe_embed_one(text: str) -> Optional[list[float]]:
    """Like :func:`embed_one`, but never raises: returns ``None`` if
    embeddings are disabled or the model fails to load / run.

    Used on the listing write path, where a missing embedding is recoverable
    (``/matching/recommend`` backfills it lazily) and must not fail the
    request.
    """
    try:
        return embed_one(text)
    except EmbeddingsDisabled:
        return None
    except Exception:
        # Model download / load can fail many ways (network, disk, a broken
        # torch install); none of them should break a listing write.
        logger.warning("embedding failed; leaving it to lazy backfill", exc_info=True)
        return None
