import time
from datetime import datetime, timezone
from typing import Union

# HTTPException lets us return clean 4xx errors instead of default 500s
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
# rate limiting: per-client-IP, in-memory storage -- no Redis needed at this scale
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

# index primitives
from app.index import load_corpus, build_index, retrieve_candidates
# combined BM25 + PageRank scoring, whole-candidate-set-at-once
from app.ranking import score_documents
# turns a raw query string into required/optional/excluded/phrases
from app.query_parser import parse_query
from app.validation import validate_query  # raw-input sanity checks
# corpus-dictionary-based spelling suggestions
from app.spellcheck import build_symspell, correct_query
# link-graph + PageRank authority scoring
from app.authority import build_link_graph, compute_pagerank, normalize_pagerank
# highlighted excerpt generation for each result
from app.snippets import build_snippet
# collapses duplicate postings, keeping the best-scored copy
from app.dedup import dedup_results
# Phase 4: typed response models, repeated-query cache, structured logging, autocomplete
from app.schemas import SearchResponse, NoResultsResponse, SuggestResponse, HealthResponse, ErrorResponse
from app.cache import SearchResultCache
from app.logging_config import get_logger, log_request
from app.suggest import build_suggest_index, get_suggestions
# index-cache persistence, ported from index.cpp's saveToDisk()/loadFromDisk()
from app.persistence import save_index, load_index
# Phase 5: semantic re-ranking (sentence-transformers embeddings + cosine similarity)
from app.semantic import (
    load_model as load_semantic_model,
    build_doc_embeddings,
    save_embeddings,
    load_embeddings,
    semantic_rerank,
)

logger = get_logger()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI()  # the API application instance
app.state.limiter = limiter
# a client over the limit gets slowapi's default 429 JSON body, not a raw exception
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# last line of defense: an unexpected bug should never leak a raw traceback to the client
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_exception", extra={
                 "extra_fields": {"path": str(request.url), "error": str(exc)}})
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


# load the corpus once at startup, not per request
CORPUS_PATH = "data/corpus.json"
INDEX_CACHE_PATH = "data/index_cache.pkl"
docs = load_corpus(CORPUS_PATH)

# try the on-disk index cache first (ported from index.cpp's loadFromDisk()); only
# rebuild from scratch if there's no cache yet, or corpus.json changed since it was built
cached_index = load_index(INDEX_CACHE_PATH, CORPUS_PATH)
if cached_index is not None:
    inverted_index, doc_lengths, avg_doc_length, total_docs_count = cached_index
    logger.info("startup", extra={
                "extra_fields": {"index_source": "cache", "path": INDEX_CACHE_PATH}})
else:
    # single-pass build: positional index + doc lengths + avg doc length + doc count
    inverted_index, doc_lengths, avg_doc_length, total_docs_count = build_index(docs)
    save_index(INDEX_CACHE_PATH, CORPUS_PATH, inverted_index,
               doc_lengths, avg_doc_length, total_docs_count)
    logger.info("startup", extra={
                "extra_fields": {"index_source": "rebuilt", "path": INDEX_CACHE_PATH}})

# build the corpus-derived spelling dictionary once at startup
sym_spell = build_symspell(docs)

# link graph + PageRank, all computed once at startup since the corpus/links don't change per-request
link_graph = build_link_graph(docs)
pagerank_raw = compute_pagerank(link_graph)
pagerank_norm = normalize_pagerank(pagerank_raw)

# autocomplete vocabulary (unstemmed terms + corpus frequency), built once at startup
suggest_terms, suggest_frequencies = build_suggest_index(docs)

# Phase 5: semantic re-ranking model + per-document embeddings, built/loaded once
EMBEDDINGS_CACHE_PATH = "data/embeddings_cache.pkl"
semantic_model = load_semantic_model()
cached_embeddings = load_embeddings(EMBEDDINGS_CACHE_PATH, CORPUS_PATH)
if cached_embeddings is not None:
    doc_embeddings, embedding_doc_id_order = cached_embeddings
    logger.info("startup", extra={
                "extra_fields": {"embeddings_source": "cache", "path": EMBEDDINGS_CACHE_PATH}})
else:
    doc_embeddings, embedding_doc_id_order = build_doc_embeddings(docs, semantic_model)
    save_embeddings(EMBEDDINGS_CACHE_PATH, CORPUS_PATH, doc_embeddings, embedding_doc_id_order)
    logger.info("startup", extra={
                "extra_fields": {"embeddings_source": "rebuilt", "path": EMBEDDINGS_CACHE_PATH}})
