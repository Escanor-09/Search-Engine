# Hand-rolled BM25, ported from index.cpp's InvertedIndex::searchBM25() (lines
# 121-169 there). This replaces the rank_bm25 library entirely -- exactly the
# "Future Roadmap" item Phase 3 flagged before index.cpp existed, now with a
# concrete reference formula to port instead of reimplementing BM25 from a paper.
#
# One generalization beyond the C++ source: searchBM25() scores a single word
# against the whole index. Our queries can be multi-term (AND/OR), so this sums
# the same per-term formula across every term in the query -- standard BM25,
# index.cpp just never needed the multi-term case since it only demos one word.
import math

# same constants as index.cpp: k1 and b are standard, well-established BM25 defaults
K1 = 1.2
B = 0.75


# idf via the "+1" variant, exactly as index.cpp computes it -- this is the same
# formula Lucene/Elasticsearch's default BM25Similarity uses (idf never negative by
# construction, since (N-df+0.5)/(df+0.5) + 1.0 >= 1.0 for any df in [0, N]).
# Note this is NOT what rank_bm25 (the library this replaces) did internally: it used
# the classic Robertson/Sparck-Jones idf -- log(N-df+0.5) - log(df+0.5), no "+1" --
# which CAN go negative for very common terms, floored via an epsilon*average_idf
# fallback instead. Two different, both legitimate, BM25 variants; this file follows
# index.cpp's (and Lucene's), not rank_bm25's.
def _idf(term: str, inverted_index: dict, total_docs_count: int) -> float:
    df = len(inverted_index.get(term, {}))  # doc frequency: docs containing `term`
    return math.log((total_docs_count - df + 0.5) / (df + 0.5) + 1.0)


# the per-posting formula from searchBM25(), applied to one (term, doc) pair
def _term_score(term_idf: float, tf: int, dl: int, avg_doc_length: float) -> float:
    if tf == 0 or avg_doc_length == 0:
        return 0.0
    tf_component = (tf * (K1 + 1.0)) / \
        (tf + K1 * (1.0 - B + B * (dl / avg_doc_length)))
    return term_idf * tf_component


# scores every candidate doc against every query term, summing per-term contributions.
# Only touches candidate_ids -- unlike rank_bm25.get_scores(), which always recomputed
# every document in the whole corpus regardless of how many were actually asked for.
def score_candidates(
    candidate_ids: set,
    query_terms: list[str],
    inverted_index: dict,
    doc_lengths: dict,
    avg_doc_length: float,
    total_docs_count: int,
) -> dict:
    unique_terms = set(query_terms)
    # idf depends only on the term (corpus-wide document frequency), never the doc --
    # compute it once per unique term rather than once per (term, doc) pair
    term_idfs = {
        term: _idf(term, inverted_index, total_docs_count)
        for term in unique_terms
    }

    scores = {}
    for doc_id in candidate_ids:
        dl = doc_lengths.get(doc_id, 0)
        total = 0.0
        for term in unique_terms:
            postings = inverted_index.get(term, {})
            tf = len(postings.get(doc_id, []))
            total += _term_score(term_idfs[term], tf, dl, avg_doc_length)
        scores[doc_id] = total
    return scores
