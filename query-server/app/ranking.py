# combines BM25 relevance with a PageRank authority score into one final ranking score,
# plus the same exact-phrase bonus Phase 2 used. Swaps out Phase 2's hand-rolled TF-IDF entirely.

# still needed: BM25 has no concept of phrases, so we boost separately
from app.index import phrase_match
# Phase 4: hand-rolled BM25 (ported from index.cpp), replacing the rank_bm25 library
from app.bm25 import score_candidates

# how much relevance (BM25) counts toward the final score
BM25_WEIGHT = 0.85
# how much link authority (PageRank) counts toward the final score -- a boost, not the main signal
PAGERANK_WEIGHT = 0.15
# flat bonus added after weighting; same constant, same role it played in Phase 2
PHRASE_BOOST = 2.0


# min-max scales a {doc_id: float} map into 0..1, so BM25 and PageRank sit on the same scale before summing
def _normalize(raw_scores: dict) -> dict:
    if not raw_scores:  # no candidates to score
        return {}
    values = raw_scores.values()
    lo, hi = min(values), max(values)
    span = hi - lo
    if span == 0:  # every candidate scored identically -- nothing to differentiate between them
        return dict.fromkeys(raw_scores, 1.0)
    return {doc_id: (v - lo) / span for doc_id, v in raw_scores.items()}


# scores every candidate doc in ONE pass and returns {doc_id: final_score}
def score_documents(
    candidate_ids: set,
    structured_query: dict,
    inverted_index: dict,
    doc_lengths: dict,
    avg_doc_length: float,
    total_docs_count: int,
    pagerank_norm: dict,
) -> dict:
    # both required and optional terms feed BM25's relevance judgment; excluded terms never reach this
    # function since retrieve_candidates() already filtered those docs out of candidate_ids
    query_terms = structured_query["required"] + structured_query["optional"]

    # hand-rolled BM25 (app/bm25.py, ported from index.cpp), scored directly against
    # candidate_ids -- unlike rank_bm25.get_scores(), which always scored the entire
    # corpus regardless of query, this never touches a document outside candidate_ids
    candidate_bm25 = score_candidates(
        candidate_ids, query_terms, inverted_index, doc_lengths, avg_doc_length, total_docs_count)

    # normalize BM25 only across THIS query's candidates, not the whole corpus -- we only care about
    # relative relevance among docs that already passed the boolean/phrase filters
    bm25_norm = _normalize(candidate_bm25)

    scores = {}
    for doc_id in candidate_ids:  # combine relevance + authority for every candidate
        combined = (
            BM25_WEIGHT * bm25_norm.get(doc_id, 0.0)
            + PAGERANK_WEIGHT * pagerank_norm.get(doc_id, 0.0)
        )
        # same phrase-boost logic as Phase 2
        for phrase_terms in structured_query["phrases"]:
            if phrase_match(phrase_terms, doc_id, inverted_index):
                combined += PHRASE_BOOST
        scores[doc_id] = combined

    return scores  # {doc_id: final combined score}, ready for main.py to sort

# Why score_documents() takes the whole candidate SET at once, instead of Phase 2's one-doc-at-a-time
# score_document(): score_candidates() computes each query term's idf exactly once (a corpus-wide
# number, independent of which doc is being scored) and reuses it for every candidate. Scoring one
# doc_id at a time would recompute the same idf values over and over for no reason. This mattered even
# more back when relevance came from rank_bm25.get_scores(), which rescored the ENTIRE corpus on every
# call regardless of query -- that constraint is gone now that BM25 is hand-rolled directly against
# candidate_ids, but batching by query (not by document) is still the right shape for this function.
#
# Known carry-over quirk from Phase 2 (not something Phase 3 changes): retrieve_candidates() only uses
# phrases as a scoring BOOST, not a filter -- a query that's ONLY a phrase (no bare required/optional
# words) still returns the whole corpus as candidates, ranked by whether the phrase matched. Worth
# revisiting later, but out of scope for this pass.