# maps doc_id -> row index into doc_embeddings, since the embeddings matrix (like
# the old BM25 model) has no concept of doc_id, only array position
doc_id_to_embedding_index = {doc_id: i for i,
                             doc_id in enumerate(embedding_doc_id_order)}

# repeated-query cache: holds the full ranked+deduped list per normalized query,
# taken *before* pagination -- so page 2 of an already-seen query is still a cache hit
search_cache = SearchResultCache()

# for /health's uptime figure
STARTED_AT = datetime.now(timezone.utc)
_start_perf = time.perf_counter()

# hard ceiling so a client can't request one page containing the entire corpus
MAX_PAGE_SIZE = 50


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        corpus_size=len(docs),
        uptime_seconds=round(time.perf_counter() - _start_perf, 3),
        started_at=STARTED_AT.isoformat(),
    )


@app.get("/suggest", response_model=SuggestResponse)
@limiter.limit("30/minute")
# prefix-based autocomplete; deliberately skips validate_query() since partial,
# in-progress input (e.g. a single letter) is exactly what this endpoint expects
def suggest(request: Request, prefix: str = "", limit: int = 10):
    suggestions = get_suggestions(
        prefix, suggest_terms, suggest_frequencies, limit=limit)
    return SuggestResponse(prefix=prefix, suggestions=suggestions)


