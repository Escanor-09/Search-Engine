# Phase 5: semantic re-ranking on top of BM25 retrieval.
#
# Precomputes one embedding per document at startup (same "expensive work happens
# once" pattern as the positional index, PageRank, and BM25 stats), using a small,
# CPU-friendly sentence-embedding model. At query time, only the query itself needs
# embedding (cheap, one vector); re-ranking then does a cosine-similarity comparison
# against the ALREADY-COMPUTED embeddings of just the top-K BM25 candidates -- never
# the whole corpus -- which is what keeps this affordable per-request.
import pickle
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"  # 384-dim, ~80MB, fast enough for CPU inference
# only the top TOP_K BM25-ranked candidates get semantically re-ranked -- the
# rest of the result list is left exactly as BM25+PageRank ordered it
TOP_K = 30
# how much the semantic signal counts vs. the existing BM25+PageRank score,
# within the re-ranked head of the list (0.5 = equal weight to both)
SEMANTIC_WEIGHT = 0.5


def load_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def _doc_text(doc: dict) -> str:
    return f"{doc['title']}. {doc['content']}"


# embeds every document once; returns (embeddings matrix, doc_id order list) --
# same doc_id_order pattern build_bm25_index() used to use, since the embedding
# model has no concept of "doc_id" either, only array position
def build_doc_embeddings(docs: dict, model: SentenceTransformer):
    doc_id_order = list(docs.keys())
    texts = [_doc_text(docs[doc_id]) for doc_id in doc_id_order]
    embeddings = model.encode(
        texts,
        batch_size=64,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=True,  # pre-normalized so cosine similarity = dot product later
    )
    return embeddings, doc_id_order


# same save/load-with-staleness-check shape as app/persistence.py's index cache --
# embedding 1000 docs costs ~8s plus ~10s of model load time, worth not repeating
# on every restart
def save_embeddings(cache_path: str, corpus_path: str, embeddings: np.ndarray, doc_id_order: list) -> None:
    payload = {
        "corpus_mtime": Path(corpus_path).stat().st_mtime,
        "embeddings": embeddings,
        "doc_id_order": doc_id_order,
    }
    Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "wb") as f:
        pickle.dump(payload, f)


def load_embeddings(cache_path: str, corpus_path: str):
    cache_file = Path(cache_path)
    if not cache_file.exists():
        return None
    with open(cache_file, "rb") as f:
        payload = pickle.load(f)
    if payload.get("corpus_mtime") != Path(corpus_path).stat().st_mtime:
        return None  # corpus changed since these embeddings were built -- stale
    return payload["embeddings"], payload["doc_id_order"]


# default number of ADDITIONAL documents pulled in purely by semantic similarity,
# beyond whatever BM25 already retrieved -- see AUGMENT_K note below
AUGMENT_K = 15


