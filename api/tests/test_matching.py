"""Tests for semantic listing matching.

Two layers:

* ``TestRanking`` — pure unit tests of ``app.services.matching``. They feed
  hand-built toy vectors straight in, so they run everywhere, fast, with no
  model and no database.
* ``TestRealEmbeddings`` — exercise the actual ``all-MiniLM-L6-v2`` model
  through ``app.ml.embeddings``. Skipped automatically if
  ``sentence-transformers`` isn't installed; when it is, the first run
  downloads the model (~90 MB, then cached).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.matching import (
    DATE_MISS_PENALTY,
    EXACT_ZIP_BONUS,
    ZIP3_PREFIX_BONUS,
    match_listings,
    score_listing,
)


def _listing(**overrides) -> dict:
    base = {
        "_id": "l-0",
        "title": "A space",
        "description": "Some room",
        "zipCode": "78705",
        "pricePerMonth": 100.0,
        "availability": True,
        "embedding": [0.0, 0.0, 1.0],
    }
    base.update(overrides)
    return base


class TestRanking:
    # Query points along +x; listings are placed at known cosine distances.
    QUERY = [1.0, 0.0, 0.0]

    def test_semantic_score_orders_by_cosine_similarity(self):
        aligned = _listing(_id="aligned", embedding=[1.0, 0.0, 0.0])
        orthogonal = _listing(_id="orthogonal", embedding=[0.0, 1.0, 0.0])
        opposed = _listing(_id="opposed", embedding=[-1.0, 0.0, 0.0])

        top, _ = match_listings([opposed, orthogonal, aligned], self.QUERY)

        assert [lst["_id"] for lst in top] == ["aligned", "orthogonal", "opposed"]

    def test_unavailable_listings_are_dropped(self):
        live = _listing(_id="live", embedding=[1.0, 0.0, 0.0])
        off = _listing(_id="off", embedding=[1.0, 0.0, 0.0], availability=False)

        top, _ = match_listings([live, off], self.QUERY)

        assert [lst["_id"] for lst in top] == ["live"]

    def test_exact_zip_outranks_zip3_prefix_outranks_neither(self):
        # Identical text relevance; only ZIP differs.
        exact = _listing(_id="exact", embedding=[1.0, 0.0, 0.0], zipCode="78705")
        prefix = _listing(_id="prefix", embedding=[1.0, 0.0, 0.0], zipCode="78701")
        elsewhere = _listing(_id="elsewhere", embedding=[1.0, 0.0, 0.0], zipCode="90210")

        top, _ = match_listings(
            [elsewhere, prefix, exact], self.QUERY, target_zip="78705"
        )

        assert [lst["_id"] for lst in top] == ["exact", "prefix", "elsewhere"]

    def test_zip_bonus_constants_are_ordered(self):
        assert EXACT_ZIP_BONUS > ZIP3_PREFIX_BONUS > 0

    def test_price_is_only_a_nudge_not_a_dominant_signal(self):
        # A strong text match at a high price must still beat a weak text
        # match that happens to be cheap.
        relevant_pricey = _listing(
            _id="relevant", embedding=[1.0, 0.0, 0.0], pricePerMonth=400.0
        )
        irrelevant_cheap = _listing(
            _id="cheap", embedding=[0.0, 1.0, 0.0], pricePerMonth=1.0
        )

        top, _ = match_listings([irrelevant_cheap, relevant_pricey], self.QUERY)

        assert top[0]["_id"] == "relevant"

    def test_cheaper_listing_wins_when_text_relevance_is_equal(self):
        cheap = _listing(_id="cheap", embedding=[1.0, 0.0, 0.0], pricePerMonth=25.0)
        pricey = _listing(_id="pricey", embedding=[1.0, 0.0, 0.0], pricePerMonth=250.0)

        top, _ = match_listings([pricey, cheap], self.QUERY)

        assert [lst["_id"] for lst in top] == ["cheap", "pricey"]

    def test_none_query_vector_falls_back_to_structured_ranking(self):
        far_cheap = _listing(_id="far", zipCode="90210", pricePerMonth=20.0)
        near_pricey = _listing(_id="near", zipCode="78705", pricePerMonth=300.0)

        top, explanation = match_listings(
            [far_cheap, near_pricey], None, target_zip="78705"
        )

        assert top[0]["_id"] == "near"  # exact-ZIP bonus outweighs the price nudge
        assert "unavailable" in explanation.lower()

    def test_date_window_miss_is_penalized(self):
        covers = _listing(
            _id="covers",
            embedding=[1.0, 0.0, 0.0],
            availableFrom="2026-01-01",
            availableTo="2026-12-31",
        )
        too_short = _listing(
            _id="short",
            embedding=[1.0, 0.0, 0.0],
            availableFrom="2026-01-01",
            availableTo="2026-03-01",
        )

        top, _ = match_listings(
            [too_short, covers],
            self.QUERY,
            want_from=date(2026, 6, 1),
            want_to=date(2026, 7, 1),
        )

        assert [lst["_id"] for lst in top] == ["covers", "short"]

    def test_listing_with_no_embedding_scores_zero_semantic_and_does_not_crash(self):
        no_vec = _listing(_id="no_vec")
        no_vec.pop("embedding")

        score = score_listing(no_vec, self.QUERY)

        # only the price nudge remains (ZIP not targeted, no dates)
        assert 0.0 < score < 0.1

    def test_top_n_is_respected_with_stable_tiebreak(self):
        listings = [
            _listing(_id=f"l-{i}", embedding=[1.0, 0.0, 0.0]) for i in range(10)
        ]
        top, _ = match_listings(list(reversed(listings)), self.QUERY, top_n=3)

        # all tied on score -> ascending _id order
        assert [lst["_id"] for lst in top] == ["l-0", "l-1", "l-2"]

    def test_explanation_names_the_target_zip(self):
        _, explanation = match_listings(
            [_listing(embedding=[1.0, 0.0, 0.0])], self.QUERY, target_zip="78705"
        )
        assert "78705" in explanation

    def test_empty_input_yields_no_match_explanation(self):
        top, explanation = match_listings([], self.QUERY)
        assert top == []
        assert "no available spaces" in explanation.lower()

    def test_date_miss_penalty_can_be_overcome_by_strong_relevance(self):
        # sanity check that the penalty is a nudge over a big semantic gap,
        # not an absolute filter
        assert DATE_MISS_PENALTY < 0


@pytest.fixture
def real_embeddings(monkeypatch):
    pytest.importorskip("sentence_transformers")
    from app.core.config import settings
    from app.ml import embeddings

    monkeypatch.setattr(settings, "embeddings_enabled", True)
    embeddings._model.cache_clear()
    yield embeddings
    embeddings._model.cache_clear()


class TestRealEmbeddings:
    def test_output_is_unit_normalized_and_correct_dim(self, real_embeddings):
        import numpy as np

        vectors = real_embeddings.embed(["a climate controlled storage room"])

        assert vectors.shape == (1, real_embeddings.EMBEDDING_DIM)
        assert np.isclose(np.linalg.norm(vectors[0]), 1.0, atol=1e-4)

    def test_synonym_query_beats_keyword_absence(self, real_embeddings):
        """The whole point of the upgrade: a listing that never says the
        query's words still wins when it means the same thing."""
        from app.services.matching import match_listings

        bike_spot = {
            "_id": "bike",
            "title": "Covered spot near campus",
            "description": "Ideal for cyclists keeping their equipment safe over the semester.",
            "zipCode": "78705",
            "pricePerMonth": 90.0,
            "availability": True,
        }
        wine_cellar = {
            "_id": "wine",
            "title": "Temperature-controlled cellar",
            "description": "Perfect for collectors storing fine wine and spirits.",
            "zipCode": "78705",
            "pricePerMonth": 90.0,
            "availability": True,
        }
        texts = [real_embeddings.listing_text(bike_spot), real_embeddings.listing_text(wine_cellar)]
        vectors = real_embeddings.embed(texts)
        bike_spot["embedding"] = vectors[0].tolist()
        wine_cellar["embedding"] = vectors[1].tolist()

        query_vector = real_embeddings.embed_one("somewhere to keep my road bicycle")

        top, _ = match_listings([wine_cellar, bike_spot], query_vector)

        assert top[0]["_id"] == "bike"

    async def test_recommend_endpoint_ranks_semantically(
        self, real_embeddings, client, verified_host
    ):
        """End-to-end: create listings through the real API (embeddings
        computed on write), then hit /matching/recommend."""
        headers = {"Authorization": f"Bearer {verified_host['token']}"}

        for title, desc in [
            ("Garage bay", "Great for parking a motorcycle or keeping bikes and riding gear."),
            ("Spare closet", "Shelving for documents, paperwork and small archive boxes."),
        ]:
            resp = await client.post(
                "/listings/",
                json={
                    "title": title,
                    "description": desc,
                    "size": "M",
                    "sizeSqft": 100,
                    "pricePerMonth": 120,
                    "addressSummary": "Somewhere, TX",
                    "zipCode": "78705",
                    "availableFrom": "2026-01-01",
                    "availableTo": "2026-12-31",
                },
                headers=headers,
            )
            assert resp.status_code == 201, resp.text

        match = await client.post(
            "/matching/recommend",
            json={"query": "a place to park my motorbike"},
        )
        assert match.status_code == 200, match.text
        body = match.json()
        assert body["listings"], body
        assert body["listings"][0]["title"] == "Garage bay"
        assert "closest in meaning" in body["explanation"]