@app.get(
    "/search",
    response_model=Union[SearchResponse, NoResultsResponse],
    responses={400: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
# q defaults to "" for our own clean validation error
def search(request: Request, q: str = "", page: int = 1, page_size: int = 10, rerank: bool = False):
    request_start = time.perf_counter()

    # run basic sanity checks on the raw input first, before any real work
    validation_error = validate_query(q)
    if validation_error:  # input failed validation
        raise HTTPException(status_code=400, detail=validation_error)

    if page < 1:  # page numbers start at 1, not 0
        raise HTTPException(
            status_code=400, detail="page must be 1 or greater.")
    if page_size < 1 or page_size > MAX_PAGE_SIZE:  # keep page sizes sane in both directions
        raise HTTPException(
            status_code=400, detail=f"page_size must be between 1 and {MAX_PAGE_SIZE}.")

    # rerank changes result ORDER for the same query text, so it has to be part
    # of the cache key -- otherwise a rerank=true request could be served a
    # rerank=false cache entry (or vice versa) written by an earlier request
    cache_key = f"{q}\x1frerank" if rerank else q

    # cache lookup -- a hit skips spellcheck, parsing, retrieval, scoring,
    # semantic re-ranking, and dedup entirely. Snippets are still generated
    # below, since they're only ever built for the current page, cache hit or not.
    cached = search_cache.get(cache_key)
    if cached is not None:
        deduped, did_you_mean, structured = cached
        response = _build_search_response(
            q, page, page_size, deduped, did_you_mean, structured)
        log_request(logger, query=q, rerank=rerank, latency_ms=round((time.perf_counter() - request_start) * 1000, 2),
                    result_count=len(deduped), cache_hit=True)
        return response

    # spell-check the raw query against the corpus dictionary
    correction = correct_query(q, sym_spell)
    # an unrecognized word is a dead end for lexical (BM25) matching -- but NOT
    # for semantic re-ranking, which works on meaning rather than dictionary
    # membership. So this early rejection only applies to the default (lexical)
    # path; with rerank=True, an unknown word just means BM25 won't find a
    # lexical match for it, which the semantic augmentation step can still work
    # around (see app/semantic.py's semantic_rerank docstring).
    if correction["unknown_words"] and not rerank:
        log_request(logger, query=q, rerank=rerank, latency_ms=round((time.perf_counter() - request_start) * 1000, 2),
                    result_count=0, cache_hit=False)
        return NoResultsResponse(
            query=q,
            message="No results found.",
            unknown_words=correction["unknown_words"],
            results=[],
        )

    # search the corrected form if anything was actually corrected, otherwise use the original untouched
    search_query = correction["corrected_query"] if correction["suggestions"] else q

    # parse the (possibly corrected) query into required/optional/excluded/phrases
    structured = parse_query(search_query)
    if not any([structured["required"], structured["optional"], structured["phrases"]]):
        log_request(logger, query=q, rerank=rerank, latency_ms=round((time.perf_counter() - request_start) * 1000, 2),
                    result_count=0, cache_hit=False)
        return NoResultsResponse(
            query=q, message="Query did not contain any searchable terms.", results=[])

    # boolean + phrase-aware retrieval from the index (unchanged from Phase 2)
    candidate_ids = retrieve_candidates(structured, docs, inverted_index)

    # hand-rolled BM25 (scored directly against candidate_ids) + a PageRank lookup per candidate, combined into one score
    scores = score_documents(candidate_ids, structured, inverted_index,
                             doc_lengths, avg_doc_length, total_docs_count, pagerank_norm)

    # sort by score, tie-breaking on doc_id -- a Python set's iteration order isn't something we want
    # user-visible ranking to depend on, so equal scores always come back in the same deterministic order
    ranked_ids = sorted(
        candidate_ids, key=lambda doc_id: (-scores[doc_id], doc_id))

    # Phase 5: optionally re-rank the top of the list by semantic (embedding)
    # similarity to the query, blended with the existing BM25+PageRank score --
    # and pull in documents BM25 missed entirely, via pure embedding similarity
    # across the whole corpus (see app/semantic.py's semantic_rerank docstring
    # for why that second part is necessary, not optional).
    if rerank:
        # only let augmentation (semantic-only, whole-corpus finds) run for
        # queries with no explicit hard constraint it could bypass -- see
        # semantic_rerank()'s docstring for why this is a constraint check,
        # not a candidate-count check
        allow_augmentation = not (
            structured["required"] or structured["excluded"]
            or structured["excluded_phrases"] or structured["phrases"]
        )
        # embed the RAW query, not the spell-corrected one -- SymSpell "corrects"
        # any word absent from this corpus to the nearest in-corpus word within
        # edit distance 2, even when the original word is perfectly valid
        # English (e.g. "sick" -> "since", "get" -> "gem", observed directly
        # while testing this). That correction actively hurts a semantic model,
        # which handles real-world text (typos included) far better than
        # edit-distance correction does, and doesn't need it in the first place.
        ranked_ids, scores = semantic_rerank(
            q, ranked_ids, scores, semantic_model,
            doc_embeddings, doc_id_to_embedding_index, embedding_doc_id_order,
            allow_augmentation=allow_augmentation)

    scored = [  # build the result objects, in ranked order -- NO snippet yet;
        # generating one requires re-tokenizing the full document, which is by
        # far the most expensive step per result (see the design doc's Phase 4
        # corpus-scaling notes), so it's deferred until we know which handful of
        # results actually need to be shown, in _build_search_response() below
        {
            "doc_id": doc_id,
            "title": docs[doc_id]["title"],
            "company": docs[doc_id].get("company"),
            "url": docs[doc_id].get("url"),
            "score": scores[doc_id],
        }
        for doc_id in ranked_ids
    ]

    # collapse duplicate postings (same title+content), keeping the highest-scoring copy of each
    deduped = dedup_results(scored, docs)

    # only cache the success path -- the unknown-word / no-searchable-terms
    # branches above are cheap early exits, not worth caching forever.
    # `structured` is cached alongside the results because snippet generation
    # (deferred to _build_search_response) needs it on a cache HIT too, not
    # just on the miss path that originally parsed the query.
    did_you_mean = search_query if correction["suggestions"] else None
    search_cache.set(cache_key, (deduped, did_you_mean, structured))

    response = _build_search_response(
        q, page, page_size, deduped, did_you_mean, structured)
    log_request(logger, query=q, rerank=rerank, latency_ms=round((time.perf_counter() - request_start) * 1000, 2),
                result_count=len(deduped), cache_hit=False)
    return response


# shared by both the cache-hit and cache-miss paths: slice the (already ranked
# + deduped) result list into the requested page, THEN generate snippets only
# for that page -- not for the full candidate/result set, which is what made
# large-corpus queries slow (see design doc, Phase 4 corpus-scaling notes)
def _build_search_response(q: str, page: int, page_size: int, deduped: list, did_you_mean, structured: dict):
    total_results = len(deduped)
    start = (page - 1) * page_size
    end = start + page_size
    page_results = deduped[start:end]  # slice out just the requested page

    results_with_snippets = [
        {**result, "snippet": build_snippet(docs[result["doc_id"]], structured)}
        for result in page_results
    ]

    return SearchResponse(
        query=q,
        page=page,
        page_size=page_size,
        total_results=total_results,
        total_pages=(total_results + page_size - 1) // page_size if total_results else 0,
        results=results_with_snippets,
        did_you_mean=did_you_mean,
    )