# Re-orders the top `top_k` of an already-ranked doc_id list by blending cosine
# similarity (query embedding vs. each doc's precomputed embedding) with the
# existing BM25+PageRank score -- AND, if `allow_augmentation` is True, injects
# up to `augment_k` documents that BM25 missed entirely, found purely by
# embedding similarity against the WHOLE corpus.
#
# That second part matters more than it might look: a "rerank the top-K BM25
# results" design (which is what this started as) can only ever reorder
# documents BM25 already found. For a genuine paraphrase query that shares no
# literal words with the target documents at all, BM25 retrieves nothing, so
# there is nothing to reorder -- the rerank step would be a no-op. Comparing
# the query embedding against every document's embedding (cheap: one matrix
# multiply against precomputed vectors, not a re-embedding of every document)
# lets a handful of genuinely relevant-by-meaning documents surface even when
# BM25 found zero (or, just as importantly, many but poorly-targeted) candidates.
#
# `allow_augmentation` should be False whenever the query has an explicit hard
# constraint -- required terms, excluded terms/phrases, or included phrases --
# since augmentation searches by meaning alone and has no way to check any of
# those constraints; it could inject a doc that fails an explicit AND, or one
# that actually contains an explicit NOT-excluded term. It's the caller's job
# (main.py) to decide this from the structured query, not candidate count --
# a query can have a huge candidate count from a single common word (a false
# signal of "BM25 already handled this well") while still being poorly served.
# Docs beyond top_k that were never reranked or augmented are left untouched,
# appended after in their original BM25 order.
#
# Returns (new_ranked_ids, updated_scores) -- updated_scores is base_scores
# plus an entry for every augmented doc_id (which had no BM25 score at all).
def semantic_rerank(
    query: str,
    ranked_ids: list,
    base_scores: dict,
    model: SentenceTransformer,
    doc_embeddings: np.ndarray,
    doc_id_to_index: dict,
    embedding_doc_id_order: list,
    top_k: int = TOP_K,
    weight: float = SEMANTIC_WEIGHT,
    augment_k: int = AUGMENT_K,
    allow_augmentation: bool = True,
) -> tuple:
    query_embedding = model.encode(
        [query], convert_to_numpy=True, normalize_embeddings=True)[0]

    head = ranked_ids[:top_k]
    tail = ranked_ids[top_k:]
    already_present = set(ranked_ids)

    augmented = []
    if allow_augmentation and augment_k > 0:
        # cosine similarity of the query against every document, so documents
        # BM25 never retrieved still have a chance to surface via meaning alone
        all_similarities = doc_embeddings @ query_embedding
        order = np.argsort(all_similarities)[::-1]
        for idx in order:
            doc_id = embedding_doc_id_order[idx]
            if doc_id not in already_present:
                augmented.append((doc_id, float(all_similarities[idx])))
                if len(augmented) >= augment_k:
                    break

    head_indices = [doc_id_to_index[doc_id] for doc_id in head]
    head_similarities = doc_embeddings[head_indices] @ query_embedding if head else np.array([])

    # everything being re-ranked together: BM25's head (has both a base score
    # and a semantic score) plus the augmented, semantic-only finds (no base
    # score at all -- BM25 never evaluated them, see blended_score() below)
    pool_semantic = dict(augmented)
    pool_semantic.update(
        {doc_id: float(sim) for doc_id, sim in zip(head, head_similarities)})
    pool_ids = list(pool_semantic.keys())

    sem_values = list(pool_semantic.values())
    sem_lo, sem_hi = min(sem_values), max(sem_values)
    sem_span = sem_hi - sem_lo
    # base_lo/base_hi are computed ONLY from head docs (the ones BM25 actually
    # scored) -- mixing in a fabricated 0.0 for augmented docs here would drag
    # base_lo down artificially and corrupt the normalization range for head docs
    base_values = [base_scores[doc_id] for doc_id in head] if head else [0.0]
    base_lo, base_hi = min(base_values), max(base_values)
    base_span = base_hi - base_lo

    def blended_score(doc_id: int) -> float:
        sem_norm = (pool_semantic[doc_id] - sem_lo) / \
            sem_span if sem_span > 0 else 1.0
        # a doc BM25 never scored at all (an augmented, semantic-only find) has
        # no lexical opinion to blend in -- treating its "missing" base score as
        # 0.0 and normalizing it alongside real BM25 scores would make it look
        # WORSE than the worst real BM25 candidate, which isn't true; BM25
        # simply never looked at it. Judge it purely on semantic similarity.
        if doc_id not in base_scores:
            return sem_norm
        base_norm = (base_scores[doc_id] - base_lo) / \
            base_span if base_span > 0 else 1.0
        return weight * sem_norm + (1 - weight) * base_norm

    reranked_pool = sorted(pool_ids, key=lambda d: (-blended_score(d), d))

    # every doc in the reranked pool gets its score REPLACED with the blended
    # value actually used to rank it -- not left as a raw, un-normalized BM25
    # score for head docs and a meaningless placeholder for augmented docs.
    # Otherwise the "score" a client sees wouldn't match the order they're in,
    # and augmented docs (often the most relevant ones for a paraphrase query --
    # see the docstring above) would misleadingly show up as 0.0.
    updated_scores = dict(base_scores)
    for doc_id in pool_ids:
        updated_scores[doc_id] = blended_score(doc_id)

    return reranked_pool + tail, updated_scores
