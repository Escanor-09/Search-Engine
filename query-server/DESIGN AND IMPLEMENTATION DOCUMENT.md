# DESIGN AND IMPLEMENTATION DOCUMENT

_This is the complete, evolving version of the project's design document. It follows the same template as the original draft (`DESIGN AND IMPLEMENTATION DOCUMENT 3a576dff9cb1804db52ac3852d2c12ce.md`), but every section is filled in, and it is updated at the end of each phase rather than left as a snapshot of Phase 2. Sections that were empty headers in the original (Scalability, Limitations, Future Roadmap, Interview Questions, Glossary) are written out in full here._

- REPORT TEMPLATE
  EXECUTIVE SUMMARY
  - GOAL
  - PROBLEM STATEMENT
  - MOTIVATION
  - CURRENT FEATURES
  - FUTURE ROADMAP
    REQUIREMENTS
  - FUNCTIONAL
  - NON FUNCTIONAL
    SYSTEM ARCHITECTURE
  - ONE DIAGRAM PER MODULE
    COMPLETE REQUEST FLOW
  - EXPLAIN EVERY FUNCTIONAL CALL
    COMPONENT DOCUMENTATION
  - ONE SECTION PER FILE
    ALGORITHMS
    DESIGN DECISIONS
  - DECISION
    - WHY?
    - ALTERNATE
    - WHY REJECTED?
      COMPLEXITY ANALYSIS
  - FUNCTION
    - TIME
    - SPACE
      SCALABILITY
      LIMITATIONS
      FUTURE ROADMAP
      INTERVIEW QUESTIONS
      GLOSSARY

---

# EXECUTIVE SUMMARY

### Goal

The goal of this project is to design and implement a search engine completely from scratch, in order to understand how modern information retrieval systems operate internally — not just how to call one.

The long-term objective is to evolve this project into a production-inspired search engine capable of supporting:

- efficient indexing
- fast query processing
- scalable retrieval
- intelligent ranking (relevance + authority)
- typo tolerance
- semantic search
- distributed indexing
- learning-to-rank models

The project therefore serves two purposes:

1. Learn the theoretical foundations of Information Retrieval.
2. Demonstrate practical software engineering skills expected in large-scale backend systems.

### Problem Statement

Searching through large collections of documents is fundamentally different from searching through small datasets.

Suppose we have one million job postings. A naive solution would examine every document for every query. This approach has time complexity O(N) per query. As the number of documents grows, response time increases linearly.

Modern search engines solve this problem differently. Instead of searching documents, they search an **index**. An index maps words directly to the documents containing those words. This changes retrieval from

> Search every document

to

> Directly jump to candidate documents.

But finding candidate documents is only half the problem. Once you have candidates, you still need to decide **which ones matter most** (ranking), **which one wins when two documents are near-duplicates** (deduplication), **how to show the user why a result matched** (snippets), and **how to hand back a million matches without drowning the client** (pagination). Phase 3 of this project is specifically about that second half — going from "a list of matching documents" to "a genuinely useful ranked results page."

The objective of this project is to build every stage of this pipeline manually, understanding the tradeoffs at each stage rather than treating any of it as a black box.

### Motivation

Most developers understand how to use a search engine but not how one actually works. This project addresses that gap by implementing every core algorithm from first principles (with a few library-assisted MVP steps, clearly flagged as such — see Design Decisions).

**Educational Motivation**

Develop a deep understanding of Information Retrieval concepts such as:

- tokenization
- inverted indexes
- document ranking (TF-IDF, then BM25)
- link-based authority (PageRank)
- query parsing
- phrase retrieval
- spell correction
- snippet generation and highlighting
- deduplication
- pagination
- index optimization

**Engineering Motivation**

Learn how large backend systems are designed. The project emphasizes:

- modularity
- maintainability
- scalability
- separation of concerns

rather than simply producing correct output.

**Interview Motivation**

Search engines combine concepts from several computer science subjects:

- Data Structures
- Algorithms
- Operating Systems
- Databases
- Information Retrieval
- Graph Theory (PageRank)
- Distributed Systems
- Software Engineering

Because of this, they are frequently discussed during interviews for backend engineering roles. A dedicated Interview Questions section, grounded in the actual decisions made in this codebase, appears near the end of this document.

### Current Features

Features are grouped by the phase in which they were introduced, so this document doubles as a change history. Everything listed under an earlier phase is still present in the current system unless explicitly stated otherwise (e.g. in Limitations).

**Phase 1 — Bare-bones pipeline**

- Simple tokenizer (lowercase, strip punctuation, split on whitespace)
- Naive index / lookup against a stub corpus
- Plain TF-IDF scoring
- A single FastAPI endpoint, `GET /search?q=...`, returning ranked doc IDs and titles
- Manual testing against a small corpus

**Phase 2 — Real query processing**

- **Corpus Loading** — The corpus is stored as structured JSON documents containing metadata such as title, company, location, content, and URL. During startup, the corpus is loaded once and reorganized into a dictionary keyed by document ID for constant-time document lookup.
- **Tokenization Pipeline** — Every document and every query passes through the same normalization pipeline: lowercase → remove punctuation → split into words → remove stopwords → Snowball stemming → normalized tokens. A shared tokenizer ensures indexed terms and query terms are transformed identically before matching. A lighter tokenizer without stemming is used separately for spell correction, since correction needs to compare real word forms.
- **Positional Inverted Index** — Instead of storing `python → {1, 5, 9}`, the index stores `python → {1: [3, 15], 5: [9], 9: [1, 7, 18]}`. This positional information enables phrase queries and allows term frequencies to be computed directly from the index without re-tokenizing documents.
- **Boolean Retrieval** — AND, OR, NOT queries, implemented using set operations (intersection, union, difference). The parser separates required, optional, and excluded terms; the retrieval stage combines them into the final candidate set.
- **Phrase Search** — Quoted phrases (e.g. `"machine learning"`) are extracted, tokenized through the same normalization pipeline, and verified against the positional index for consecutive occurrence. Phrase matches receive an additional ranking boost.
- **Spell Correction** — Automatic spelling correction before query execution, using a dictionary built entirely from the indexed corpus rather than a general English dictionary. Implemented with SymSpell, max edit distance 2, preserving boolean operators and quoted-phrase boundaries while correcting only searchable terms.
- **TF-IDF Ranking** — Candidate documents ranked using term frequency × inverse document frequency, plus the phrase boost.
- **REST Search API** — `GET /search?q=...`, exposed via FastAPI. Pipeline: validate → spell-correct → parse → retrieve candidates → rank → respond. All heavyweight preprocessing (corpus load, positional index, document lengths, spelling dictionary) happens once at startup.
- **Manual QA harness** — `tests/test_queries.md` (a written log of ~20 manual test queries covering every Phase 1/2 feature) and `tests/run_queries.sh` (a curl script that fires all of them at the running server and writes timestamped JSON output to a results file), used to verify behavior by hand before moving to the next phase.

**Phase 3 — Real ranking**

- **BM25 Relevance Ranking** — TF-IDF is replaced by BM25 (via the `rank_bm25` library, `BM25Okapi`) as the primary relevance signal. See Design Decisions for why the library was chosen for this MVP over a hand-rolled implementation, and Future Roadmap for the planned custom version.
- **Synthetic Link Graph** — `data/corpus.json` was extended with a `links` field per document (a list of other document IDs it "links to"), generated with a seeded random process (seed 42, 2–4 outlinks per doc) to stand in for what a real web-crawler component would have produced. Verified: no self-links, no dangling references, in-degree ranging 1–7 across the corpus.
- **PageRank Authority Scoring** — `networkx.pagerank()` computes an authority score per document from the link graph, once at startup. Authority is combined with BM25 relevance via a weighted linear sum (`0.85 × BM25_norm + 0.15 × PageRank_norm`), both min-max normalized first so they live on a comparable scale. The combination step is isolated in its own module (`authority.py`) precisely so a delay or absence of real crawler data never blocks the rest of the ranking pipeline.
- **Snippet Generation with Highlighting** — Each result now includes a `snippet` field: a ~25-word excerpt centered on the first query-term match in the document, with matched words wrapped in `<mark>` tags. Matching is done by _stem_, not literal substring, using the same `tokenize()` pipeline as indexing — so a query for "engineers" correctly highlights "Engineer" in the text.
- **Deduplication** — Documents with identical (whitespace-normalized, case-insensitive) title + content are collapsed to a single result, keeping the highest-scoring copy. Verified against a genuine duplicate pair already present in the corpus (doc 49 and doc 79 — same posting, different `location`).
- **Pagination** — `page` and `page_size` query parameters (defaults 1 and 10, max page size 50), applied after sorting and deduplication. The response reports `total_results` and `total_pages`.
- **Deterministic Tie-Breaking** — Results are sorted by `(-score, doc_id)` rather than score alone, so documents with identical scores always return in the same order across requests — not left to depend on Python set iteration order.
- **New dependencies** — `rank_bm25`, `networkx`, `numpy` (transitive, via `rank_bm25`), and `scipy` (transitive, discovered only when `networkx.pagerank()` crashed at startup without it — see Design Decisions and the incident note in Limitations).
- **Bug found during Phase 3 manual testing** — Boolean `AND` queries where the first term appears _before_ the `AND` keyword (e.g. `python AND kubernetes`) were silently misparsed as `OR` due to how the query parser's "sticky mode" logic handles words seen before the first operator. Root-caused, fix designed and verified in isolation. See Design Decisions §22 and Limitations for current status.

**Phase 4 — Production readiness, and a friend's C++ index as a reference implementation**

- **Autocomplete (`/suggest`)** — prefix-based term suggestions built from the corpus vocabulary at startup (`app/suggest.py`) and looked up via binary search over a sorted term list, ranked by corpus-wide frequency.
- **Typed Response Schemas** — every endpoint (`/search`, `/suggest`, `/health`) now declares a Pydantic `response_model` (`app/schemas.py`) instead of returning free-form dicts, giving FastAPI's OpenAPI docs and response validation a concrete contract instead of an implicit one.
- **Repeated-Query Caching** — an in-memory LRU cache (`app/cache.py`, backed by `cachetools.LRUCache`) keyed on the normalized query string, storing the full ranked-and-deduplicated result list _before_ pagination — so a repeated query (any page of it) skips spellcheck, parsing, retrieval, BM25/PageRank scoring, snippet generation, and deduplication entirely, going straight to the pagination slice.
- **Structured (JSON) Logging** — every `/search` request emits one JSON log line (`app/logging_config.py`) recording query, latency, result count, and cache-hit status. Deliberately JSON from day one, so this data can directly feed Phase 5's evaluation/A-B analysis without a log-reformatting step later.
- **Rate Limiting** — `/search` and `/suggest` are capped at 30 requests/minute per client IP (`slowapi`, in-memory storage — no external service required), returning HTTP 429 once exceeded.
- **Global Error Handling** — an unhandled-exception handler now guarantees a clean JSON 500 response instead of ever leaking a raw traceback to a client.
- **`/health` Endpoint** — reports operational status, corpus size, uptime, and startup timestamp.
- **A friend's C++ indexing engine (`index.cpp`) as a design reference** — a teammate working on the indexing side independently shared a from-scratch C++ inverted-index implementation (positional postings, BM25 scoring, binary disk persistence). Two of its ideas were ported into this Python codebase (its flat `termDictionary`/`globalPostingPool` array layout was deliberately **not** ported — see Design Decisions §28):
  - **Hand-Rolled BM25** — `rank_bm25` was removed entirely and replaced with a from-scratch implementation (`app/bm25.py`) following `index.cpp`'s `searchBM25()` formula (`k1=1.2`, `b=0.75`, the "+1" idf variant) exactly, generalized from single-term to multi-term queries. This closes the O(N×q) whole-corpus-rescan gap flagged as a Phase 3 Future Roadmap item — BM25 is now scored directly against the candidate set, O(m×q). See Design Decisions §29 for why its raw scores don't numerically match `rank_bm25`'s (a different, also-legitimate BM25 variant), and why that's fine.
  - **Single-Pass Index Construction** — `build_inverted_index()` and `build_doc_lengths()` (previously two separate full-corpus tokenization passes) were merged into one `build_index()` pass, following the shape of `index.cpp`'s `InvertedIndex::build()`. This pass also now computes `avg_doc_length` and `total_docs_count` as first-class values — exactly the two corpus-wide numbers the hand-rolled BM25 above needs.
  - **Index Persistence** — the positional index, doc lengths, and corpus-wide stats are now cached to disk (`app/persistence.py`, `data/index_cache.pkl`) and reloaded on the next startup instead of being rebuilt from `corpus.json` every time, with a corpus-mtime check that rejects a stale cache automatically. Conceptually ported from `index.cpp`'s `saveToDisk()`/`loadFromDisk()`, using `pickle` instead of hand-rolled binary encoding — Python doesn't need to manage its own byte layout the way the C++ original does.
- **New dependencies** — `cachetools`, `slowapi` (pulling in `limits`, `Deprecated`, `wrapt`, `packaging` transitively). **Removed dependency** — `rank_bm25`, now that BM25 is hand-rolled.

**Phase 4.5 — Corpus scale-up, and two real bugs found by scaling it**

- **Corpus grown from 100 to 1,000 documents, and from one domain to ten** — `data/corpus.json` was regenerated (`scripts/generate_corpus.py`, template-based, not hand-written) to span tech, healthcare, finance, education, sports, entertainment, food, travel, science/environment, and law/government (100 docs each), each with 300-500 words of content (measured: min 473, max 500, mean 488.9 words). The original 100-doc corpus is preserved at `data/corpus_v1_100docs_backup.json`. Vocabulary grew from 77 to 1,104 stemmed terms; `avg_doc_length` grew from 32.5 to 351.9 tokens; corpus file size grew from 50KB to 3.7MB.
- **Startup cost, measured before/after:** single-pass index build (tokenize + positional index) now takes 1.58s cold, 0.03s from the Phase 4 on-disk cache — confirming that cache is now doing real work, not just theoretical work. PageRank over 1,000 nodes: 9ms (no scaling concern at this size).
- **Bug found by the scale-up: snippet generation was the dominant cost, not BM25.** A `climate` query (100 candidates) cost 204ms total, profiled as 237ms of that in `build_snippet()` alone — called for every ranked candidate, before pagination, exactly the O(m×L) cost the Phase 3 Scalability section had already flagged as "what breaks second." **Fixed** by moving snippet generation to run only on the page slice actually being returned (`app/main.py`, `_build_search_response()`), after dedup/pagination instead of before. Measured result: the same query dropped from 204ms to 32ms on a cache miss (6.4× faster) — cost now scales with `page_size`, not candidate count.
- **Bug found by the scale-up: phrase queries barely filtered anything.** `retrieve_candidates()` used an included phrase only as a scoring boost (Limitation carried from Phase 2/3); at 100 docs this was easy to miss, but at 1,000 docs a query like `"renewable grid development"` returned **995 of 1,000 documents**. **Fixed** (`app/index.py`) — an included phrase is now a hard requirement on the candidate set. Measured result: the same query dropped from 995 to **7** results, all genuinely on-topic.
- **Test coverage rewritten for the new corpus** — `tests/test_queries.md` now has 55 cases spanning all 10 domains plus regression coverage for both fixes above.

**Phase 5 — Semantic re-ranking and a quantified evaluation**

- **Semantic re-ranking (`app/semantic.py`)** — an opt-in `rerank=true` parameter on `/search`. Every document gets one precomputed sentence embedding at startup (`all-MiniLM-L6-v2`, 384-dim, via `sentence-transformers`), cached to disk the same way the index is (`data/embeddings_cache.pkl`). At query time, the top-K (30) BM25-ranked candidates are re-ordered by a 50/50 blend of BM25+PageRank score and cosine similarity to the query embedding.
- **Augmentation, not just re-ranking** — a pure "re-rank BM25's top-K" design has nothing to reorder when a query shares no vocabulary with its target documents at all (BM25 finds zero candidates). `semantic_rerank()` also compares the query embedding against the **whole corpus**, surfacing up to 15 documents BM25 never retrieved — but only for queries with no explicit `AND`/`NOT`/phrase constraint, so a confident boolean query is never diluted with semantic-only extras that might not actually satisfy it.
- **Three real bugs found and fixed while verifying this against live queries, not assumed correct:**
  1. A normalization bug gave every augmented (semantic-only) document a fabricated `0.0` BM25 score, which min-max-normalized as *worse than the worst real BM25 candidate* — fixed by scoring augmented docs purely on semantic similarity, not a fabricated lexical score.
  2. Augmentation initially bypassed explicit boolean constraints entirely (a confident `python AND kubernetes` query was getting diluted with 15 unrelated "semantically similar" docs) — fixed by gating augmentation on whether the query has any explicit `required`/`excluded`/`phrases` constraint, not on candidate count (candidate count is a false signal — a query can retrieve hundreds of candidates via one noisy common word while still being poorly served).
  3. The corpus-derived spellchecker was silently corrupting semantic queries before they reached the embedding model — e.g. correcting `sick → since` and `get → gem` (both valid English words, just absent from this corpus's narrow template vocabulary) — fixed by embedding the **raw** query, not the spell-corrected one, since embeddings don't need lexical correction and it was actively hurting them.
- **Evaluation framework (`scripts/evaluate.py`)** — Precision@10, MRR, and nDCG@10, computed against a 20-query judgment set (10 lexical control queries + 10 semantic paraphrase queries) with **programmatically-derived ground truth** (this corpus is synthetic, so relevance is determined from the same generation metadata — title-topic match for lexical queries, `category` match for semantic queries — rather than independent human judgment; see Design Decisions for why that's the honest characterization). Both search modes run through the exact same code path `/search` uses.
- **Measured result:** overall, Precision@10 0.555→0.625 (+12.6%), MRR 0.687→0.782 (+13.8%), nDCG@10 0.635→0.708 (+11.5%). Split by query type: the **lexical control group barely moves** (P@10 0.510→0.520) — confirming semantic re-ranking doesn't hurt queries BM25 already handles well — while the **semantic/paraphrase group improves substantially** (P@10 0.600→0.730, +21.7%; MRR 0.604→0.740, +22.5%; nDCG@10 0.600→0.725, +20.8%). Full per-query results and the honest misses (one query regressed, one scored 0.0 under both modes) are in the evaluation report and `data/evaluation_results.json`.
- **New dependencies** — `sentence-transformers` (pulling in `torch`, `transformers`, `huggingface_hub`, `tokenizers`, `safetensors`, `scikit-learn`, and their transitive dependencies).

### Future Roadmap

A one-paragraph summary; the full breakdown is in the dedicated **FUTURE ROADMAP** section near the end of this document.

Phase 4 closed three items that were open at the end of Phase 3: BM25 is now hand-rolled instead of library-based, the index survives a server restart via an on-disk cache, and the API layer gained caching, structured logging, rate limiting, autocomplete, and a health endpoint. Scaling the corpus to 1,000 documents (Phase 4.5) then surfaced and closed two real bugs — a snippet-generation bottleneck and a non-functional phrase filter — that were invisible at 100 documents. Phase 5 added the differentiator the project's own Phase 3/4 roadmap had been pointing toward: semantic re-ranking with a quantified before/after (see Executive Summary above for the numbers), not just a qualitative claim that it works. What's left: the two known query-parsing/retrieval gaps identified during Phase 3 (still untouched), replacing the synthetic link graph with a real crawler once available, learning-to-rank, and an automated test suite — the last of which is more overdue with every phase that keeps relying on manual verification instead.

---

# REQUIREMENTS

### Functional

1. **Document Indexing** — The system shall ingest a structured document corpus and build a searchable positional inverted index before serving requests.
2. **Query Processing** — The system shall normalize user queries using the same tokenization pipeline applied during indexing, to ensure consistent term matching.
3. **Boolean Retrieval** — The system shall support AND, OR, NOT operators within search queries.
4. **Phrase Search** — The system shall support exact phrase queries enclosed in quotation marks.
5. **Spell Correction** — The system shall detect misspelled terms and generate corrections using a dictionary derived from the indexed corpus.
6. **Relevance Ranking** — The system shall rank retrieved documents by estimated relevance using BM25, with an exact-phrase-match bonus.
7. **Authority Ranking** — The system shall factor a link-graph-derived authority score (PageRank) into the final ranking, combined with relevance via a pluggable weighted-combination step.
8. **Snippet Generation** — The system shall return a highlighted text excerpt for every result, showing the matched query terms in context.
9. **Deduplication** — The system shall detect and collapse duplicate documents in the result set, keeping only the highest-scoring copy of each.
10. **Pagination** — The system shall support paging through results via `page` and `page_size` parameters, and report total result/page counts.
11. **Deterministic Ordering** — The system shall break ranking ties deterministically, so identical queries return identically ordered results across repeated requests.
12. **REST Interface** — The system shall expose search functionality through a REST API returning JSON responses.
13. **Query Validation** — The system shall reject invalid inputs before query processing, including empty queries, control characters, excessively long inputs, and inputs without alphanumeric characters, plus invalid pagination parameters.
14. **Autocomplete** — The system shall provide prefix-based query suggestions drawn from the corpus vocabulary, via a dedicated endpoint separate from `/search`.
15. **Repeated-Query Caching** — The system shall cache the full ranked result set for a previously-seen query, keyed on the normalized query text, so a repeated query does not repeat retrieval or ranking work.
16. **Structured Logging** — The system shall log every search request in a machine-readable (JSON) format, capturing at minimum the query, latency, result count, and whether the result was served from cache.
17. **Rate Limiting** — The system shall limit the request rate accepted from a single client, rejecting requests beyond that limit with a clear error rather than degrading silently.
18. **Health Reporting** — The system shall expose an endpoint reporting operational status and basic corpus/uptime metadata, suitable for automated liveness checks.
19. **Graceful Error Handling** — The system shall return a well-formed JSON error response for any unexpected server-side failure, never a raw stack trace.
20. **Index Persistence** — The system shall be able to reuse a previously-built index across server restarts, rebuilding from the source corpus only when no valid cached index exists.

### Non-Functional

1. **Performance** — The system should minimize query latency by avoiding repeated preprocessing. Indexes, document lengths, BM25 statistics, the link graph, PageRank scores, and the spelling dictionary are all constructed once during application startup rather than rebuilt per request — and, as of Phase 4, the index itself is persisted to disk so a restart doesn't pay that startup cost again either. Within a request, BM25 is scored exactly once per query, directly against the candidate set, never once per candidate document in a loop. As of Phase 4, a repeated query additionally short-circuits the entire retrieval/ranking pipeline via an in-memory result cache.
2. **Correctness** — Every document and every query must pass through an identical normalization pipeline to ensure deterministic matching. Where this invariant was violated (see the Phase 3 AND-parsing bug), it is treated as a defect to be fixed, not a quirk to work around.
3. **Maintainability** — The project is organized into independent modules with clear responsibilities: tokenizer, indexing, ranking, authority scoring, snippet generation, deduplication, parsing, validation, spell correction, and the API layer. This separation reduces coupling and makes future features easier to add.
4. **Extensibility** — The architecture is intentionally designed so individual components can be replaced independently. Examples already exercised in this project: TF-IDF was replaced by BM25 without touching retrieval or the API layer; PageRank was added as an entirely separate, optional module that the rest of the pipeline doesn't depend on existing. Future examples include replacing SymSpell with another correction algorithm, or replacing the ranking stage with a learning-to-rank model.
5. **Scalability** — Although the current implementation operates entirely in memory over a 100-document corpus, the design anticipates future support for compressed indexes, incremental updates, distributed storage, and larger corpora. See the dedicated Scalability section for what would need to change first.
6. **Reliability** — Invalid user input (including now-invalid pagination parameters) is detected before entering the retrieval pipeline, preventing unnecessary computation and malformed requests from propagating through later stages.
7. **Testability** — Each module exposes focused responsibilities and can be tested independently: tokenizer correctness, parser correctness, phrase matching, boolean retrieval, ranking, spell correction, snippet generation, and deduplication can all be verified without running the complete search engine. In practice, verification so far has been manual (see Limitations) rather than an automated suite — this is flagged as a Future Roadmap item.
8. **Determinism** — Given the same corpus and the same query (including page/page_size), the system should always return results in the same order. This became an explicit requirement in Phase 3 once ranking ties (e.g. from PageRank producing identical normalized scores) became possible in a way TF-IDF rarely produced.
9. **Observability** — Every search request must be logged in a structured, machine-parseable format (query, latency, result count, cache status) from the moment logging exists at all, so that later phases (evaluation, A/B analysis) can consume this data directly without a retroactive format change.

---

# SYSTEM ARCHITECTURE

### Architectural Philosophy

The search engine follows a **modular pipeline architecture**. Each module is responsible for exactly one task. Data flows sequentially through the pipeline, where the output of one stage becomes the input to the next. This follows the **Single Responsibility Principle (SRP)**, making the system easier to understand, test, maintain, and extend.

As of Phase 3, the architecture spans **seven conceptual layers** (up from six in Phase 2):

1. API Layer
2. Validation Layer
3. Query Processing Layer
4. Retrieval Layer
5. Ranking Layer _(now itself a fusion of two sub-signals: relevance and authority)_
6. Authority Layer _(new — startup-only, feeds into Ranking)_
7. Response Layer _(now includes snippet generation, deduplication, and pagination, not just JSON formatting)_

Each layer is independent of the others except through clearly defined interfaces.

**Phase 4 addendum:** rather than inserting an eighth sequential layer, Phase 4's additions are cross-cutting concerns that wrap the existing seven layers instead of sitting between them in the pipeline — see "Phase 4 — Cross-Cutting Concerns" below for each one's diagram. Autocomplete is the one exception: it's a genuinely separate, parallel pipeline (its own startup-built index, its own endpoint), not a layer inside `/search` at all.

### High-Level System Architecture

```jsx
                                User
                                  │
                                  ▼
                         FastAPI Search API
                                  │
        ┌─────────────────────────┴─────────────────────────┐
        │                                                     │
        ▼                                                     ▼
 Input Validation                              Startup Initialization
        │                                                     │
        ▼                                                     ▼
 Spell Correction                       Corpus + Positional Index
        │                                                     │
        ▼                                                     ▼
 Query Parsing                          Document Length Table
        │                                                     │
        ▼                                                     ▼
 Boolean Retrieval                      SymSpell Dictionary
        │                                                     │
        ▼                                                     ▼
 Candidate Documents                    Positional Index + Doc Lengths (Phase 4: hand-rolled BM25 reads these directly)
        │                                                     │
        ▼                                                     ▼
 BM25 + PageRank Fusion  ◄──────────────  Link Graph → PageRank (normalized)
        │
        ▼
 Snippet Generation
        │
        ▼
 Deduplication
        │
        ▼
 Pagination
        │
        ▼
 JSON Response
```

The left-hand side is the **runtime query pipeline**. The right-hand side is initialized only once when the server starts. This separation avoids rebuilding expensive data structures — including PageRank scores — for every request; as of Phase 4, BM25 has no separate "model" to rebuild at all, since `app/bm25.py` scores directly against the positional index and doc lengths already built above.

### API Layer

**Responsibility:** entry point of the application.

- starting FastAPI
- loading the corpus, loading-or-building the positional index (Phase 4), and the link graph/PageRank scores
- receiving HTTP requests
- orchestrating the entire search pipeline
- formatting JSON responses (including pagination metadata)

```jsx
        Browser
           │
GET /search?q=...&page=...&page_size=...
           │
           ▼
      FastAPI Server
           │
           ▼
 search(q, page, page_size)
           │
           ▼
 Search Pipeline
```

The API layer never performs ranking, parsing, indexing, snippet generation, or deduplication itself. It delegates work to specialized modules. This keeps the API layer thin — a property that held through Phase 3 despite the pipeline growing by four new steps.

### Validation Layer

`validation.py` — ensure invalid queries never reach the retrieval engine.

```jsx
User Query / page / page_size
      │
      ▼
validate_query() + range checks
      │
 ┌────┴────┐
Valid   Invalid
 │          │
 ▼          ▼
Continue   HTTP 400
```

Rules: empty query, whitespace-only query, control characters, query length, punctuation-only query, `page < 1`, `page_size` outside `[1, 50]`. If validation fails, processing terminates immediately with an HTTP error — no downstream work is performed.

### Spell Correction

`spellcheck.py` — correct user spelling mistakes before retrieval. Unchanged since Phase 2.

```jsx
Raw Query
      │
      ▼
Split into words
      │
      ▼
Corpus Dictionary
      │
      ▼
SymSpell Lookup
      │
      ▼
Corrected Query
```

The dictionary is built entirely from the indexed corpus rather than a general English dictionary. Advantages: technical words preserved, company names preserved, domain-specific vocabulary recognized, fewer incorrect "corrections." Unknown words (no valid correction within edit distance 2) produce `{"message": "No results found."}` instead of a dangerous guess.

### Query Parser

`query_parser.py` — convert raw text into a structured query representation.

```jsx
Raw Query

python AND docker NOT java

            │
            ▼
         Parser
            │
            ▼
{
 required : [python, docker],
 optional : [],
 excluded : [java],
 phrases : []
}
```

The parser understands AND, OR, NOT, and quoted phrases. Every later component works on this structured representation instead of the raw string. **Known defect (Phase 3):** the example above is the _intended_ behavior; the _actual current_ behavior for this exact input is `required: [docker], optional: [python], excluded: [java]`, because "python" is parsed before any operator is seen. See Component Documentation → `query_parser.py` and Design Decisions §22 for the full explanation and the fix.

### Retrieval Engine

`index.py` — identify candidate documents. Retrieval behavior itself is unchanged since Phase 2. Phase 3 added a `rank_bm25` model builder to this file as a separate concern from candidate retrieval; Phase 4 removed that builder entirely and instead merged the corpus-tokenization pass into a single `build_index()` (see Component Documentation) that also now produces `avg_doc_length`/`total_docs_count` for the hand-rolled BM25 in `bm25.py`.

```jsx
Structured Query
        │
        ▼
Boolean Retrieval
        │
        ▼
Posting Lists
        │
        ▼
Set Operations
        │
        ▼
Candidate Documents
```

The retrieval engine never computes relevance. Its only job is answering _"which documents qualify?"_ — using OR, AND, NOT retrieval, and phrase verification, all via the positional inverted index. **Known limitation carried into Phase 3:** phrases are used here only to _filter out_ excluded-phrase matches, never to _require_ an included phrase to match. See Limitations.

### Ranking Engine

`ranking.py` — order candidate documents by estimated relevance **and** authority. Substantially rewritten in Phase 3.

```jsx
Candidate Documents
          │
          ▼
BM25 (whole corpus, ONE call per query)
          │
          ▼
Normalize BM25 (across candidates only)
          │
          ▼
Normalize PageRank (precomputed at startup)
          │
          ▼
Weighted Sum (0.85 × BM25 + 0.15 × PageRank)
          │
          ▼
Phrase Bonus (+2.0 flat, if applicable)
          │
          ▼
Final Score
```

The ranking engine does **not** find candidate documents — it assumes retrieval already happened. Its sole responsibility is scoring and, indirectly (via the score it returns), ordering.

**Phase 3 architectural change worth calling out explicitly:** Phase 2's `score_document()` scored one document at a time. Phase 3's `score_documents()` (plural) scores the _entire candidate set_ in a single call. This isn't a style choice — `rank_bm25.get_scores()` always recomputes relevance for the whole corpus regardless of how many documents you ask about, so calling it once per candidate would mean re-scoring the entire corpus once per candidate. Calling it once per _query_ and reusing the result keeps this to exactly one full-corpus pass no matter how many documents match.

### Authority Layer _(new in Phase 3)_

`authority.py` — build the link graph and compute PageRank, once at startup.

```jsx
corpus["links"] field
        │
        ▼
build_link_graph() → networkx.DiGraph
        │
        ▼
compute_pagerank() → {doc_id: raw_score}
        │
        ▼
normalize_pagerank() → {doc_id: 0..1}
```

This is deliberately its own module, not folded into `ranking.py`, so the authority signal is easy to swap out, delay, or disable entirely — the stated design goal being that a slow or missing crawler component should never block BM25 or anything else in the pipeline. Ranking only ever consumes the final `pagerank_norm` dict; it has no idea how that dict was produced.

### Snippet Generation _(new in Phase 3)_

`snippets.py` — build a highlighted excerpt per result.

```jsx
Doc text + structured query
        │
        ▼
Tokenize every word (stem-by-stem)
        │
        ▼
Find first word whose stem matches a query term
        │
        ▼
Window ±12 words around that match
        │
        ▼
Wrap matched words in <mark> tags
        │
        ▼
Snippet string
```

Matching is done by stem, not literal substring — reusing the exact same `tokenize()` pipeline used for indexing, so highlighting stays consistent with what actually caused the document to match in the first place.

### Deduplication _(new in Phase 3)_

`dedup.py` — collapse duplicate postings, keep the best-scored copy.

```jsx
Sorted, scored results
        │
        ▼
Fingerprint each doc (lowercased, whitespace-collapsed title+content)
        │
        ▼
Keep first (= best-scoring) occurrence of each fingerprint
        │
        ▼
Deduplicated results
```

This only works correctly because the results are already sorted best-first _before_ `dedup_results()` runs — "first occurrence wins" is what turns into "best-scoring copy wins."

### Pagination _(new in Phase 3, inside `main.py`)_

No dedicated module — a straightforward list slice applied after deduplication:

```jsx
Deduplicated Results
        │
        ▼
total_results = len(deduped)
        │
        ▼
start = (page - 1) × page_size
end   = start + page_size
        │
        ▼
Page Slice + Metadata
```

### Data Structures

The architecture relies on several core data structures.

| Structure                              | Shape                                                             | Purpose                                                                                  |
| -------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Corpus**                             | `docID → Document`                                                | O(1) document lookup                                                                     |
| **Positional Inverted Index**          | `term → docID → [positions]`                                      | retrieval, phrase search, term frequency, and (Phase 4) direct BM25 scoring               |
| **Document Length Table + Avg Length** | `docID → token count`, plus one corpus-wide float                 | Phase 4: actively used by hand-rolled BM25 (`app/bm25.py`) — no longer just kept for later |
| **SymSpell Dictionary**                | `word → frequency`                                                | spelling correction                                                                      |
| **Autocomplete Index**                 | sorted `[term, ...]` list + `{term: frequency}`                   | Phase 4: prefix lookup for `/suggest`                                                     |
| **Repeated-Query Cache**               | `cachetools.LRUCache`, normalized query → ranked result list      | Phase 4: skips the whole pipeline on a repeat query                                       |
| **Link Graph**                         | `networkx.DiGraph`, nodes = doc IDs, edges = `doc_id → linked_id` | input to PageRank                                                                        |
| **PageRank Scores (raw + normalized)** | `docID → float`                                                   | authority signal fed into ranking                                                        |

### Startup vs Runtime

One important architectural decision, carried forward and extended in Phase 3 and Phase 4, is separating expensive preprocessing from runtime operations.

**Startup** — executed exactly once:

```jsx
Load corpus
   ↓
Load index from disk cache, or build positional index + doc lengths + avg doc length (Phase 4)
   ↓
(Phase 4) Save index to disk cache, if it was just rebuilt
   ↓
Build SymSpell dictionary
   ↓
Build link graph
   ↓
Compute + normalize PageRank
   ↓
Build autocomplete index (Phase 4)
   ↓
Construct repeated-query cache (Phase 4)
```

**Runtime** — executed for every query:

```jsx
Validation
   ↓
Cache Lookup (Phase 4 -- hit short-circuits straight to Pagination)
   ↓
Spellcheck
   ↓
Parsing
   ↓
Retrieval
   ↓
BM25 + PageRank Fusion (one BM25 pass, reused for every candidate)
   ↓
Snippet Generation
   ↓
Deduplication
   ↓
Cache Store (Phase 4 -- success path only)
   ↓
Pagination
   ↓
Structured Log Line (Phase 4)
   ↓
JSON Response
```

This minimizes latency for every query after the first — the corpus never gets re-read, the positional index never gets rebuilt, and the BM25 scoring and PageRank scores never get recomputed per request. As of Phase 4, a repeated query doesn't even re-run the pipeline at all.

### Phase 4 — Cross-Cutting Concerns

Unlike Phases 1-3, these don't sit at a fixed position in the sequential pipeline — each wraps the request (or the startup sequence) as a whole.

**Repeated-Query Cache** (`cache.py`)

```jsx
Validated Query
      │
      ▼
SearchResultCache.get(q)
      │
 ┌────┴────┐
 Hit      Miss
 │          │
 ▼          ▼
Paginate   Run full pipeline
directly   (spellcheck -> ... -> dedup)
 │          │
 │          ▼
 │     SearchResultCache.set(q, deduped)  -- success path only
 │          │
 └────┬─────┘
      ▼
 Paginate + Respond
```

Keyed on the normalized query string, not `(query, page, page_size)` — the cache holds the full deduplicated list, and pagination is just a cheap slice applied after either path. The unknown-word and no-searchable-terms zero-result branches are deliberately never cached (see Design Decisions §30).

**Structured Logging** (`logging_config.py`)

```jsx
Request start (perf_counter)
      │
      ▼
   ... pipeline runs (cache hit or miss) ...
      │
      ▼
log_request(logger, query, latency_ms, result_count, cache_hit)
      │
      ▼
One JSON line to stdout
```

Every `/search` request logs exactly once, regardless of which branch it took (cache hit, cache miss, unknown-word rejection, no-searchable-terms rejection).

**Rate Limiting** (`slowapi`, wired in `main.py`)

```jsx
Incoming Request
      │
      ▼
Limiter checks (client IP, 30/minute)
      │
 ┌────┴────┐
 Under    Over limit
 limit     │
 │         ▼
 ▼      HTTP 429 (slowapi's default handler)
Endpoint runs
```

Runs *before* validation — an over-limit client never reaches `validate_query()` or anything past it.

**Autocomplete** (`suggest.py`) — a parallel pipeline, not a stage inside `/search`

```jsx
Corpus (startup)                    Request: GET /suggest?prefix=...
      │                                        │
      ▼                                        ▼
basic_tokenize() every doc              bisect to first match
      │                                        │
      ▼                                        ▼
{term: frequency} + sorted term list    walk forward while prefix matches
      │                                        │
      ▼                                        ▼
  (held in memory)                    sort by frequency desc, term asc
                                                │
                                                ▼
                                        Top-N suggestions
```

Uses `basic_tokenize()` (unstemmed), not the `tokenize()` pipeline the search index uses — a stemmed form like "engin" is correct for matching but useless to show a user as a suggested word.

**Index Persistence** (`persistence.py`) — changes *how* startup populates the Retrieval Layer, not its runtime behavior

```jsx
Server startup
      │
      ▼
load_index(cache_path, corpus_path)
      │
 ┌────┴─────────────────┐
 Valid cache          No cache / stale / incompatible
 │                       │
 ▼                       ▼
Use cached           build_index(docs)  -- single tokenization pass
inverted_index,             │
doc_lengths,                ▼
avg_doc_length,      save_index(...) -- write cache for next startup
total_docs_count            │
 └───────────┬──────────────┘
             ▼
     Continue startup (BM25 needs nothing further -- it
     reads inverted_index/doc_lengths directly per query)
```

Staleness is detected by comparing `corpus.json`'s file-modification time against the mtime recorded inside the cache file at build time — editing the corpus and restarting cannot silently serve a stale index.

---

# COMPLETE REQUEST FLOW

This chapter follows a single search request from the moment it enters the system until the response is returned, using two examples: one showing the full Phase 3 pipeline end-to-end, and one specifically illustrating the known boolean-parsing defect.

## Example 1 — Full Pipeline Walkthrough

**Request:** `GET /search?q=python&page=1&page_size=10`

**Step 1 — HTTP Request.** FastAPI routes the request to `search()` inside `main.py`.

**Step 2 — Validation.** `validate_query(q)` runs first: empty? whitespace? too long? control characters? contains letters? Then `page`/`page_size` are range-checked (`page ≥ 1`, `1 ≤ page_size ≤ 50`). Any failure returns HTTP 400 immediately; no further work happens.

**Step 2.5 — Cache Lookup (Phase 4).** `search_cache.get("python")` — assume this is the first time this query has been seen since startup, so it's a miss and the full pipeline below runs. (See Example 3 for the same query on a subsequent request, where this step short-circuits everything through Step 9.)

**Step 3 — Spell Correction.** `correct_query("python", sym_spell)` — "python" is already a known corpus word, so nothing changes. (If the input had been "pyhton," this step would return `corrected_query="python"` and a `suggestions` map, which later populates `did_you_mean` in the response.)

**Step 4 — Query Parsing.** `parse_query("python")` → `{required: [], optional: ["python"], excluded: [], phrases: [], excluded_phrases: []}`. A single bare word with no operator lands in `optional`.

**Step 5 — Candidate Retrieval.** `retrieve_candidates()`: since `required` is empty and `optional` is non-empty, `base = candidates(["python"], inverted_index)` — every doc_id whose postings list contains "python." No exclusions or phrase filtering apply here. Result (from real corpus data): 32 candidate doc IDs.

**Step 6 — Scoring (Phase 4: hand-rolled BM25).** `score_documents(candidate_ids, structured, inverted_index, doc_lengths, avg_doc_length, total_docs_count, pagerank_norm)`:

- `score_candidates()` (in `app/bm25.py`) computes `"python"`'s idf once, then scores each of the 32 candidates directly against the positional index and doc lengths — never touching a document outside the candidate set.
- The resulting 32 scores are min-max normalized against each other (not the whole corpus).
- Each candidate's final score = `0.85 × bm25_norm + 0.15 × pagerank_norm` (`pagerank_norm` was already precomputed at startup — no extra work here). No phrases were in this query, so no phrase bonus applies.

**Step 7 — Sorting.** `sorted(candidate_ids, key=lambda doc_id: (-scores[doc_id], doc_id))` — highest score first, doc_id as a deterministic tiebreaker.

**Step 8 — Snippet Generation.** For each of the 32 ranked results, `build_snippet(docs[doc_id], structured)` produces a ~25-word excerpt around the first occurrence of a word that stems to "python," with that word wrapped in `<mark>`.

**Step 9 — Deduplication.** `dedup_results(scored, docs)` fingerprints each of the 32 results and drops any that are exact duplicates of an already-kept (higher-ranked) result.

**Step 9.5 — Cache Store (Phase 4).** `search_cache.set("python", (deduped, did_you_mean))` — the full 32-result deduplicated list is cached under the raw query, before pagination is applied. This is what makes Example 3's follow-up request a hit.

**Step 10 — Pagination.** With `page=1, page_size=10`: `total_results` = the deduplicated count, `total_pages = ceil(total_results / 10)`, and the first 10 results are sliced out.

**Step 10.5 — Structured Log Line (Phase 4).** `log_request(logger, query="python", latency_ms=7.91, result_count=32, cache_hit=False)` — measured directly during Phase 4 verification.

**Step 11 — Response Generation.** `main.py` builds:

```json
{
  "query": "python",
  "page": 1,
  "page_size": 10,
  "total_results": 32,
  "total_pages": 4,
  "results": [
    {
      "doc_id": 87,
      "title": "Systems Engineer at Razorpay",
      "company": "Razorpay",
      "url": "https://example.com/jobs/87",
      "score": 0.9488,
      "snippet": "...knowledge of Docker, Linux, algorithms, <mark>Python,</mark> and C++..."
    }
  ],
  "did_you_mean": null
}
```

_(As of Phase 4, `did_you_mean` always appears — `null` when no correction happened — rather than being omitted, per the `SearchResponse` schema in `app/schemas.py`. Phase 2/3's behavior, kept here as a historical note, omitted the key entirely instead.)_

### Complete End-to-End Flow

```jsx
                     User
                       │
                       ▼
        GET /search?q=...&page=...&page_size=...
                       │
                       ▼
           Rate Limit Check (Phase 4)
                       │
                       ▼
              validate_query()
                       │
                       ▼
       search_cache.get(q) (Phase 4) ── hit ──▶ paginate(slice) ──▶ log_request() ──▶ Build JSON Response
                       │
                       │ miss
                       ▼
              correct_query()
                       │
                       ▼
               parse_query()
                       │
                       ▼
          retrieve_candidates()
                       │
                       ▼
             score_documents()  ◄── Phase 4: hand-rolled BM25, no more rank_bm25
                       │
                       ▼
                sort(results)
                       │
                       ▼
             build_snippet() × N
                       │
                       ▼
             dedup_results()
                       │
                       ▼
       search_cache.set(q, ...) (Phase 4, success path only)
                       │
                       ▼
              paginate(slice)
                       │
                       ▼
             log_request() (Phase 4)
                       │
                       ▼
             Build JSON Response
                       │
                       ▼
                    Client
```

## Example 2 — The Known Boolean-Parsing Defect

**Request:** `GET /search?q=python AND kubernetes`

Walking through Step 4 (Query Parsing) with the _current, as-shipped_ `query_parser.py`:

1. `python` is read while `current_mode` is still `None` (no operator seen yet) → falls into the `else` branch → added to `optional`.
2. `AND` is read → `current_mode` switches to `"AND"` — but only for words _after_ it.
3. `kubernetes` is read while `current_mode == "AND"` → added to `required`.

Result: `{required: ["kubernet"], optional: ["python"], excluded: []}` — **not** the intended `{required: ["python", "kubernet"], optional: [], excluded: []}`.

At Step 5, `retrieve_candidates()` then computes `base = required_ids | optional_ids` — a **union**, not an intersection — so any document containing _either_ "python" or "kubernetes" becomes a candidate. This was caught empirically: doc 87 ("Systems Engineer at Razorpay," verified to contain no mention of "kubernetes" at all) appeared as the #1 result for `python AND kubernetes`, which should be impossible for a correctly-functioning AND query.

The fix (designed and verified in an isolated test, described in full in Design Decisions §22) changes `query_parser.py` to retroactively promote already-collected `optional` terms into `required` the moment the _first_ operator encountered is `AND`. As of this writing, the fix has been designed, explained, and verified against multiple test cases, but its live status in the pasted codebase should be confirmed against the current `query_parser.py` before relying on `AND` queries — the corrected pipeline diagram above (Example 1) assumes correct parsing; this box exists specifically to flag where the current implementation still diverges from it.

## Example 3 — Cache Hit (Phase 4)

**Request:** `GET /search?q=python&page=2&page_size=2`, sent immediately after Example 1's `GET /search?q=python&page=1&page_size=2` already ran.

**Step 1 — HTTP Request + Validation.** Identical to Example 1.

**Step 2 — Cache Lookup.** `search_cache.get("python")` — Example 1's request already populated this entry (`search_cache.set("python", (deduped, did_you_mean))`, keyed on the normalized query, holding the full 32-result deduplicated list from before pagination was applied). This is a hit.

**Step 3 — Everything from spellcheck through deduplication is skipped entirely.** No `correct_query()` call, no `parse_query()` call, no `retrieve_candidates()`, no `score_documents()` (and therefore no BM25 or PageRank computation), no `build_snippet()` calls, no `dedup_results()`.

**Step 4 — Pagination.** `_build_search_response()` slices the cached 32-result list at `start=2, end=4` (`page=2, page_size=2`) — different results than Example 1's page 1, from the same cached list.

**Step 5 — Structured Log Line.** `{"timestamp": ..., "level": "INFO", "message": "request", "query": "python", "latency_ms": 0.02, "result_count": 32, "cache_hit": true}` — measured directly during Phase 4 verification: **0.02ms**, versus **7.91ms** for the equivalent cache-miss request. `result_count` reflects the full cached set (32), not the 2 results returned on this particular page.

**Step 6 — Response.** Same JSON shape as Example 1, just page 2's slice instead of page 1's, and no `did_you_mean` (this query needed no correction, which is also part of what's cached).

---

# COMPONENT DOCUMENTATION

Each module performs one well-defined task. This section documents every source file in the project, including the four introduced or substantially rewritten in Phase 3.

## tokenizer.py _(unchanged since Phase 2)_

Raw English → normalized sequence of searchable terms.

```jsx
Raw Text
↓
Lowercase
↓
Remove punctuation
↓
Split into words
↓
Remove stopwords
↓
Snowball stemming
↓
Normalized Tokens
```

Example:

```jsx
"The Python Developers were Running Fast."
↓ lowercase
"the python developers were running fast"
↓ tokenize
["the","python","developers","were","running","fast"]
↓ stopword removal
["python","developers","running","fast"]
↓ stemming
["python","develop","run","fast"]
```

Also exposes `basic_tokenize()` — lowercase/strip-punctuation/split _without_ stemming or stopword removal — used by spell correction, which needs to compare real word forms rather than stems.

**Why stemming?** Without it, "running," "runs," and "run" are three unrelated tokens; a search for "run" would miss documents containing only "running." After stemming, all three collapse to the same indexed term.

**Why Snowball over alternatives?**

| Option                | Pros                                                            | Cons                                                         |
| --------------------- | --------------------------------------------------------------- | ------------------------------------------------------------ |
| **Snowball (chosen)** | fast, lightweight, good accuracy/speed balance, built into NLTK | —                                                            |
| Porter Stemmer        | very popular                                                    | older algorithm, slightly less accurate                      |
| WordNet Lemmatizer    | produces real English words                                     | slower, requires POS tagging, more computationally expensive |

Snowball gives the best tradeoff for a lexical search engine of this scale.

## index.py — indexing changed in Phase 4

Implements the retrieval engine: builds the positional inverted index and retrieves candidate documents for a query. It's the most important module in the search engine because it eliminates the need to scan every document.

**Responsibilities:**

1. Build the positional index, doc lengths, and corpus-wide length stats in one pass: `Documents → term → docID → positions`, plus `docID → length`, `avg_doc_length`, `total_docs_count`.
2. Boolean retrieval — AND, OR, NOT via set operations.
3. Phrase matching using positional information.

**Internal data structures:**

```jsx
# Positional index
{
  "python": {
     2: [3, 9],
     5: [8],
     8: [17]
  }
}

# Document lengths
{0: 125, 1: 84, 2: 301}
```

**Phase 4 rewrite — `build_index(docs)` replaces `build_inverted_index()` + `build_doc_lengths()`:** ported from a teammate's C++ reference implementation, `index.cpp`'s `InvertedIndex::build()` — tokenize each document exactly once, and derive the positional postings, per-doc length, and corpus-wide `avg_doc_length`/`total_docs_count` from that single pass. Phases 2/3 tokenized the corpus in three separate passes across `build_inverted_index()`, `build_doc_lengths()`, and `build_bm25_index()` — harmless at 100 documents, but pure waste, and exactly the inefficiency the C++ source's single-loop design avoids. `build_bm25_index()` (the `rank_bm25`-based model builder) was deleted outright in Phase 4 — see the `ranking.py`/`bm25.py` entries below for its from-scratch replacement.

**Why `avg_doc_length` and `total_docs_count` are new:** `index.cpp`'s `build()` computes both directly because its hand-rolled BM25 needs them; our own hand-rolled BM25 (`app/bm25.py`) needs the exact same two numbers, which is why they're introduced in this pass rather than computed on demand later — this was flagged as intentional groundwork back in Phase 3's Design Decisions §13, before either `index.cpp` or the hand-rolled BM25 existed.

**Resolved in Phase 4.5 — the phrase-filter gap.** `retrieve_candidates()` used to treat `phrases` as a scoring boost only, never a hard filter — a phrase-only query (e.g. `"machine learning"`) returned nearly the entire corpus as candidates. Harmless-looking at 100 documents; at 1,000 it became impossible to ignore — `"renewable grid development"` returned **995 of 1,000 documents**. Fixed: an included phrase is now required (`all(phrase_match(...) for p in structured_query["phrases"])`), applied after the existing required/optional/excluded narrowing. Verified: the same query now returns **7** documents, all genuinely about renewable grid development. See Design Decisions for why this was deferred through Phase 3 and only fixed once the corpus scale made the cost of deferring it obvious.

## ranking.py — rewritten in Phase 3, BM25 source swapped in Phase 4

Ranks retrieved documents by estimated relevance **and** authority. Retrieval answers _"which documents qualify?"_; ranking answers _"which should appear first?"_

**Input:** candidate doc IDs, the structured query, the inverted index (for phrase checks), doc lengths + avg doc length + total doc count (Phase 4 — feeds the hand-rolled BM25), and the precomputed normalized PageRank scores.

**Output:** `{doc_id: final_score}`.

**Current ranking formula:**

```
final_score = 0.85 × normalize(BM25 scores among candidates)
            + 0.15 × normalize(PageRank scores, precomputed globally)
            + 2.0  (if an included phrase matches this doc)
```

**Phase 4 change — `score_documents()` no longer takes `bm25_model`/`doc_id_order`.** Those were the `rank_bm25` library's interface; they're gone now that `app/bm25.py`'s `score_candidates()` is called directly, scoring `candidate_ids` by doc_id rather than by array position, so no doc-ID-to-array-index mapping is needed anymore.

**Why `score_documents()` (plural) instead of Phase 2's `score_document()` (singular)?** The Phase 3 reason no longer applies as stated — `rank_bm25.get_scores()` used to rescore the _entire_ corpus on every call regardless of how many documents were needed, which is exactly the constraint the hand-rolled `score_candidates()` (Phase 4) removes by scoring only `candidate_ids` directly. What still justifies batching by query rather than by document: each query term's idf is a corpus-wide number, independent of which document is being scored, so computing it once per unique term and reusing it across every candidate (inside `score_candidates()`) avoids recomputing the same idf value once per document for no reason. See Complexity Analysis for the updated cost comparison.

**Why separate ranking from retrieval at all?** So each can evolve independently. TF-IDF → BM25 was a one-file change (`ranking.py`) that touched nothing in `index.py`, `query_parser.py`, or `main.py`'s retrieval call. Adding PageRank as a second signal required zero changes to retrieval either — it only extended what `score_documents()` does with an already-built candidate set.

## bm25.py — new in Phase 4

A from-scratch BM25 implementation, replacing the `rank_bm25` library. Ported from a teammate's C++ inverted-index project (`index.cpp`'s `InvertedIndex::searchBM25()`), which was shared partway through this project specifically as a working reference implementation for the "hand-roll BM25" item already sitting on the Phase 3 Future Roadmap.

**Functions:**

- `_idf(term, inverted_index, total_docs_count)` — `log((N - df + 0.5)/(df + 0.5) + 1.0)`, where `df` is how many documents contain `term`. The "+1" inside the log is copied directly from `index.cpp`'s formula, and is the same formula Lucene/Elasticsearch's default `BM25Similarity` uses — it guarantees `idf >= log(1) = 0` for any `df` in `[0, N]`, unlike the classic Robertson/Sparck-Jones idf (which `rank_bm25` used internally, and which *can* go negative — see Design Decisions §29 for why the two implementations don't produce matching raw scores, and why that's expected rather than a bug).
- `_term_score(term_idf, tf, dl, avg_doc_length)` — the per-posting formula from `searchBM25()`: `idf × (tf×(k1+1)) / (tf + k1×(1-b+b×dl/avgdl))`, with `k1=1.2, b=0.75` — the exact constants `index.cpp` uses.
- `score_candidates(candidate_ids, query_terms, inverted_index, doc_lengths, avg_doc_length, total_docs_count)` — sums `_term_score()` across every query term, for every candidate document. This is the one generalization beyond `index.cpp`'s source: `searchBM25()` only ever scores a single word; our boolean AND/OR queries need the sum-across-terms extension, which is standard BM25 but not something the C++ reference needed to implement.

**Why this only touches `candidate_ids`, not the whole corpus:** unlike `rank_bm25.get_scores()`, which always computed a score for every document in the corpus regardless of the query, `score_candidates()` never evaluates a document outside the already-filtered candidate set — closing the O(N×q) vs O(m×q) gap documented in Complexity Analysis.

**Verification performed before wiring this in (not just unit-level, but an actual comparison):** hand-rolled scores were compared against `rank_bm25`'s output for several real queries against the live corpus. Raw scores did not match — traced to `rank_bm25`'s different idf formula and different default `k1` (1.5, vs. `index.cpp`'s 1.2), not a defect in the port. What was checked instead, since `ranking.py` min-max normalizes BM25 scores before combining with PageRank: whether the two implementations produce the *same relative ranking order* among candidates. They did, on every query tested (top-10 order identical). See Design Decisions §29.

## semantic.py — new in Phase 5

Semantic (embedding-based) re-ranking on top of BM25 retrieval, opt-in via `/search?rerank=true`.

**Model:** `all-MiniLM-L6-v2` (`sentence-transformers`), 384-dim embeddings. Chosen for CPU-friendly inference speed over larger, more accurate embedding models — an MVP-first choice in the same spirit as Phase 3's initial `rank_bm25`/`networkx` decisions.

**Startup cost, measured:** loading the model takes ~10s; embedding all 1,000 documents takes ~8s. Both are paid once — embeddings are cached to disk (`data/embeddings_cache.pkl`, same mtime-staleness-check pattern as `persistence.py`'s index cache) and reloaded on subsequent restarts, though the model itself must still be loaded into memory every startup (~10-11s total) since it's needed to embed incoming queries, not just build the cache.

**Functions:**

- `build_doc_embeddings(docs, model)` — one embedding per document (title + content), computed once, analogous to `build_index()`'s single-pass philosophy.
- `semantic_rerank(query, ranked_ids, base_scores, model, doc_embeddings, doc_id_to_index, embedding_doc_id_order, top_k=30, weight=0.5, augment_k=15, allow_augmentation=True)` — does two things, not one:
  1. **Re-ranks** the top `top_k` BM25-ranked candidates by a 50/50 blend of their existing BM25+PageRank score and cosine similarity to the query embedding (both min-max normalized within the re-ranked group first).
  2. **Augments** — compares the query embedding against the embeddings of the *entire* corpus (one matrix multiply against already-precomputed vectors, not a re-embedding of anything), pulling in up to `augment_k` documents BM25 never retrieved at all.

**Why augmentation is necessary, not optional:** a "rerank the top-K BM25 results" design, taken literally, can only ever reorder documents BM25 already found. For a genuine paraphrase query sharing no literal vocabulary with its target documents, BM25 retrieves nothing — there is nothing to reorder, and the rerank step becomes a silent no-op. Comparing the query embedding against every document's embedding is cheap (a single `numpy` matrix multiply against vectors already computed at startup) and lets genuinely relevant documents surface by meaning even when lexical retrieval found zero candidates.

**Why `allow_augmentation` is a constraint check, not a candidate-count check.** The first implementation gated augmentation on `len(head) < top_k` — skip it if BM25 already found "enough" candidates. This was wrong, and caught by testing, not assumed: a query like `fighting global warming with clean power` retrieved 321 candidates purely via the generic word "global" (which appears across many unrelated domain templates) — a *high* candidate count driven by a *low-quality* lexical signal. The correct gate is whether the query has an explicit hard constraint (`required`, `excluded`, `excluded_phrases`, or `phrases`) that an augmented document — found by meaning alone, with no way to check any of those constraints — could violate. A confident `python AND kubernetes` query (`required` non-empty) never gets augmented; a pure optional/paraphrase query always can, regardless of how many (possibly noisy) candidates BM25 already found.

**Two more bugs found and fixed while verifying this against live queries:**

1. **Fabricated-score normalization bug.** Augmented documents initially received a placeholder BM25 score of `0.0` for blending purposes. Since real BM25 candidates in the re-ranked group typically all score `> 0`, min-max normalizing `0.0` alongside them made an augmented document look *worse than the worst real BM25 candidate* — even when its semantic similarity was the highest in the entire pool. Confirmed directly: for the climate-change paraphrase above, a genuinely on-topic document (query-doc cosine similarity 0.4777, verified in isolation) was ranked *behind* an unrelated tech job posting (similarity 0.0919) before this fix. Fixed by scoring augmented documents purely on semantic similarity (no fabricated base component at all), and by computing the base-score normalization range only from documents BM25 actually scored.
2. **Spellcheck was corrupting the query before it reached the embedding model.** `correct_query()` (Phase 2's corpus-derived SymSpell dictionary) "corrected" `sick → since` and `get → gem` for the query `helping sick people get better faster` — both are valid English words, just absent from this corpus's narrow template vocabulary, so SymSpell aggressively substituted the nearest in-corpus word within edit distance 2. `gem` then matched heavily against travel documents titled "... Hidden Gem Destination," pulling the whole result set off-topic. Fixed by embedding the **raw** query text, not the spell-corrected one, for the semantic step specifically — BM25 retrieval still benefits from correction, but embeddings don't need lexical correction and, as directly observed here, it can actively hurt them.

**Honest residual limitation:** even after fix #2, BM25's *own* candidate ordering (used to build the re-ranked "head") is still computed from the spell-corrected query, since that's Phase 2's existing, unmodified retrieval path. A corrected query can still bias which documents enter the head pool before semantic blending ever runs. Not fully solved — see Limitations.

## authority.py — new in Phase 3

Builds the link graph from each document's `links` field, and computes a normalized PageRank authority score per document.

**Functions:**

- `build_link_graph(docs)` → `networkx.DiGraph`, one node per document (even if it has zero in/out links), one edge per `(doc_id, linked_id)` pair.
- `compute_pagerank(graph)` → `{doc_id: raw_score}` via `networkx.pagerank()` (standard damping factor 0.85).
- `normalize_pagerank(scores)` → min-max scaled to `[0, 1]`, so it's on a comparable footing to normalized BM25 before `ranking.py` combines the two.

**Why its own file, not folded into `ranking.py`?** So the entire authority signal — build graph, compute PageRank, normalize — can be swapped out, mocked, or delayed without ranking.py needing to know or care. This directly serves the stated Phase 3 design goal: a slow or missing crawler component (in this project, standing in as the synthetic link graph) should never block BM25 or anything else.

## snippets.py — new in Phase 3

Builds a highlighted excerpt of a document's text, centered on the first query term it actually contains.

**Function:** `build_snippet(doc, structured_query) → str`

**Design highlights:**

- Matching is done by **stem**, not literal substring — every word in the doc is run through the same `tokenize()` pipeline used for indexing, so a query for "engineers" correctly highlights "Engineer" in the original text.
- A 12-word window on each side of the first match is kept (≈25 words total), with `...` prefixes/suffixes when the snippet doesn't start/end at the document boundary.
- Matched words are wrapped in `<mark>` tags — the standard HTML tag for "highlighted search text," rendered correctly by browsers with zero extra CSS if a frontend is ever built, and still readable as literal text if only consumed as raw JSON.

**Cost note, updated in Phase 4.5 — this call site moved, the function didn't.** `build_snippet()` itself is unchanged; what changed is *when* `main.py` calls it. Through Phase 4 it was called once per ranked candidate, before pagination — harmless at 100 documents, but measured at 1,000 documents to be **237ms of a 245ms total query** (a `climate` query, 100 candidates) — 97% of total latency, dwarfing BM25 scoring (0.09ms). Fixed by moving the call to `_build_search_response()`, after the page slice — snippets are now generated only for the ~10 results actually returned, not the full candidate set. Measured result: the same query dropped from 204ms to 32ms end-to-end (6.4× faster). Cost is now O(page_size × L), not O(m × L) — flat regardless of how many documents a query matches. See Complexity Analysis and Scalability for the updated figures, and Design Decisions for why cache hits got *slower* (0.02ms → ~20ms) as a direct consequence of this fix.

## dedup.py — new in Phase 3

Collapses duplicate postings, keeping the best-scored copy of each.

**Functions:**

- `_fingerprint(doc)` → lowercased, whitespace-collapsed `title + content` string.
- `dedup_results(scored_results, docs)` → walks an already-sorted (best-first) result list, keeps the first occurrence of each fingerprint, discards the rest.

**Why this matters for this specific corpus:** the corpus contains genuine duplicate postings — same title, same job description, differing only in `location` (e.g. doc 49 and doc 79, both "Backend Engineer at Tower Research," identical content). Without dedup, a user would see the same job twice. Verified directly: a query returning both would-be duplicates confirmed only the higher/first-ranked copy (doc 49) survived; doc 79 was correctly dropped.

**Scope of matching:** exact fingerprint only (after whitespace/case normalization) — not fuzzy or near-duplicate detection. See Limitations.

## spellcheck.py _(unchanged since Phase 2)_

Corrects user spelling mistakes. `User Query → Tokenize → Ignore Operators → SymSpell → Correct Query`.

**Dictionary source:** built from the indexed corpus, not a general English dictionary — recognizes company names, technical words, abbreviations, and domain vocabulary that a generic dictionary would flag as misspelled.

**Why SymSpell?** It precomputes delete-variants of every dictionary word once, up front, making lookup fast at query time.

| Option                   | Time Complexity                          | Notes                                   |
| ------------------------ | ---------------------------------------- | --------------------------------------- |
| Naive Levenshtein search | O(N) per lookup                          | compares against every dictionary word  |
| **SymSpell (chosen)**    | ~O(1) average lookup after preprocessing | preprocessing cost paid once at startup |

## query_parser.py

Converts raw queries into structured queries.

**Intended input/output:** `python AND docker NOT java` → `{required: ["python","docker"], optional: [], excluded: ["java"], phrases: []}`.

Extracts AND/OR/NOT, recognizes quoted phrases, normalizes query tokens via `tokenize()`, returns a structured representation. Without this parser, every later module would need to understand raw query strings; instead, retrieval receives structured data, which greatly simplifies retrieval logic.

**Sticky-mode design:** an operator (AND/OR/NOT) sets a "mode" that applies to every word after it, until the next operator. No operator at all defaults to OR (optional) — this deliberately matches Phase 1 behavior, where every query term was implicitly OR'd together.

**Phase 3 defect:** because the default mode is OR and it only changes _forward_ from an operator's position, a word appearing _before_ the first operator is always captured under the default OR mode — even if that first operator turns out to be AND. `"python AND kubernetes"` therefore parses as `optional: ["python"], required: ["kubernetes"]` instead of both being required. Root-caused via live testing (see Complete Request Flow, Example 2) and fixed by retroactively promoting already-collected optional terms into required the moment the first operator is confirmed to be AND. Full before/after code and reasoning in Design Decisions §22.

**Phrase extraction (unchanged):** a leading `NOT` before a quoted phrase routes it to `excluded_phrases`; otherwise it goes to `phrases`. Phrases are always effectively "required-like" or "excluded" in this grammar — there's no notion of an _optional_ phrase, which is consistent with (and part of the reasoning behind) the fix above only needing to touch bare-word handling, not phrase handling.

## validation.py _(unchanged since Phase 2, extended by `main.py` for pagination)_

Protects the search engine from malformed inputs: empty, whitespace-only, punctuation-only, control-character-containing, or excessively long queries. Rejecting bad input early reduces computation, improves reliability, and prevents unexpected behavior downstream. Phase 3 added sibling checks directly in `main.py` for `page`/`page_size`, following the same "fail fast, before real work" philosophy rather than folding pagination validation into this file (pagination isn't about the _query_, so it didn't naturally belong in `validate_query()`).

## schemas.py — new in Phase 4

Pydantic response models for every endpoint, replacing hand-shaped dicts with a declared contract FastAPI can validate against and document automatically.

**Models:** `SearchResultItem` (one result row), `SearchResponse` (the normal paginated `/search` success shape), `NoResultsResponse` (covers both of `/search`'s zero-result branches — unknown-word rejection and no-searchable-terms rejection — via optional/defaulted fields), `SuggestResponse`, `HealthResponse`, `ErrorResponse`.

**Why one `NoResultsResponse` for two different branches instead of two separate models?** Both branches share the same minimal shape (`query`, `message`, optionally `unknown_words`, always an empty `results`) — introducing a second near-identical model would be duplication without a corresponding gain in clarity.

**A deliberate, accepted behavior change:** fields like `did_you_mean` and `unknown_words` now always appear in the JSON response (as `null`/`[]` when not applicable) instead of being omitted entirely, which is what the pre-Phase-4 hand-built dicts did. This is the standard tradeoff of moving from free-form dicts to a fixed schema, not an oversight.

## cache.py — new in Phase 4

An in-memory LRU cache for `/search` results, wrapping `cachetools.LRUCache` (default capacity 256 entries).

**Class:** `SearchResultCache` — `get(query)`/`set(query, value)`, both normalizing the key via `.strip().lower()` so trivial whitespace/case differences still hit the same entry.

**What's cached:** the full ranked-and-deduplicated result list, *before* pagination — not a per-`(query, page, page_size)` entry. This means page 2 of an already-seen query is still a cache hit; caching per-page instead would have made every page after the first a guaranteed miss for no benefit.

**What's deliberately never cached:** the unknown-word and no-searchable-terms zero-result branches in `main.py` — those are cheap early exits, and caching a "no results" verdict indefinitely felt like the wrong default for something this cheap to recompute. See Design Decisions §30.

**Why no TTL / invalidation logic?** The corpus is static within a server's lifetime (same assumption Phase 3's offset-pagination decision relies on) — there's no scenario in the current system where a cached result set could become stale during a single run. This would need to change if the corpus ever supported live updates without a restart (see Future Roadmap).

## logging_config.py — new in Phase 4

Structured (JSON) request logging, configured once at import time.

**Functions/classes:** `JSONFormatter` (a `logging.Formatter` subclass emitting one JSON object per line: timestamp, level, message, plus any structured fields passed in), `get_logger()` (guards against duplicate handlers if called more than once), `log_request(logger, **fields)` — the single call site every endpoint uses.

**Why JSON from day one, instead of adding structure later?** Directly stated in the Phase 4 planning notes: this data is meant to feed Phase 5's evaluation and A/B analysis work. Retrofitting structure onto plain-text log lines later would mean re-processing or discarding everything logged before the format changed; emitting JSON from the first request avoids that entirely.

**Why a custom formatter instead of a `python-json-logger`-style dependency?** The formatter needed is a few lines of stdlib `logging` — pulling in a new dependency for something this small would be adding a library for the sake of it, not because the standard library couldn't do the job.

## suggest.py — new in Phase 4

Prefix-based autocomplete over the corpus vocabulary, built once at startup.

**Functions:**

- `build_suggest_index(docs)` — walks the corpus once with `basic_tokenize()` (unstemmed — deliberately *not* the `tokenize()` pipeline the search index uses), building a `{term: frequency}` table, then returns `(sorted_terms, frequencies)`.
- `get_suggestions(prefix, sorted_terms, frequencies, limit=10)` — `bisect.bisect_left` jumps directly to the first term at or after `prefix` in sorted order, then walks forward only while `term.startswith(prefix)` still holds, stopping the instant it doesn't (sorted order guarantees no later term could match either). Matches are then ranked by frequency (descending), with alphabetical order as a deterministic tiebreaker.

**Why unstemmed terms, when the rest of the system stems everything?** A stemmed form like "engin" (from "engineering") is exactly right for *matching* inside the search index, but useless to *show a user* as a suggested completion. Autocomplete needs to display real, readable word forms.

**Why binary search over a sorted list instead of a trie?** At this corpus's vocabulary size (order of a few hundred distinct terms), a sorted-list-plus-`bisect` prefix scan and a trie have effectively the same practical lookup cost, but the sorted list needed zero new data-structure code. A trie becomes worth the added complexity once vocabulary size or the fraction of a request spent in this lookup actually shows up as a bottleneck — see Scalability.

## persistence.py — new in Phase 4

Saves and loads the built index to/from disk, so a server restart can reuse it instead of rebuilding from `corpus.json` every time. The Python counterpart to `index.cpp`'s `saveToDisk()`/`loadFromDisk()`.

**Functions:**

- `save_index(cache_path, corpus_path, inverted_index, doc_lengths, avg_doc_length, total_docs_count)` — `pickle.dump`s a payload containing all four index values plus a magic marker, a version number, and `corpus_path`'s file-modification time at the moment of writing.
- `load_index(cache_path, corpus_path)` — returns `None` (triggering a fresh rebuild) if the cache file doesn't exist, if its magic/version don't match, or if `corpus_path`'s *current* mtime doesn't match the mtime recorded at save time; otherwise returns the four cached values.

**Why `pickle` instead of porting `index.cpp`'s hand-rolled binary format (magic bytes, offset table, varint-encoded position gaps)?** That format exists in the C++ source because it's writing raw struct bytes to disk itself and has to manage its own layout. `pickle` already serializes the same logical Python objects (dicts, floats, ints) without needing a custom byte layout — reimplementing the C++ approach in Python would be solving a problem Python's standard library already solves.

**What *was* deliberately carried over from the C++ design:** the magic-marker-plus-version-field idea (so a leftover cache file from an incompatible earlier version is rejected outright rather than half-loaded), and — something `index.cpp` itself does *not* do — a staleness check against the source corpus, added specifically so editing `corpus.json` and restarting can never silently serve an out-of-date index.

**Verified behavior (not just read from the code):** three consecutive server startups were run by hand — first with no cache file (rebuilt, cache written), second with the cache present (loaded from cache, confirmed via a startup log line), third after `touch`-ing `corpus.json` to simulate an edit (correctly detected the mtime mismatch and rebuilt rather than serving the stale cache).

## main.py — substantially extended in Phase 3, again in Phase 4, and again in Phase 5

Coordinates the entire system. Intentionally thin.

**Responsibilities:**

- startup: load corpus, load-or-build the positional index (Phase 4 — via `persistence.py`'s cache check), build the link graph, compute + normalize PageRank, build the spelling dictionary, build the autocomplete index (Phase 4), construct the repeated-query cache (Phase 4), load the semantic model + load-or-build document embeddings (Phase 5 — via `semantic.py`'s own cache check)
- receive HTTP requests across three endpoints: `/search` (now with an optional `rerank` param, Phase 5), `/suggest` (Phase 4), `/health` (Phase 4)
- enforce rate limiting (Phase 4) and catch unhandled exceptions globally (Phase 4) before/around endpoint logic
- for `/search`: check the result cache (keyed on query + rerank flag, Phase 5), then (on a miss) call pipeline modules in order: validate → spellcheck → parse → retrieve → score → sort → **semantic re-rank (Phase 5, optional)** → cache-store → **snippet (Phase 4.5 — moved here, after pagination)** → dedup → paginate
- log a structured line for every `/search` request, now including the `rerank` flag (Phase 5)
- generate the JSON response using the Phase 4 Pydantic response models, including pagination metadata

**Phase 4.5 correction worth calling out:** the pipeline order above is not what Phase 4 originally shipped. Snippet generation used to run immediately after sorting, before dedup and pagination — for every ranked candidate, not just the page being returned. Moving it to run after pagination (inside `_build_search_response()`) was the single biggest latency fix made after scaling the corpus to 1,000 documents — see `snippets.py`'s entry above for the measured numbers.

**Phase 5 addition — `unknown_words` rejection is now conditional on `rerank`:** an unrecognized word is a dead end for BM25 (nothing to lexically match), but not for semantic re-ranking, which works on meaning rather than dictionary membership. The early-rejection branch that used to fire unconditionally on any unknown word now only fires when `rerank=False`.

**Why thin controllers?** Business logic belongs in modules, not inside API endpoints. Benefits: easier testing, easier maintenance, reusable modules. This property held as the pipeline grew from 6 steps (Phase 2) to 9 (Phase 3) to effectively 11 (Phase 4, counting the cache check/store as pipeline steps) — every new step is a single delegated function call, not inline logic. The one exception worth naming: `_build_search_response()` (pagination-slicing + response construction) lives directly in `main.py` rather than a dedicated module, since both the cache-hit and cache-miss code paths need to share it and it's a handful of lines, not a concern substantial enough to justify its own file.

```jsx
                             main.py
                                │
      ┌─────────────┬──────────┼──────────┬─────────────┐
      ▼             ▼          ▼          ▼             ▼
validation.py  spellcheck.py  query_parser.py  authority.py (startup only)
                                    │
                                    ▼
                                index.py
                                    │
                                    ▼
                                ranking.py
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                    snippets.py          dedup.py
                          │                   │
                          └─────────┬─────────┘
                                    ▼
                              JSON Response
```

No component communicates directly with unrelated modules. Dependencies always move in one direction. This minimizes coupling — and made it possible to add four new Phase 3 modules (`authority.py`, `snippets.py`, `dedup.py`, plus the BM25 addition to `index.py`) without modifying `tokenizer.py`, `validation.py`, `spellcheck.py`, or the boolean-retrieval logic in `index.py` at all. The same held for Phase 4: five new modules (`schemas.py`, `cache.py`, `logging_config.py`, `suggest.py`, `persistence.py`) plus a from-scratch `bm25.py` were added — and `rank_bm25` removed — without modifying `tokenizer.py`, `query_parser.py`, `validation.py`, `spellcheck.py`, `authority.py`, `snippets.py`, or `dedup.py` at all. `ranking.py` and `index.py` did change, but only at the seam where they previously touched the `rank_bm25` library (see their entries above) — the boolean-retrieval, phrase-matching, and score-fusion logic around that seam is untouched. Phase 5 added one new module (`semantic.py`) touching only `main.py`'s wiring.

## Supporting scripts (not part of the live API)

### scripts/generate_corpus.py — new in Phase 4.5

Generates `data/corpus.json`: template-based, not hand-written, since 1,000 unique 300-500 word documents isn't practical to author by hand. Ten domains (tech, healthcare, finance, education, sports, entertainment, food, travel, science/environment, law/government), 100 documents each. Each document's content is assembled from ~14 domain-agnostic master sentence templates, filled from a per-domain phrase bank (subject/focus/activity/skill/benefit/challenge/development/importance/outcome/trend/closing — ~5 options each), looped until word count lands in `[300, 500]` (measured actual distribution: min 473, max 500, mean 488.9 — clustered toward the top of the range, not uniformly spread, a byproduct of the stop condition rather than a deliberate design goal). Five duplicate pairs are deliberately injected (same title + content, different id/location) so `dedup_results()` continues to have real exact-duplicates to catch, mirroring what the original 100-doc corpus had by chance (docs 49/79).

**Known consequence of a narrow, fixed phrase bank:** common English words that simply never appear in any template (e.g. "companies," "power," "help," "sick," "kids") are absent from the resulting corpus vocabulary entirely — which is what exposed the spellcheck-corruption bug documented in `semantic.py`'s entry above. Worth knowing before reading too much into any single query's evaluation result.

### scripts/evaluate.py — new in Phase 5

The evaluation framework: computes Precision@10, MRR, and nDCG@10 for BM25-only vs. BM25+semantic re-ranking, against a 20-query judgment set (10 lexical, 10 semantic-paraphrase).

**Ground-truth methodology, stated plainly:** because the corpus is synthetically generated by the script above, relevance is determined *programmatically* rather than by independent human judgment — lexical queries are judged against every document whose title contains the exact topic phrase named; semantic queries are judged against every document in the target domain's `category` field. This is honestly reproducible-by-construction, not independent human relevance judgment, and the report built from it says so explicitly rather than presenting the numbers as more rigorous than they are.

**Both search modes run through logic mirroring `main.py`'s actual `/search` code paths** (`search_bm25_only()` and `search_bm25_plus_semantic()`), including the conditional unknown-word rejection — not an idealized bypass — so results reflect what a real client gets from each mode.

**Measured results (20-query mean):**

| | Precision@10 | MRR | nDCG@10 |
|---|---|---|---|
| BM25-only (overall) | 0.555 | 0.687 | 0.635 |
| BM25+semantic (overall) | 0.625 | 0.782 | 0.708 |
| BM25-only (lexical subset) | 0.510 | 0.770 | 0.670 |
| BM25+semantic (lexical subset) | 0.520 | 0.825 | 0.691 |
| BM25-only (semantic subset) | 0.600 | 0.604 | 0.600 |
| BM25+semantic (semantic subset) | 0.730 | 0.740 | 0.725 |

The lexical subset barely moving (a control group — BM25 already handles exact-phrase queries well) while the semantic subset improves substantially (+21.7% P@10, +22.5% MRR, +20.8% nDCG@10) is the actual "does this technique work" evidence, not the overall average by itself. Full per-query results, including one query that regressed under re-ranking and one that scored 0.0 under both modes, are in `data/evaluation_results.json` and the published evaluation report.

---

# ALGORITHMS

## Tokenization Algorithm _(unchanged)_

```jsx
Raw Text
↓ lowercase
↓ remove punctuation
↓ split into tokens
↓ remove stopwords
↓ stem words
↓ Return tokens
```

`"The developers were Running."` → `["develop", "run"]`. Without normalization, "Run," "Running," and "Runs" would all be different terms.

## Positional Inverted Index Construction _(unchanged)_

For every document, for every token, store `term → document → position`.

`machine → Doc 5 → [1]`, `learning → Doc 5 → [2]` (if "machine learning" is the first two words of doc 5's normalized token stream).

**Why better than sequential scan?** Sequential scan: search = read every document, O(N). Index: search = jump to posting list, O(df) where df (document frequency) is typically ≪ N.

## Boolean Retrieval Algorithm _(unchanged)_

AND = intersection, OR = union, NOT = difference, all via Python sets.

```jsx
Posting A = {2,4,8}
Posting B = {4,8,10}
AND → {4,8}   (intersection)
OR  → {2,4,8,10}  (union)
```

**Why sets?** Python sets provide efficient union, intersection, and difference — simple to implement, fast in practice.

## Phrase Search Algorithm _(unchanged)_

Phrase "machine learning": `machine → [5]`, `learning → [6]`. Since `6 = 5 + 1`, the phrase is found at position 5. If the offsets aren't consecutive, the phrase is rejected. No need to re-scan the document — the answer comes directly from positional information already in the index.

## BM25 Algorithm _(introduced in Phase 3 via `rank_bm25`; hand-rolled in Phase 4)_

BM25 (Best Matching 25) extends TF-IDF with two refinements: **term-frequency saturation** (a term appearing 20 times shouldn't score 20× higher than appearing once — its contribution saturates) and **document-length normalization** (a long document naturally contains more term occurrences by chance; BM25 discounts for that using the document's length relative to the corpus average).

Conceptually, for a query term _t_ and document _d_:

```
score(t, d) = IDF(t) × ( f(t,d) × (k1 + 1) )
                      ─────────────────────────────────────
                        f(t,d) + k1 × (1 - b + b × |d|/avgdl)
```

where `f(t,d)` is term frequency, `|d|` is document length, `avgdl` is the average document length across the corpus, and `k1`/`b` are tuning constants. A document's total BM25 score is the sum of this term across all query terms.

**Phase 4: `k1`/`b`/`idf` are now `index.cpp`'s values, not `rank_bm25`'s defaults.** `k1=1.2, b=0.75`, and `idf = log((N-df+0.5)/(df+0.5) + 1.0)` — the same "+1" idf variant Lucene/Elasticsearch's default `BM25Similarity` uses, which can never go negative. `rank_bm25` (removed in Phase 4) used a different, also-standard combination: `k1=1.5` and the classic Robertson/Sparck-Jones idf (no "+1", floored at `epsilon × average_idf` when it would otherwise go negative). Two legitimate BM25 variants, not a bug in either — see Design Decisions §29 for the comparison performed before trusting the hand-rolled version.

**Why BM25 over plain TF-IDF?** TF-IDF's raw `tf × idf` grows unboundedly with term frequency and ignores document length. BM25's saturation and length-normalization terms make it a substantially better relevance signal in practice — it's the de facto standard scoring function in classical (non-neural) information retrieval, used by Elasticsearch and Lucene by default.

## PageRank Algorithm _(new in Phase 3)_

Models the corpus as a directed graph (documents = nodes, links = edges) and computes each node's "authority" as the stationary distribution of a random walk that, at each step, follows an outgoing link with probability _d_ (the damping factor, 0.85) or jumps to a uniformly random node with probability `1 - d` (modeling a user who eventually gets bored and starts over).

```
PR(p) = (1 - d)/N + d × Σ [ PR(q) / L(q) ]   for every page q linking to p
```

Computed iteratively (power iteration) until scores converge within a tolerance. `networkx.pagerank()` handles this — including the "dangling node" edge case (a document with zero outlinks, which would otherwise leak rank out of the system).

**Why PageRank here, on a job-postings corpus with no real hyperlinks?** It's a stand-in for a real crawler's link graph (see Design Decisions §19), included specifically so the _ranking fusion architecture_ — combining a relevance signal with an independent authority signal — could be built and tested now, ahead of real crawler data arriving.

## Score Fusion Algorithm _(new in Phase 3)_

```
final_score = w_bm25 × normalize(bm25_raw)   +   w_pagerank × normalize(pagerank_raw)   +   phrase_bonus
```

with `w_bm25 = 0.85`, `w_pagerank = 0.15`. Both raw score sets are min-max normalized to `[0, 1]` _before_ combining — BM25's raw scores can be any real number (occasionally negative, for very common terms — see Limitations), while PageRank's raw scores are tiny fractions that sum to 1 across the whole graph. Combining un-normalized values would let whichever signal happens to have larger raw magnitude dominate, regardless of the intended weights.

## Snippet Generation Algorithm _(new in Phase 3)_

1. Collect every stemmed term worth highlighting (required + optional + all phrase terms).
2. Split the doc's title+content into words, stemming each one via the same `tokenize()` pipeline used at index time.
3. Find the first word whose stem is in the target-term set.
4. Take a window of 12 words on each side.
5. Re-wrap every matched word inside that window in `<mark>` tags.

**Why stem-based matching instead of literal substring search?** Literal substring matching for a query like "engineers" would fail to highlight "Engineer" (singular) in the doc text, even though that's exactly the word that caused the document to match during retrieval. Stem-based matching keeps the highlighting consistent with the actual matching logic.

## Deduplication Algorithm _(new in Phase 3)_

1. Normalize each doc's `title + content` (lowercase, whitespace-collapsed) into a fingerprint string.
2. Walk the already-sorted (best-score-first) result list.
3. Keep a result only if its fingerprint hasn't been seen yet; otherwise discard it.

Because the list is pre-sorted, "first occurrence" is equivalent to "highest-scoring occurrence" — no separate best-of comparison is needed.

## Pagination Algorithm _(new in Phase 3)_

Simple offset-based slicing after sorting and deduplication:

```
start = (page - 1) × page_size
end   = start + page_size
page_results = deduped_results[start:end]
total_pages  = ceil(total_results / page_size)
```

**Why offset-based, not cursor-based?** See Design Decisions §27 — offset pagination is simpler to implement and sufficient for a bounded, in-memory, non-mutating corpus; cursor-based pagination becomes preferable once the underlying data can change between page requests.

## LRU Cache Algorithm _(new in Phase 4)_

Least-Recently-Used eviction: the cache holds at most `maxsize` entries; inserting past that limit evicts whichever entry hasn't been accessed most recently. `cachetools.LRUCache` implements this with an ordered mapping — every `get`/`set` moves that key to the "most recently used" end, so eviction always removes from the opposite end in O(1).

**Why LRU specifically, over a simpler unbounded dict or a random-eviction cache?** An unbounded cache is a memory leak waiting to happen once enough distinct queries have ever been seen; LRU's assumption — that a query seen recently is more likely to be seen again soon than one seen long ago — matches real query traffic (popular/repeated searches) far better than evicting at random.

## Prefix Search Algorithm (Autocomplete) _(new in Phase 4)_

Given a sorted list of terms and a prefix, `bisect.bisect_left` finds the insertion point for `prefix` in **O(log n)** — the first index where a term equal to or greater than `prefix` would sit. Walking forward from there and stopping the instant a term no longer starts with `prefix` costs O(k), where _k_ is the number of matches actually found (bounded further by `limit`).

```
sorted_terms = ["docker", "engineer", "engineering", "kubernetes", "python"]
prefix = "eng"
bisect_left → index 1 ("engineer")
walk forward: "engineer" ✓, "engineering" ✓, "kubernetes" ✗ → stop
matches = ["engineer", "engineering"]
```

**Why this instead of scanning every term and checking `.startswith()`?** A full scan costs O(n) regardless of how few terms actually match; `bisect` skips straight past every term that sorts before the prefix, so cost scales with matches found, not vocabulary size.

## Overall Search Algorithm _(updated for Phase 4)_

```jsx
Receive Query
      │
      ▼
Rate Limit Check (Phase 4)
      │
      ▼
Validate Input (query + pagination)
      │
      ▼
Cache Lookup (Phase 4) ── hit ──▶ Paginate ──▶ Log ──▶ Return JSON
      │
      │ miss
      ▼
Spell Correction
      │
      ▼
Parse Query
      │
      ▼
Retrieve Candidates
      │
      ▼
Score (hand-rolled BM25 + PageRank fusion + phrase bonus)  ◄── Phase 4: BM25 no longer library-based
      │
      ▼
Sort (score desc, doc_id asc)
      │
      ▼
Generate Snippets
      │
      ▼
Deduplicate
      │
      ▼
Cache Store (Phase 4, success path only)
      │
      ▼
Paginate
      │
      ▼
Log Request (Phase 4)
      │
      ▼
Return JSON
```

## Semantic Re-ranking Algorithm _(new in Phase 5)_

Two steps, not one:

```
1. Re-rank: for the top-K (30) BM25-ranked candidates,
   blended_score = 0.5 × normalize(cosine_similarity(query_embedding, doc_embedding))
                 + 0.5 × normalize(BM25 + PageRank score)

2. Augment: compare query_embedding against EVERY document's precomputed
   embedding (one matrix multiply, no re-embedding of documents), pulling in
   up to 15 documents BM25 never retrieved at all -- but ONLY if the query has
   no explicit AND/NOT/phrase constraint an augmented doc can't be checked against.
```

`cosine_similarity` is a plain dot product here, not a full cosine formula, because every embedding is L2-normalized at encode time (`normalize_embeddings=True`) — for unit vectors, dot product and cosine similarity are the same number.

**Why augmentation, when the task was "re-rank the top-K"?** A re-rank-only design can only reorder documents already found. For a paraphrase query sharing zero literal vocabulary with its target documents, BM25's candidate set is empty, so there is nothing to reorder — measured directly: `fighting global warming with clean power` returns zero BM25 candidates (the words "fighting"/"warming" don't exist in this corpus), yet the true top-10 documents by pure embedding similarity are all genuinely about climate/renewable energy (cosine 0.34-0.40, verified against the full corpus). Augmentation is what lets those surface at all.

## Evaluation Metrics _(new in Phase 5)_

Standard information-retrieval metrics, computed in `scripts/evaluate.py` against a judgment set of `(query, relevant_doc_ids)` pairs:

```
Precision@10 = |relevant documents in top 10| / 10

MRR (Mean Reciprocal Rank) = average over queries of 1 / rank_of_first_relevant_result
                             (0 if no relevant result appears at all)

nDCG@10 = DCG@10 / IDCG@10
  where DCG@10 = Σ (1 / log2(i + 2)) for each relevant doc at position i (0-indexed)
  and IDCG@10  = DCG@10 of the ideal ranking (all relevant docs placed first)
```

Binary relevance is used throughout (a document either is or isn't relevant to a query) — no graded relevance scale, since the ground truth itself (title-phrase match or category match) is inherently binary. **Why all three metrics, not just one?** Precision@10 measures raw hit rate but ignores order within the top 10; MRR rewards getting *any* relevant result to the very top but ignores everything after the first hit; nDCG@10 is the only one of the three that rewards getting the *best* ordering across the whole top 10, not just a hit rate or a first-hit position. Reporting all three, not cherry-picking whichever looks best, is what makes the comparison in Executive Summary/Component Documentation trustworthy.

---

# DESIGN DECISIONS

This chapter answers one question: _"Why did you build it this way instead of another way?"_ Decisions 1–16 were made in Phase 1/2; decisions 17 onward were made in Phase 3.

1. **Why Python?** Alternatives: Java, C++, Go. Chosen for development speed, readability, its IR/ML-adjacent ecosystem (NLTK, SymSpell, rank_bm25, networkx all being readily available), and interview friendliness.
2. **Why FastAPI?** Alternatives: Flask, Django, Express.js. Chosen for automatic OpenAPI docs (the `/docs` Swagger UI used throughout manual testing), built-in request validation, async support, and strong performance for a project this size.
3. **Why a JSON corpus?** Alternatives: SQL, MongoDB, CSV. JSON is sufficient while the corpus is small, static, and loaded once at startup; a real database becomes valuable once the corpus needs incremental updates, concurrent writes, or exceeds available memory — see Scalability.
4. **Why an in-memory index?** Alternatives: SQLite, Redis, a disk-based index. Chosen for simplicity and latency at this corpus size; memory becomes the limiting factor at large scale — see Scalability.
5. **Why a positional inverted index (not a simple inverted index, B-tree, trie, or sequential scan)?** Positions specifically enable phrase queries and let term frequency be read directly from the index instead of re-tokenizing documents at ranking time — both used constantly by Phases 2 and 3.
6. **Why store positions (not just doc IDs)?** Enables phrase search now, and near/proximity search and BM25F-style field weighting later, without changing the index's fundamental shape.
7. **Why Snowball stemmer?** See `tokenizer.py` in Component Documentation — best balance of speed and accuracy among Snowball, Porter, and WordNet lemmatization for this project's scale.
8. **Why stopword removal?** Smaller index, faster retrieval. Tradeoff: queries that are _entirely_ stopwords, or where a stopword is semantically load-bearing (e.g. band names like "The Who," or "To Be or Not to Be"), lose meaning after removal. Accepted for a technical-job-postings corpus where this scenario essentially never arises.
9. **Why SymSpell (over Norvig's algorithm, a BK-tree, a trie, or naive Levenshtein search)?** SymSpell shifts nearly all the work to a one-time preprocessing step (generating delete-variants of every dictionary word), making query-time lookup much faster — well suited to an interactive search system where lookup latency is user-visible.
10. **Why a corpus-derived dictionary instead of a general English dictionary?** A general dictionary would flag "TensorFlow," "Kubernetes," or company names as misspelled. A corpus-derived dictionary recognizes anything that actually appears in the indexed documents, at the cost of not catching genuinely novel typos of words the corpus happens not to contain.
11. **Why TF-IDF first, then BM25?** TF-IDF was the right choice for a Phase 1/2 MVP — simple to implement and reason about while the rest of the pipeline (parsing, retrieval, boolean logic) was still being built. BM25 was deferred to Phase 3 specifically so ranking quality improvements could be evaluated in isolation, once the surrounding pipeline was stable. See #17–18 below for the BM25-specific decision.
12. **Why separate retrieval and ranking?** Many first attempts at a search engine retrieve-and-score in one pass. This project deliberately keeps them separate: `retrieve_candidates()` only ever answers "which documents qualify," and `score_documents()`/`ranking.py` only ever answers "in what order." This is what allowed TF-IDF → BM25 and the later addition of PageRank fusion to happen entirely inside `ranking.py`, without touching retrieval logic at all — a concrete payoff of the separation, not just a theoretical one.
13. **Why a modular architecture (not one giant file)?** Testing, maintainability, extensibility — demonstrated concretely in Phase 3, where four new/rewritten files (`authority.py`, `snippets.py`, `dedup.py`, `ranking.py`) were added or changed without modifying `tokenizer.py`, `validation.py`, `spellcheck.py`, or the boolean-retrieval half of `index.py` at all.
14. **Why startup initialization (build once, reuse forever) instead of building the index per-request?** A very important systems decision that only became more important in Phase 3: the BM25 model and PageRank computation are each nontrivial to build, and both are now startup-only costs, never per-request costs.
15. **Why a REST API (not a CLI, desktop app, socket server, or GraphQL)?** REST/JSON is simple to test manually (curl, Swagger UI, browser address bar), simple to consume from any future frontend, and is the expected interface for a backend-engineering-focused project.
16. **Why build this from scratch instead of using Elasticsearch?** Educational value, transparency, and control — the entire point of the project is understanding _why_ each piece works, not just that it works. (Phase 3's two library dependencies, `rank_bm25` and `networkx`, are a deliberate, scoped exception — see #17–18.)

---

**Phase 3 decisions:**

1. **Why `rank_bm25` for BM25 instead of hand-rolling it immediately?**
   - **Why:** Get a correct, well-tested BM25 implementation working end-to-end quickly, to validate the rest of the Phase 3 pipeline (score fusion, snippets, dedup, pagination) against a trustworthy relevance signal before investing in a from-scratch version.
   - **Alternate:** Implement BM25 directly on top of the existing positional inverted index (`term_frequency_in_doc`, `doc_ids_for_term`, `doc_lengths` — all of which already exist and were retained specifically for this).
   - **Why (partially) rejected — deferred, not abandoned:** The hand-rolled version is explicitly the better long-term choice (it would use the existing index instead of `rank_bm25`'s whole-corpus rescan — see Complexity Analysis — and makes a substantially stronger resume/interview story than "used a library"). It's deferred to a follow-up pass, not skipped.
2. **Why `networkx` (with `scipy` as a transitive dependency) for PageRank instead of hand-rolling power iteration?**
   - **Why:** `networkx.pagerank()` is a correct, well-tested reference implementation, letting the score-fusion architecture (normalization, weighting, combination) be built and verified against trustworthy PageRank output immediately.
   - **Alternate:** Hand-rolled power iteration in plain Python/dicts — entirely feasible at this graph size (100 nodes) with no library needed at all.
   - **Why accepted (for now):** Same MVP-first reasoning as the BM25 decision. Unlike BM25, there was no strong resume-value argument pushing toward a custom PageRank implementation specifically, so this one may reasonably stay library-based longer.
   - **Incident note:** `networkx.pagerank()` silently depends on `scipy` internally, which wasn't installed and wasn't listed as a direct `networkx` dependency by pip. This caused the server to crash at startup on first run (`ModuleNotFoundError: No module named 'scipy'`), diagnosed from the traceback, fixed by installing `scipy` and adding it to `requirements.txt`. Worth remembering: a library's _declared_ dependencies and its _actual_ runtime dependencies aren't always the same set.
3. **Why a synthetic, seeded-random link graph instead of waiting for a real crawler?**
   - **Why:** The Phase 3 spec explicitly calls for designing the PageRank fusion as pluggable specifically so a delayed or missing crawler component doesn't block the rest of the phase. Since no real crawler exists yet, generating a synthetic graph was the only way to actually exercise and test that fusion step now.
   - **Alternate:** Skip the PageRank sub-task entirely until real link data exists.
   - **Why rejected:** Would leave the fusion architecture (normalization, weighting, the `authority.py` module boundary) completely untested. A seeded random graph (fixed seed 42, 2–4 outlinks per doc) is reproducible, explainable in a writeup, and gives PageRank genuine variance to differentiate on (in-degree observed ranging 1–7 across the corpus) — while being explicitly documented as fabricated data, not real authority (see Limitations).
4. **Why min-max normalize both BM25 and PageRank before combining, instead of combining raw scores?**
   - **Why:** BM25's raw scores are unbounded (and occasionally negative, for very common terms in a small/templated corpus). PageRank's raw scores are tiny fractions summing to 1 across the whole graph (~1/100 on average here). Combining these directly would let whichever signal has larger raw magnitude dominate the final score regardless of the intended 0.85/0.15 weighting.
   - **Alternate:** Z-score normalization (mean/standard-deviation based) instead of min-max.
   - **Why rejected:** Min-max guarantees both signals land in exactly `[0, 1]`, which makes the weighted-sum interpretation ("85% relevance, 15% authority") literal and easy to reason about. Z-score doesn't bound the output range, reintroducing the same magnitude problem it was meant to solve.
5. **Why weight BM25 at 0.85 and PageRank at 0.15 specifically?**
   - **Why:** Relevance should dominate — a highly authoritative but off-topic document shouldn't outrank a directly relevant one. PageRank is meant to act as a tie-breaking boost among already-relevant candidates, not an independent ranking signal.
   - **Alternate:** A 50/50 split, or a multiplicative combination instead of a weighted sum.
   - **Why rejected:** An even split would let link authority meaningfully override relevance, which doesn't match how job-search relevance should behave. These specific weights are acknowledged as arbitrary starting points (flagged directly in the `ranking.py` comments as tunable), not the result of a formal evaluation — a genuine evaluation would require the labeled relevance judgments this project doesn't yet have (see Future Roadmap).
6. **Why does `score_documents()` score the entire candidate set in one call instead of one document at a time (Phase 2's pattern)?**
   - **Why:** `rank_bm25.get_scores()` always rescans the entire corpus per call, regardless of how many documents are actually needed. Calling it inside a per-candidate loop would mean re-scoring the whole corpus once _per candidate_ — wasteful even at 100 documents, strictly worse as the corpus grows.
   - **Alternate:** Keep Phase 2's one-document-at-a-time `score_document()` signature, just swap its internals to call BM25.
   - **Why rejected:** Would silently turn every query into an O(candidates × corpus_size) operation instead of O(corpus_size). The signature change was deliberate specifically to prevent this.
7. **Why does phrase inclusion remain a scoring boost rather than a candidate filter, even after being identified as a gap?**
   - **Why:** This is a genuine, explicit, user-confirmed decision to defer rather than an oversight being ignored. Fixing it properly requires deciding phrase semantics when combined with required/optional/excluded terms in the same query — a design question, not just a one-line patch.
   - **Alternate:** Immediately change `retrieve_candidates()` so any included phrase also narrows the candidate set (treating a phrase as an implicit AND-requirement).
   - **Why deferred, not implemented:** Explicitly deferred by project decision during Phase 3, to be revisited alongside the hand-rolled BM25 work. Documented clearly here and in Limitations so it isn't mistaken for unnoticed behavior.
8. **Why stem-based (not literal substring) matching for snippet highlighting?**
   - **Why:** A query for "engineers" should highlight "Engineer" in the doc text — the same word that caused the document to match during retrieval. Literal substring matching would miss this entirely.
   - **Alternate:** Literal case-insensitive substring search for each raw query word.
   - **Why rejected:** Would produce highlighting inconsistent with the actual matching logic (which is stem-based throughout the rest of the system), confusing a user who sees a document ranked highly for "engineers" with no visible highlight anywhere.
9. **Why `<mark>` HTML tags instead of markdown-style `**bold**` or custom delimiters?**
   - **Why:** `<mark>` is the standard HTML element for "highlighted search text" — a future frontend renders it correctly with zero extra CSS.
   - **Alternate:** `**term**` (markdown-style) or custom delimiters like `[[term]]`.
   - **Why rejected:** Markdown bold has no special meaning to a browser and would need frontend-side parsing; custom delimiters would need an entirely custom rendering convention documented and maintained separately. `<mark>` needs neither.
10. **Why exact-fingerprint deduplication instead of fuzzy/near-duplicate detection?**
    - **Why:** The corpus's actual duplicates (verified: doc 49 / doc 79) are byte-for-byte identical in title+content, differing only in an unindexed field (`location`). Exact-fingerprint matching, after whitespace/case normalization, catches every real case in this corpus at negligible cost.
    - **Alternate:** Fuzzy similarity (e.g. shingling + Jaccard similarity, or embedding-based cosine similarity) to catch near-duplicates that differ by a few words.
    - **Why rejected (for now):** No near-duplicate (as opposed to exact-duplicate) cases currently exist in the corpus to justify the added complexity and computational cost. Flagged as a Future Roadmap item for when the corpus grows or comes from a real (messier) crawl.
11. **Why offset-based pagination (`page`/`page_size`) instead of cursor-based pagination?**
    - **Why:** The corpus is static within a server's lifetime — the underlying result set for a given query never changes between page requests, so offset-based slicing (`results[start:end]`) is simple, correct, and has no edge cases to worry about.
    - **Alternate:** Cursor-based pagination (opaque tokens referencing a specific position, robust to underlying data changing between requests).
    - **Why rejected (for now):** Cursor-based pagination solves a problem this system doesn't have yet — a corpus that mutates between a user's page-1 and page-2 requests. Worth revisiting once the corpus supports live updates (see Future Roadmap).
12. **Why explicit `(-score, doc_id)` tie-breaking instead of relying on default sort/set ordering?**
    - **Why:** PageRank's normalization can produce identical or near-identical scores for multiple documents, making score ties more likely than they were under pure TF-IDF. Python's `set` iteration order for integers isn't something a user-visible ranking should silently depend on.
    - **Alternate:** Sort by score only, and accept whatever order ties happen to come out in.
    - **Why rejected:** Would make identical queries potentially return differently-ordered results across requests or across Python versions/runs — violating the Determinism non-functional requirement introduced in Phase 3.
13. **Why keep `build_doc_lengths()`/`doc_lengths` in `main.py` even though the current (library-based) BM25 scoring doesn't use it?**
    - **Why:** It's exactly the data a hand-rolled BM25 (the explicitly planned Phase 3 follow-up) will need — document length relative to corpus-average length is a core BM25 input.
    - **Alternate:** Remove it now as dead code, since nothing currently reads it.
    - **Why rejected:** Removing it now would mean recomputing/re-adding it later for the planned custom BM25 work — pure churn for a function that costs almost nothing to keep computing at startup.
14. **The AND-parsing bug: why a scoped, minimal fix instead of a full boolean-grammar rewrite (with real operator precedence and parentheses)?**
    - **Why:** The specific failure mode identified — a bare word appearing _before_ the first operator in a query — has a narrow, well-defined fix: retroactively promote already-collected optional terms into required the moment the first operator is confirmed to be `AND`. This directly matches the parser's existing documented intent ("AND/NOT are additive narrowing on top of the default OR"), which the union logic in `retrieve_candidates()` already correctly implements — the bug was entirely in which bucket a term landed in, not in how the buckets get combined.
    - **Alternate:** Rewrite the parser with real operator precedence and explicit clause boundaries (parentheses), so arbitrarily mixed `AND`/`OR`/`NOT` queries have unambiguous, user-controllable meaning.
    - **Why rejected (for now):** The project's query grammar was already explicitly scoped to exclude parentheses/precedence from the start (documented directly in `query_parser.py`'s own comments) — a full rewrite is a disproportionate response to a bug whose actual cause was much narrower. The scoped fix was verified correct against every test case that matters for this grammar (`python AND kubernetes`, `engineer AND python NOT google`, `docker OR linux`, `python NOT kubernetes`, `docker AND linux AND python`) without touching the boolean-grammar scope decision at all. A full-precedence grammar remains a legitimate Future Roadmap item, not a rejected idea.

---

**Phase 4 decisions:**

28. **Why NOT port `index.cpp`'s flat `termDictionary`/`globalPostingPool`/`globalPositionsPool` array layout, given the instruction to port "as much as we can"?**
    - **Why:** That layout exists to buy cache-locality and avoid per-term dict overhead at large scale in C++ — a real win at millions of documents. At this corpus's 100 documents, it buys nothing measurable.
    - **Alternate:** Restructure `app/index.py`'s positional index into the same flat-array shape as `index.cpp`.
    - **Why rejected:** The cost is real and immediate — it would mean rewriting `retrieve_candidates()`, `phrase_match()`, and every boolean-retrieval set operation to work against array offsets instead of dict lookups — while the benefit is entirely hypothetical at the current corpus size. Flagged instead as a Scalability item, to revisit only if corpus size actually becomes the bottleneck it's designed to solve.
29. **Why follow `index.cpp`'s exact BM25 formula (`k1=1.2`, the "+1" idf variant) instead of reverse-engineering `rank_bm25`'s defaults to keep raw scores numerically unchanged?**
    - **Why:** The explicit goal of this exercise was porting the teammate's C++ reference implementation — and it turns out to be a legitimate, real-world formula in its own right (identical to Lucene/Elasticsearch's default `BM25Similarity`), not an arbitrary choice needing justification against the library it replaces.
    - **Alternate:** Match `rank_bm25`'s internals (`k1=1.5`, classic Robertson/Sparck-Jones idf with an epsilon floor) so BM25 scores stay numerically identical across the swap.
    - **Why rejected:** Would mean not actually porting `index.cpp`'s approach, defeating the point of the exercise. It's also unnecessary: `ranking.py` min-max normalizes BM25 scores before combining them with PageRank, so raw-score continuity was never a real requirement — only ranking *order* needed to stay sane, which was directly verified against `rank_bm25` on multiple real queries before this was wired in (see `bm25.py` in Component Documentation).
30. **Why cache only the success path of `/search`, never the unknown-word or no-searchable-terms branches?**
    - **Why:** Those branches are already cheap early exits — no retrieval, no scoring, no snippet generation. Caching a "no results" verdict indefinitely felt like the wrong default for something this cheap to recompute, especially with no cache-invalidation mechanism if the corpus or spelling dictionary ever changed within a server's lifetime.
    - **Alternate:** Cache every `/search` branch uniformly, for implementation simplicity.
    - **Why rejected:** The cost/benefit is asymmetric — caching the expensive success path saves real, measurable work (verified: 7.91ms → 0.02ms on a cache hit); caching a cheap rejection saves almost nothing while adding a class of "stale rejection" bugs to reason about for no real gain.
31. **Why key the cache on the raw query string alone, not `(query, page, page_size)`?**
    - **Why:** Retrieval, scoring, snippet generation, and deduplication cost the same regardless of which page is requested — only the final slice differs. A page-scoped cache key would make every page after the first a guaranteed miss for a query that's actually already been fully computed.
    - **Alternate:** Cache key = the full `(q, page, page_size)` tuple.
    - **Why rejected:** Strictly worse hit rate for zero benefit — slicing the already-cached full result list per page is nearly free, so there's no cost to sharing one cache entry across every page of the same query.
32. **Why an in-memory LRU cache (`cachetools`) instead of Redis?**
    - **Why:** No external infrastructure exists anywhere in this project yet. An in-memory cache keeps the whole phase runnable with a `pip install`, matching the same MVP-first reasoning Phase 3 used for `rank_bm25`/`networkx` (Design Decisions §17-18): get the architecture right with the simplest correct tool, before reaching for infrastructure the project doesn't need yet.
    - **Alternate:** A Redis-backed cache.
    - **Why rejected (for now):** Redis's actual advantage — a cache *shared* across multiple server processes/replicas — doesn't apply yet, since the system runs as a single process. It becomes the right choice once horizontal scaling (see Scalability) is actually implemented, not before. Flagged in Future Roadmap.
33. **Why `slowapi` for rate limiting instead of hand-rolling a token-bucket limiter?**
    - **Why:** Rate limiting is infrastructure, not an information-retrieval concept core to this project's educational goals — unlike BM25 or PageRank, which were deliberately taken through a library-first-then-hand-rolled (or library-first, in PageRank's case) progression specifically *because* they're the concepts this project exists to teach.
    - **Alternate:** A hand-rolled sliding-window or token-bucket counter keyed by client IP.
    - **Why rejected:** No resume/interview-value or pipeline-architecture argument pushes toward a custom implementation here the way it did for BM25 (Design Decisions §17). `slowapi`'s default in-memory storage already matches this project's "no external infra yet" constraint, same as the cache decision above.
34. **Why `pickle` for index persistence instead of porting `index.cpp`'s hand-rolled binary format (magic bytes, offset table, varint-encoded position gaps), and why add a corpus-staleness check `index.cpp` itself doesn't have?**
    - **Why:** The C++ binary format exists because that code is writing raw struct bytes to disk itself and has to manage its own layout — `pickle` already serializes the same logical Python objects (dicts, floats, ints) without needing one. Separately: without a staleness check, editing `corpus.json` and restarting the server would silently serve an index built from the *old* corpus, with no error — a real correctness gap, even at this project's scale.
    - **Alternate:** Port the exact byte-level format from `index.cpp`, and skip staleness checking to match the C++ source exactly (magic bytes + version only, which is all it does).
    - **Why rejected:** Reimplementing a custom binary layout in Python would be solving a problem the standard library already solves, for no correctness or performance benefit at this scale. Skipping the staleness check would be faithfully copying a gap in the reference implementation rather than an intentional design choice — `index.cpp` most likely never needed one because its own workflow rebuilds explicitly rather than running as a long-lived server reloading between corpus edits, which is exactly this project's actual situation. What *was* kept from the C++ design: the magic-marker-plus-version-field idea, so an incompatible leftover cache file is rejected outright.
35. **Why merge `build_inverted_index()` and `build_doc_lengths()` into one `build_index()` pass instead of adding `avg_doc_length`/`total_docs_count` as a third, separate function?**
    - **Why:** The corpus was already being tokenized independently by both of those two functions, plus a third time by the now-removed `build_bm25_index()` — three full-corpus tokenization passes for data cheapest to compute together in one loop. This is precisely the inefficiency `index.cpp`'s single-loop `InvertedIndex::build()` was designed to avoid.
    - **Alternate:** Add a fourth, still-separate `compute_avg_doc_length(docs)` function alongside the existing two.
    - **Why rejected:** Would be pure waste for no benefit — `doc_lengths` and `avg_doc_length` are trivially derived from data already being computed inside the same per-document loop the positional index needs anyway.

---

**Phase 4.5 / Phase 5 decisions:**

36. **Why generate a synthetic 1,000-doc corpus instead of waiting for a real crawler?**
    - **Why:** Phase 3's synthetic link graph precedent already established this pattern — build and test the architecture now, swap in real data later. A larger, multi-domain corpus was the only way to actually expose scale-dependent bugs (the snippet bottleneck, the phrase-filter gap) before they hit production, and to give semantic re-ranking a corpus diverse enough to demonstrate a lexical/semantic gap at all.
    - **Alternate:** Wait for a real crawler and evaluate against real data from the start.
    - **Why rejected (for now):** Same reasoning as Phase 3's synthetic link graph — a delayed dependency shouldn't block testing the parts of the system that don't need it to be real, only large and structurally realistic.
37. **Why fix the phrase-filter and snippet bugs now instead of deferring them again, as Phase 3 explicitly did?**
    - **Why:** Both were deferred in Phase 3 as low-cost-at-100-documents tradeoffs. Scaling the corpus 10× turned "low cost" into a measured, user-visible problem (995/1000 results for a specific phrase; 204ms per query dominated by re-tokenization) — the deferral was correct given the information available in Phase 3, and no longer correct given the information available in Phase 4.5.
    - **Alternate:** Continue deferring both to a dedicated "Phase 6 bug-fix pass."
    - **Why rejected:** Both fixes were small, well-isolated, and directly unblocked meaningful Phase 5 evaluation (a phrase-search feature returning literally the wrong answer, and 200ms+ query latency, would have undermined confidence in the evaluation framework built on top of them).
38. **Why blend semantic and BM25 scores 50/50 instead of a different weight, or a pure semantic re-rank?**
    - **Why:** Symmetric with Phase 3's BM25/PageRank fusion in spirit (a weighted blend of a primary and a secondary signal) but without a principled reason to weight one signal over the other here, unlike BM25/PageRank's deliberate 0.85/0.15 (relevance should dominate authority). Absent labeled preference data indicating which signal should dominate, 50/50 is the least arbitrary starting point.
    - **Alternate:** Weight BM25 more heavily (treat semantic purely as a tie-breaker), or replace BM25 ranking entirely within the re-ranked group.
    - **Why rejected (for now):** No evaluation data yet justifies a different split — see Future Roadmap for re-tuning this once more judgment data exists, the same status Phase 3 gave its own 0.85/0.15 weights.
39. **Why is the evaluation's ground truth "programmatically derived from generation metadata" instead of independent human judgment?**
    - **Why:** The corpus is synthetically template-generated (see `generate_corpus.py`). A human — including the author of this project — "judging relevance" by reading 1,000 template-generated documents would just be re-deriving the same category/topic metadata that generation already fixed, dressed up as independent judgment when it wouldn't be. Being explicit about this is more honest than implying human-graded relevance where none meaningfully exists.
    - **Alternate:** Manually read and label every candidate document per query.
    - **Why rejected:** Not just impractical (20 queries × up to hundreds of candidates each) but not more rigorous — the "signal" a human would be pattern-matching on (title phrase, apparent topic) is exactly the metadata already available directly. This methodology is disclosed plainly in the evaluation report rather than presented as more independent than it is.

---

# COMPLEXITY ANALYSIS

### Complexity Philosophy

Complexity analysis matters here for four concrete reasons: response latency (does a query feel instant?), scalability (what breaks first as the corpus grows?), memory usage (can the whole index fit in RAM?), and honesty about tradeoffs (e.g. Phase 3 explicitly acknowledged that `rank_bm25` was _less_ efficient than a hand-rolled version could be, rather than glossing over it — Phase 4 is that hand-rolled version actually landing, closing the gap Phase 3 named in advance).

### Tokenizer — `tokenize()` _(unchanged)_

- Input size: _n_ characters.
- Operations: lowercase, remove punctuation, split, stopword lookup (O(1) per word via a set), stemming (roughly constant per word).
- **Time:** O(n)
- **Space:** O(n)

### Positional Index Construction _(unchanged)_

- Input: N documents, total tokens T.
- Each token is inserted into the index dictionary and has its position appended exactly once.
- **Time:** O(T)
- **Space:** O(T)

### Boolean Retrieval _(unchanged)_

- Posting list A of size _a_, posting list B of size _b_.
- Intersection / Union / Difference: **O(a + b)** each.
- Posting-list length, not corpus size, dominates cost — this is the entire point of using an index instead of a sequential scan.

### Phrase Search _(unchanged)_

For a phrase of length _k_, checked against posting lists of the phrase's constituent terms: roughly O(k × p) where _p_ is the length of the shortest involved posting list (the algorithm only needs to check offsets for each occurrence of the first term).

### BM25 _(Phase 3: `rank_bm25`; Phase 4: hand-rolled — the gap below is now closed)_

- **Phase 3 (`rank_bm25`, now removed):** model construction tokenized all T corpus tokens once (**Time/Space:** O(T)). Query scoring via `get_scores()` computed a score contribution per query term for **every** document in the corpus — **O(N × q) per call**, where _N_ is total corpus size and _q_ is query term count — regardless of how many documents were actually retrieved as candidates.
- **Phase 4 (`app/bm25.py`'s `score_candidates()`):** idf is computed once per unique query term (O(q)), then each of the _m_ candidate documents is scored against each of the _q_ terms via direct positional-index lookups (O(1) dict access per term per doc). **Time: O(m × q + q)**, i.e. **O(m × q)** — scored only against the candidate set, never the whole corpus. **Space:** O(q) for the per-term idf cache, negligible relative to the index itself.
- **This closes the exact gap Phase 3 flagged as an acknowledged inefficiency** (see Phase 3's Design Decisions §17 and Scalability): O(N × q) → O(m × q), which is a real win whenever `m < N` — true for almost every query, and increasingly true as the corpus grows relative to how selective its boolean/phrase filters are.
- **Repeated-query cache (Phase 4, `app/cache.py`):** on a cache hit, BM25 scoring cost drops to **O(1)** (a dict lookup) for the entire request — see the Score Normalization/Overall Query Complexity notes below for how this interacts with total request cost.

### PageRank _(new in Phase 3)_

- Graph with V nodes (documents) and E edges (links), converging in _k_ power-iteration steps (`networkx.pagerank()`'s default `max_iter`/`tol` govern _k_).
- **Time:** O(k × (V + E)) — each iteration touches every node and every edge once.
- **Space:** O(V + E) for the graph itself, O(V) for the score vector.
- Computed exactly once, at startup — this cost is paid once total, not once per query.

### Score Normalization _(new in Phase 3)_

- Min-max normalization over _m_ candidates: one pass to find min/max, one pass to rescale.
- **Time:** O(m). **Space:** O(m).

### Snippet Generation _(new in Phase 3; call site moved in Phase 4.5)_

- For a document of length _L_ words: one tokenization pass over the whole document (re-tokenized on every call, not precomputed).
- **Time:** O(L) per result. **Phase 4.5 fix: O(page_size × L) total, not O(m × L).** Through Phase 4, `main.py` called this once per ranked *candidate* (m), before pagination — measured at 1,000 documents as 237ms of a 245ms total query (97%), for a 100-candidate `climate` query. Moved to run only on the page slice actually returned; the same query dropped to 32ms total (6.4× faster). Cost is now independent of candidate count entirely.
- **Space:** O(L) per snippet (bounded further by the fixed 25-word window for the returned string, but the full-document tokenization pass still costs O(L)).
- No longer flagged as a scaling risk at any tested corpus size, now that cost no longer scales with candidate count — see Scalability.

### Deduplication _(new in Phase 3)_

- One fingerprint computation + hash-set lookup/insert per result.
- **Time:** O(m) for _m_ results (fingerprinting itself is O(doc length), so more precisely O(m × avg*doc_length), but bounded by the same \_m* results already being iterated for scoring/snippets).
- **Space:** O(m) for the seen-fingerprints set.

### Pagination _(new in Phase 3)_

- A single list slice after all sorting/filtering is complete.
- **Time:** O(page_size) — proportional to the slice returned, not the total result count.
- **Space:** O(page_size).

### Sorting _(unchanged mechanism, same complexity)_

- Python's Timsort over _m_ candidates.
- **Time:** O(m log m). **Space:** O(m).

### Repeated-Query Cache _(new in Phase 4)_

- **Hit:** one normalized-key dict lookup. **Time:** O(1). **Space:** none additional (already resident).
- **Set (on a miss):** one dict insert, plus an O(1) LRU eviction if the cache is already at `maxsize`.
- **Net effect on total query cost:** collapses the entire cache-miss complexity (O(m × q + m log m + m × L), see Overall Query Complexity below) down to O(page_size) for any repeated query.

### Prefix Search / Autocomplete _(new in Phase 4)_

- **Index construction (`build_suggest_index`):** one pass over all T corpus tokens (via `basic_tokenize`, same shape as the positional index build), then one sort of the resulting vocabulary. **Time:** O(T + V log V), where V is vocabulary size. **Space:** O(V).
- **Lookup (`get_suggestions`):** `bisect.bisect_left` locates the prefix's starting point in **O(log V)**, then a forward walk collects the _k_ matches actually found — **O(log V + k)** total, followed by an O(k log k) sort of just those matches by frequency. **Space:** O(k).

### Semantic Re-ranking _(new in Phase 5)_

- **Startup (once):** model load ~10s (measured); embedding all D documents ~8s at D=1,000 (`model.encode()`, batched). Both cached to disk after the first run — subsequent startups skip the embedding pass (not the model load, which must happen every process start to embed incoming queries).
- **Per query:** one query embedding (~tens of ms of transformer inference — the actual latency floor of this feature, not the arithmetic around it), one O(D) matrix multiply against precomputed document embeddings for augmentation, and O(top_k log top_k) to sort the re-ranked pool. **Time: O(D + top_k log top_k)** — dominated in practice by the fixed cost of one embedding-model inference call, not by anything that scales with candidate count.
- **Space:** O(D × 384) for the embeddings matrix (measured: 1.46MB for 1,000 documents at float32 — trivial).

### Overall Query Complexity (Phase 4.5)

**Cache miss, `rerank=false`:** **O(m × q + m log m + page_size × L)** — the snippet term changed from O(m × L) to O(page_size × L) in Phase 4.5 (see Snippet Generation above); the BM25 term stays O(m × q) from Phase 4. Here N = corpus size, q = query term count, m = candidate count, L = average document length, page_size = the requested page's result count.

**Cache miss, `rerank=true`:** adds the Semantic Re-ranking cost above — dominated in practice by the fixed ~tens-of-ms embedding-inference latency for the query, largely independent of m.

**Cache hit:** **O(page_size × L)**, not O(page_size) — a Phase 4.5 consequence worth calling out explicitly: since snippets now generate after pagination for *both* cache hit and miss, a cache hit is no longer near-zero cost the way it was through Phase 4 (measured: 0.02ms → ~20ms for a 10-result page). Validation, the cache lookup, and pagination remain O(1)/O(page_size); every other pipeline stage (spellcheck, parsing, retrieval, scoring, dedup) is still skipped on a hit — only snippet generation is now paid on every request regardless of cache status. See Design Decisions for why this tradeoff was accepted.

At the current corpus size (N=1,000), every path is fast in absolute terms (32-250ms depending on candidate count and rerank status); the point of the cache-miss complexity shape is that neither the BM25 term nor the snippet term degrades with corpus size the way both once did.

### Space Complexity — All Major Data Structures

| Data Structure                         | Space                                                     | Notes                                                                       |
| --------------------------------------- | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| Corpus Dictionary                      | O(D)                                                      | one entry per document                                                     |
| Positional Inverted Index              | O(T)                                                      | every token occurrence + its positions                                     |
| Document Length Table                  | O(D)                                                      | one integer per document; now actively used by hand-rolled BM25 (Phase 4)  |
| SymSpell Dictionary                    | O(V) + delete variants                                    | V = vocabulary size                                                        |
| Hand-Rolled BM25 (`app/bm25.py`)        | O(q)                                                      | per-query idf cache only — no persistent model object (Phase 4)           |
| Link Graph                             | O(V_docs + E_links)                                       | one node per doc, one edge per link                                       |
| PageRank Scores (raw + normalized)     | O(D)                                                      | two floats per document                                                   |
| Autocomplete Index (`suggest.py`)      | O(V)                                                      | sorted term list + frequency table, V = vocabulary size (Phase 4)         |
| Repeated-Query Cache (`cache.py`)      | O(min(distinct queries, maxsize) × avg result-list size)  | bounded by `maxsize` (default 256) via LRU eviction (Phase 4)             |
| On-Disk Index Cache (`persistence.py`) | O(T)                                                      | same content as the positional index + doc lengths, serialized (Phase 4)  |
| Document Embeddings (`semantic.py`)    | O(D × 384)                                                | 1.46MB measured at D=1,000; cached to disk (Phase 5)                       |

---

# SCALABILITY

The system runs as a fully in-memory, single-process deployment over 1,000 documents (grown from 100 in Phase 4.5, precisely to expose scale-dependent issues before they'd hit production). This section is about being explicit regarding what would need to change, and in what order, as scope grows further — not about implementing any of it yet.

**What broke first, now resolved: BM25's whole-corpus rescan.** As established in Complexity Analysis, `rank_bm25.get_scores()` used to cost O(N × q) per query — linear in total corpus size, not candidate-set size — which at N=1,000,000 would have dominated every query's latency regardless of how selective the boolean filters were. Phase 4's hand-rolled BM25 (`app/bm25.py`, scored directly against `candidate_ids`) closes this to O(m × q), where _m_ is the — usually much smaller — candidate count. This item is done; it's kept here, marked resolved, so the history of what broke and when stays visible.

**What broke second, now resolved: snippet generation's per-request re-tokenization.** Predicted as a risk in Phase 3's Scalability section; confirmed as the actual dominant cost once the corpus reached 1,000 documents with realistic (300-500 word) content — 237ms of a 245ms total query (97%), for a `climate` query with 100 candidates. Fixed in Phase 4.5 by moving snippet generation to run only on the paginated page slice, not every candidate. Measured result: 204ms → 32ms end-to-end for that same query. This is now resolved for any corpus size, since cost scales with `page_size` (a constant), not candidate count.

**What breaks first now: `index.py`'s dict-of-dicts positional index, at true web-scale.** `index.cpp` (the C++ reference this project ported ideas from) uses flat `termDictionary`/`globalPostingPool`/`globalPositionsPool` arrays instead of nested Python dicts specifically for cache-locality and to avoid per-entry object overhead — a real difference at millions of documents, though not one worth adopting yet (see Design Decisions §28). This is the next thing to reach for if the corpus genuinely grows large enough for it to matter, and now has a concrete reference implementation to draw from instead of a from-scratch design exercise.

**New in Phase 5: semantic re-ranking's per-replica model-load cost.** Loading `all-MiniLM-L6-v2` takes ~10s — paid on every process start, not cached the way document embeddings are (a replica needs the model in memory to embed incoming queries, regardless of whether its document embeddings came from disk). At single-process scale this is a one-time startup cost; at multi-replica scale, every replica pays it independently, and a slow-starting replica behind a load balancer is a real operational concern a production deployment would need to account for (e.g. readiness probes that wait for model load, not just process start).

**In-memory ceiling, partially addressed.** The corpus, positional index, link graph, and PageRank scores still live in one process's memory — but as of Phase 4, the positional index (plus doc lengths and corpus-wide stats) is persisted to disk (`app/persistence.py`) and *loaded* rather than *rebuilt* on every startup, provided the corpus hasn't changed since the cache was written. The link graph and PageRank scores are not yet persisted the same way — still rebuilt from scratch every startup. A production-scale version would need the index built as a separate offline step and shared across replicas (a shared disk cache today is a single-process optimization, not a multi-replica one yet), plus the same treatment extended to PageRank.

**Horizontal scaling of the API layer.** Because `main.py`'s request-handling logic holds no per-request mutable state (all shared state — the corpus, index, PageRank scores — is read-only after startup), the API layer itself is stateless and could be replicated behind a load balancer today for the *index*, since each replica can now load the same on-disk cache independently. Two Phase 4 additions don't extend cleanly to multiple replicas yet, though: the repeated-query cache (`cache.py`) and the rate limiter (`slowapi`) are both in-memory and per-process — a client could be rate-limited on replica A but not replica B, and a cache warmed on one replica wouldn't help requests landing on another. Both would need to move to a shared store (Redis is the standard choice for exactly this) once there's more than one replica — see Design Decisions §32-33 for why that move wasn't made now.

**Index sharding.** Once a corpus exceeds a single machine's practical index size, the standard approach is to shard the positional index by document ID range (or by term range) across multiple nodes, with a merge/scatter-gather step combining partial results — a significant architectural change from the current single-process design, and out of scope until the in-memory ceiling is actually reached.

**PageRank at scale.** Currently recomputed once at startup, which is fine for a static graph, and not yet covered by the Phase 4 persistence layer (see "In-memory ceiling" above). A live crawler continuously discovering new links would need either periodic batch recomputation (acceptable if authority scores can tolerate being slightly stale) or an incremental/streaming PageRank approximation (more complex, only worth it once batch recomputation itself becomes too slow to run frequently enough).

**Caching — implemented in Phase 4, in-memory only; latency profile changed by Phase 4.5.** A query-result cache exists (`app/cache.py`, LRU, keyed on normalized query — plus the `rerank` flag as of Phase 5), meaningfully cutting latency for repeated queries. Originally (Phase 4, 100-doc corpus): 7.91ms → 0.02ms on a hit, since a cached entry already included its snippets. Phase 4.5 moved snippet generation to *after* the cache lookup for both hit and miss paths (necessary so pagination still gets correct snippets for whichever page is requested) — so a hit is no longer near-zero: measured at the 1,000-doc corpus, a `climate` hit costs ~20ms (vs. ~32ms on a miss), still a real win, just not the two-orders-of-magnitude one it used to be. What the cache still doesn't solve: it's per-process, so it doesn't help once the API layer is replicated (see "Horizontal scaling" above) — that's the point at which Redis becomes the right call, not before (Design Decisions §32).

**Autocomplete at scale.** `suggest.py`'s sorted-list-plus-`bisect` approach is adequate while the vocabulary is small (measured: 1,417 terms at the current corpus size); a trie (or a proper search-as-you-type index) becomes worth the added complexity once vocabulary size or request volume on `/suggest` specifically shows up as a bottleneck (see Design Decisions in Component Documentation → `suggest.py`).

**Semantic re-ranking's augmentation step, at scale.** Currently O(D) per query (one matrix multiply against the whole corpus's embeddings) — trivially fast at D=1,000, but linear in corpus size, unlike BM25's candidate-scoped O(m × q). At a much larger corpus this would need an approximate-nearest-neighbor index (e.g. FAISS, HNSW) instead of a brute-force matrix multiply — not needed yet, but the first thing to revisit if the corpus grows another order of magnitude or two.

---

# LIMITATIONS

Honest, current-as-of-Phase-5 list of known gaps — distinguished from bugs by whether they're accepted tradeoffs (limitations) vs. defects with a designed fix pending application (flagged explicitly below). Items resolved are kept, marked resolved, so the history stays visible rather than silently disappearing.

1. ~~Phrase-only queries don't filter candidates.~~ **Resolved in Phase 4.5.** `retrieve_candidates()` now treats an included phrase as a hard requirement, not just a scoring boost. Measured before/after at the 1,000-doc corpus: `"renewable grid development"` went from 995 results to 7, all genuinely on-topic. See Design Decisions and the `index.py` entry in Component Documentation.
2. **AND-parsing sticky-mode bug.** Boolean queries where a bare word appears before the _first_ operator (e.g. `python AND kubernetes`) were found, during Phase 3 manual testing, to misparse that leading word as optional rather than required — causing AND queries to behave like OR queries in that specific shape. Root-caused, and a fix was designed and verified in an isolated test (see Design Decisions §22 and Complete Request Flow, Example 2). **Status: still open, untouched by Phase 4** — fix designed and explained to the project owner; live application to the running `query_parser.py` should be confirmed before trusting `AND` query results. Update this line once the fix has been pasted in and re-verified.
3. **Location field is not indexed.** `build_index()` (Phase 4's merged index builder) indexes only `title + content`; the `location` field (e.g. "Remote," "Noida") is invisible to search. A query like `remote` currently returns little to nothing relevant, even though many documents have that exact location. **Status: still open, untouched by Phase 4.**
4. **The link graph is synthetic, not real.** `corpus.json`'s `links` field was generated by a seeded random process specifically to unblock building and testing the PageRank fusion architecture ahead of real crawler data. PageRank scores in the current system reflect this fabricated graph structure, not genuine document authority — a real crawler's link graph is expected to replace it (see Future Roadmap), at which point PageRank's actual ranking influence should be re-evaluated. **Status: still open, untouched by Phase 4.**
5. ~~`rank_bm25` doesn't use the existing positional index.~~ **Resolved in Phase 4.** BM25 is now hand-rolled (`app/bm25.py`), scored directly against the candidate set (O(m × q)) using the existing positional index, doc lengths, and avg doc length — no whole-corpus rescan, and no separate library-managed model object. See Complexity Analysis.
6. ~~Snippet generation re-tokenizes on every request.~~ **Substantially resolved in Phase 4.5.** Still re-tokenizes per result (not precomputed), but now only for the page slice actually returned, not every candidate — the fix that mattered in practice, cutting a measured 204ms query to 32ms. See `snippets.py` in Component Documentation.
7. **Deduplication is exact-fingerprint only.** Catches byte-for-byte (post-normalization) duplicates like the confirmed doc 49/79 pair, but would miss near-duplicates that differ by even a few words. No fuzzy/similarity-based matching is implemented (see Design Decisions §26). **Status: still open, untouched by Phase 4.**
8. ~~No persistence layer.~~ **Partially resolved in Phase 4.** The positional index, doc lengths, and corpus-wide stats are now cached to disk (`app/persistence.py`) and reloaded on restart when the corpus hasn't changed since. **Still not persisted:** the link graph and PageRank scores, which are still rebuilt from scratch on every startup — see Scalability.
9. ~~No authentication, rate limiting, or abuse protection.~~ **Partially resolved in Phase 4.** `/search` and `/suggest` are now rate-limited (30/minute per client IP, `slowapi`, in-memory). **Still open:** no authentication of any kind — every endpoint remains fully open to any caller within the rate limit.
10. **Single-process, in-memory only.** No horizontal scaling story currently exists — see Scalability for what would need to change first. **Phase 4 note:** the index itself is now shareable across replicas via the on-disk cache, but the repeated-query cache and rate limiter are both in-memory and per-process, so they don't yet extend correctly to more than one replica (see Scalability and Design Decisions §32-33).
11. **No automated test suite.** Verification throughout Phases 1–4 has been manual: `tests/test_queries.md` (a written log of queries and expected behavior, extended in Phase 4 to cover `/suggest`, `/health`, caching, and rate limiting), `tests/run_queries.sh` (a script that fires them all at the running server), and ad-hoc `curl`/Python checks used to verify each Phase 4 change (cache hit/miss latency, index-cache staleness detection, BM25 ranking-order parity against `rank_bm25` before it was removed). There is still no `pytest` (or equivalent) suite that runs automatically or asserts expected outputs programmatically. **Status: still open, arguably more overdue given how much manual verification Phase 4 required.**
12. **No real operator precedence or parentheses in boolean queries.** Deliberately, explicitly out of scope from the start (see `query_parser.py`'s own design-decision comments and Design Decisions §22) — deeply mixed `AND`/`OR`/`NOT` queries have one fixed interpretation rather than a user-controllable grouping. **Status: still open, untouched by Phase 4.**
13. **Phrase adjacency is computed after stopword removal.** A phrase like "machine learning" will register as adjacent in a document containing "machine _of the_ learning," because "of" and "the" are stripped before position numbers are assigned. A deliberate, documented simplification carried over from Phase 2 — real search engines make similar tradeoffs, but it's worth naming explicitly. **Status: still open, untouched by Phase 4.**
14. **BM25 raw scores can be negative — for `rank_bm25` (removed in Phase 4), not for the current implementation.** For very common query terms in this small, templated corpus, the classic Robertson/Sparck-Jones idf `rank_bm25` used internally could go negative (floored via its epsilon mechanism). The hand-rolled BM25 that replaced it (`app/bm25.py`) uses the "+1" idf variant instead, which cannot go negative by construction (see Algorithms → BM25 Algorithm) — this specific historical note is kept for context, not because it still applies.
15. **A library's declared dependencies aren't always its full runtime dependency set.** `networkx.pagerank()` required `scipy` at runtime despite it not being listed as a `networkx` install-time requirement that `pip` resolved automatically — caught only because the server crashed at startup on first run. Worth remembering as a general lesson, not just a one-off fix.
16. **The repeated-query cache has no invalidation mechanism.** *(new in Phase 4)* If the corpus could ever change without a server restart, cached result lists would go stale with nothing to detect it — unlike the on-disk index cache, which does check `corpus.json`'s mtime. Not a problem today, since the corpus is static within a server's lifetime (the same assumption offset-pagination already relies on — Design Decisions §11), but worth flagging as a gap that would need closing before any live-update feature ships.
17. **The repeated-query cache and rate limiter are both per-process, in-memory state.** *(new in Phase 4)* Neither is visible to, or shared with, any other server process — meaning a client rate-limited by one replica isn't rate-limited by another, and a cache warmed by one replica doesn't help requests another replica receives. Not a problem yet, since the system runs as a single process (see Scalability), but this is exactly the gap Redis would close once horizontal scaling is actually implemented (Design Decisions §32).
18. **The corpus-derived spellchecker can still bias BM25's own ranking before semantic blending ever runs.** *(new in Phase 5)* Fixed: the semantic embedding now uses the raw query, not the spell-corrected one (see `semantic.py`). Not fixed: BM25 retrieval and scoring — which builds the "head" that gets semantically re-ranked — still runs on the corrected query. Directly observed: `helping sick people get better faster` had `sick`/`get` "corrected" to `since`/`gem` (both valid English words, just absent from this corpus), biasing which documents even entered the re-ranked pool. Improved re-ranking outcome from that fix (P@10 0.0 → 0.2 for that specific query) but didn't fully resolve it — a genuinely correct fix would need `main.py` to run a second, uncorrected parse/retrieve/score pass for the semantic path, not just a second embedding.
19. **This evaluation is bounded by a synthetic, template-generated corpus.** *(new in Phase 5)* Six of the ten semantic (paraphrase) test queries scored a perfect 1.0 Precision@10 under *both* BM25-only and BM25+semantic — meaning several "paraphrases" still had enough incidental lexical overlap with the corpus's fixed phrase-bank vocabulary for BM25 to already succeed unaided. The measured 20.8-22.5% improvement on the semantic subset is real, but likely understates the gap a naturally-written (non-template) corpus would show in both directions — both the cases where BM25 alone fails harder, and the cases where its baseline performance is stronger to begin with.
20. **Augmentation's cost is O(corpus size), not O(candidate count).** *(new in Phase 5)* `semantic_rerank()`'s augmentation step compares the query embedding against every document in the corpus — fine at 1,000 documents (a few milliseconds), but linear in corpus size unlike BM25's O(m × q). A much larger corpus would need an approximate-nearest-neighbor index (FAISS, HNSW) instead of a brute-force matrix multiply. See Scalability.
21. **No authentication still, even after Phase 5.** Every endpoint (including the newly rerank-capable `/search`) remains open to any caller within the rate limit — semantic re-ranking's added per-query cost (tens of milliseconds of model inference, vs. single-digit milliseconds for lexical-only) makes this a more expensive endpoint to leave unauthenticated than it was through Phase 4.

---

# FUTURE ROADMAP

Organized by theme rather than strict phase number, since some items depend on others being done first. Items Phase 4 completed are marked done and kept for history rather than deleted.

**Ranking & Retrieval Quality**

- ~~Hand-roll BM25 on top of the existing positional index~~ — **done in Phase 4** (`app/bm25.py`, ported from `index.cpp`), closing the O(N×q) → O(m×q) gap documented in Complexity Analysis.
- ~~Fix the phrase-filter gap~~ — **done in Phase 4.5**, once corpus scale made the cost of deferring it obvious (995→7 results for a specific phrase query).
- ~~Add semantic/vector search as a hybrid signal alongside BM25~~ — **done in Phase 5** (`app/semantic.py`), with a quantified before/after: +12.6% P@10, +13.8% MRR, +11.5% nDCG@10 overall; +21.7%/+22.5%/+20.8% on paraphrase-style queries specifically.
- Confirm and re-verify the AND-parsing fix (Limitations #2) is live in `query_parser.py`, then extend test coverage specifically for boolean-operator edge cases.
- Consider a real operator-precedence/parentheses grammar for boolean queries, if query complexity from real users ever demands it.
- Index the `location` (and possibly `company`) fields as filterable facets, separate from full-text relevance search.
- Re-evaluate the BM25/PageRank fusion weights (currently 0.85/0.15, acknowledged as arbitrary) once a real link graph and/or labeled relevance judgments exist.
- Re-tune the semantic/BM25 blend weight (currently 0.5/0.5, acknowledged as arbitrary in the same way) once more evaluation data exists — same status as the BM25/PageRank weights above.
- Give the semantic-re-ranking path its own uncorrected retrieval pass (Limitations #18), instead of only fixing the query embedding — BM25's own candidate ordering still runs on the spell-corrected query even when `rerank=true`.

**Data & Infrastructure**

- Replace the synthetic seeded-random link graph with a real crawler's output once available.
- ~~Add a persistence layer so startup doesn't rebuild everything from `corpus.json` every time~~ — **partially done in Phase 4** (`app/persistence.py` covers the positional index, doc lengths, and corpus stats). **Still open:** extend the same treatment to the link graph and PageRank scores, which still rebuild from scratch every startup.
- ~~Precompute snippet-relevant tokenization instead of per-request~~ — **substantially done in Phase 4.5**: still per-request, but now scoped to the page slice rather than the full candidate set (204ms → 32ms measured). True precomputation at index-build time remains a further option if this ever becomes a bottleneck again.
- Add fuzzy/near-duplicate detection to deduplication, for when the corpus stops being hand-curated and starts coming from a messier real crawl.
- Move to cursor-based pagination once the corpus supports live updates between page requests.
- Consider porting `index.cpp`'s flat `termDictionary`/`globalPostingPool`/`globalPositionsPool` array layout (Design Decisions §28) if the corpus ever grows large enough for dict-of-dicts overhead to actually show up in profiling — not before.

**Scale**

- Index sharding once corpus size exceeds single-machine memory (see Scalability).
- ~~A query-result cache for repeated/popular queries~~ — **done in Phase 4** (`app/cache.py`, in-memory LRU). **Still open:** move to a shared cache (Redis) once the API layer is actually replicated — an in-memory, per-process cache doesn't help across multiple replicas (see Scalability, Design Decisions §32).
- Move rate limiting (currently `slowapi`'s in-memory storage) to a shared backend (Redis, via `limits`' built-in Redis storage support) for the same reason — per-process rate limiting doesn't hold once there's more than one replica (Design Decisions §33).
- Incremental or batch-periodic PageRank recomputation for a continuously-crawled corpus.

**Search Quality Beyond Lexical Matching**

- ~~Semantic / vector search as a hybrid signal alongside BM25~~ — **done in Phase 5**, see Ranking & Retrieval Quality above for the numbers. What's left in this space: an ANN index (FAISS/HNSW) once corpus size makes augmentation's O(D)-per-query cost a real bottleneck (see Scalability); replacing this project's un-tuned 50/50 blend weight with something evaluation-justified; and evaluating against a naturally-written corpus, not just this synthetic one (Limitations #19).
- Learning-to-rank, once enough query/click (or otherwise labeled relevance) data exists to train against — the structured JSON logs added in Phase 4 (`app/logging_config.py`) are the concrete first step toward having that data at all.
- Title-level (not just word-level) autocomplete suggestions in `/suggest` (e.g. "software eng" → "Software Engineer at Razorpay"), once there's a concrete UX reason to want it over the current word-completion behavior.

**Engineering Hygiene**

- An automated test suite (`pytest`) covering the tokenizer, parser, retrieval, ranking, snippet generation, deduplication, caching, the hand-rolled BM25, and semantic re-ranking independently — replacing the current manual `test_queries.md`/`run_queries.sh` workflow, or at minimum running alongside it. **More overdue with every phase**, not less: Phase 5's correctness (three real bugs in `semantic.py` alone) was entirely found and verified by hand, the same as Phase 4's.
- ~~Rate limiting on the API~~ — **done in Phase 4** (`slowapi`, 30/minute per IP on `/search` and `/suggest`). **Still open, and more pressing after Phase 5:** authentication — `rerank=true` costs tens of milliseconds of model inference per request versus single digits for lexical-only, making an unauthenticated, unlimited-except-by-rate-limit endpoint a more expensive one to leave open than it was through Phase 4.
- ~~Basic observability: query latency logging~~ — **done in Phase 4** (`app/logging_config.py`, structured JSON per request, now including the `rerank` flag as of Phase 5). **Still open:** click-through data, if a frontend is ever built, to eventually evaluate ranking quality against.
- A minimal frontend, if only to make `<mark>`-tagged snippets actually render as intended, and to give `/suggest` somewhere to actually show suggestions as the user types.

---

# INTERVIEW QUESTIONS

Grounded directly in decisions made in this project — useful as prep material, not generic IR trivia.

1. **Why use an inverted index instead of scanning every document per query?** _Turns O(N) document scans into O(df) posting-list lookups, where document frequency is typically far smaller than corpus size — see Algorithms → Positional Inverted Index Construction._
2. **Walk through what happens when a user searches `python AND kubernetes`.** _A great chance to walk through the actual bug found in this project (Complete Request Flow, Example 2) — including how you diagnosed it by checking a specific document's real content rather than just reasoning about the code abstractly._
3. **Why store term positions instead of just document IDs in the index?** _Enables phrase queries and lets term frequency be read directly from the index instead of re-tokenizing documents at ranking time._
4. **How does phrase search work on top of a positional index, and what's a known limitation of your implementation?** _Consecutive-offset checking on stemmed/stopword-stripped positions; the known limitation is that adjacency is computed post-stopword-removal, so "machine of the learning" would still register as adjacent._
5. **Why is stemming applied before indexing, but the original (unstemmed) document text still used for generating snippets?** *Indexing needs term-matching consistency (stem vs. stem); snippets need to show the user real, readable text — stemming is used only to *decide what to highlight* within that real text, not to replace it.*
6. **What's the practical difference between BM25 and TF-IDF, and why does it matter?** _BM25 adds term-frequency saturation and document-length normalization on top of what TF-IDF does — see Algorithms → BM25 Algorithm for the formula and reasoning._
7. **Why did you normalize BM25 and PageRank scores before combining them, instead of combining raw scores?** _Different, incomparable raw scales (BM25 unbounded and occasionally negative; PageRank tiny fractions summing to 1) would let one signal dominate regardless of the intended weighting — see Design Decisions §20._
8. **What would break first if this corpus grew from 100 to 10 million documents?** _`rank_bm25`'s whole-corpus rescan per query (O(N×q)) — see Scalability for the full breakdown of what changes at scale, in what order._
9. **Why is retrieval kept strictly separate from ranking?** _So each can evolve independently — demonstrated concretely when TF-IDF became BM25, and later when PageRank fusion was added, without touching retrieval logic at all._
10. **How does SymSpell achieve faster lookups than naive edit-distance search?** _Precomputes delete-variants of every dictionary word once at build time, shifting the expensive work out of the request path._
11. **Why build the spelling dictionary from the corpus instead of using a general English dictionary?** _Avoids flagging legitimate domain terms (company names, technical jargon) as typos — see Design Decisions §10._
12. **Describe a real bug you found during testing, and how you diagnosed it.** _The AND-parsing bug: noticed via a suspicious result overlap between an AND and a NOT query, confirmed by checking a specific document's actual content, traced to the exact line in the parser, fixed with a minimal, scoped change, and verified against multiple test cases before it was ever merged._
13. **Why is deduplication necessary in this specific project, and how do you decide which duplicate to keep?** _The corpus contains genuine duplicate postings differing only in an unindexed field; the highest-scoring copy is kept by relying on the result list already being sorted before dedup runs._
14. **What are the tradeoffs of offset-based vs. cursor-based pagination?** _Offset-based is simpler and sufficient for a static, non-mutating result set; cursor-based is more robust once the underlying data can change between a user's page requests — see Design Decisions §27._
15. **How would you explain PageRank's damping factor to a non-technical interviewer?** _It models a random web surfer who usually follows links, but occasionally gets bored and jumps to a totally random page instead — the damping factor is the probability of following a link rather than jumping randomly._
16. **You replaced a library (`rank_bm25`) with a hand-rolled implementation and the numbers didn't match. How did you figure out whether that meant your port was wrong?** _Compared against the library's actual source instead of assuming: found `rank_bm25` used a different `k1` (1.5 vs. the ported formula's 1.2) and a different idf formula (classic Robertson/Sparck-Jones with an epsilon floor, vs. the "+1" variant Lucene/Elasticsearch and the ported `index.cpp` formula both use). Since the two are different, both-legitimate BM25 variants — and since `ranking.py` min-max normalizes BM25 before combining it with PageRank anyway — the right check wasn't "do raw scores match" but "does relative ranking order match," which it did on every test query. See Design Decisions §29._
17. **Why cache the full result list per query instead of caching per `(query, page, page_size)`?** _Retrieval and ranking cost the same regardless of which page is requested — only the final slice differs. Caching per-page would make every page after the first a guaranteed cache miss for a query that's already been fully computed once. See Design Decisions §31._
18. **Why choose an in-memory cache and an in-memory rate limiter instead of Redis, given Redis is the "obvious" production choice?** _Because the system runs as a single process — Redis's actual benefit is sharing state across multiple replicas, which doesn't apply yet. Reaching for it now would be solving a problem the system doesn't have, the same MVP-first reasoning Phase 3 already applied to `rank_bm25` and `networkx`. It becomes the right call the moment there's more than one server process — see Design Decisions §32-33 and Scalability._
19. **How do you detect that an on-disk index cache is stale, and why does that check matter?** _By comparing the source corpus file's modification time at load time against the mtime recorded inside the cache file when it was built — if they differ, the corpus changed since the cache was written, so it's rebuilt instead of trusted. Without this, editing the corpus and restarting the server would silently serve an index built from old data, with no error at all._
20. **Why did merging two existing functions (`build_inverted_index` + `build_doc_lengths`) into one (`build_index`) matter, when both already worked correctly?** _Both independently tokenized the entire corpus — along with a third pass in the (now-removed) BM25 model builder, that's three full-corpus tokenization passes for data cheapest to compute together. Not a correctness bug, but exactly the kind of redundant work that stops being "harmless at 100 documents" as the corpus grows — and the merge was a direct port of a design choice already made in a working C++ reference implementation, not a novel optimization invented from scratch._
21. **A "rerank the top-K BM25 results" design sounds sufficient for semantic search — what's actually missing from that description?** _It can only ever reorder documents BM25 already found. A genuine paraphrase query sharing no vocabulary with its target documents makes BM25's candidate set empty, so reranking becomes a silent no-op. The fix (`semantic.py`'s "augmentation" step) compares the query embedding against the whole corpus's precomputed embeddings — cheap, one matrix multiply — so genuinely relevant documents can surface even when lexical retrieval found nothing at all._
22. **How do you decide whether a "hybrid search" feature is safe to apply to every query, including ones with explicit boolean operators?** _By checking for an explicit hard constraint (required/excluded terms, phrases) the semantic-only path can't verify, not by checking how many candidates lexical retrieval already found. A query can retrieve hundreds of candidates through one noisy common word while still being poorly served — high candidate count is not the same signal as "this query doesn't need help." Caught directly: a confident `python AND kubernetes` query was initially getting diluted with unrelated semantically-similar documents that didn't actually satisfy the AND._
23. **What's the actual evidence that a technique like semantic re-ranking helped, versus just asserting it should?** _Splitting the evaluation by query type: a lexical control group (BM25 should already do well) barely moved, while a semantic/paraphrase group improved 20-23% across three separate metrics. Reporting only the overall average would have hidden that the lexical group's near-zero movement is itself evidence the technique isn't introducing regressions where it shouldn't help — and would have hidden the real misses (one query regressed, one scored zero under both modes) that a credible evaluation has to show, not hide._
24. **Why compute Precision@10, MRR, AND nDCG@10, instead of picking the one metric that looks best?** _They reward different things: Precision@10 is raw hit rate within the top 10 regardless of order; MRR rewards getting any hit to the very top but stops caring after the first one; nDCG@10 is the only one of the three sensitive to whether the best results specifically are near the top, not just present somewhere in it. A ranking change can improve one and hurt another (observed directly: one query's Precision@10 stayed flat while its MRR and nDCG@10 both dropped) — reporting only one metric would hide that._

---

# GLOSSARY

- **Inverted Index** — A mapping from terms to the documents (and, in this project, positions) containing them; the core data structure that makes search fast.
- **Posting List** — The list of documents (and positions) associated with a single term in the inverted index.
- **Positional Index** — An inverted index that also stores _where_ in each document a term occurs, enabling phrase and proximity search.
- **Term Frequency (TF)** — How often a term appears within a single document.
- **Document Frequency (DF)** — How many documents in the corpus contain a given term at all.
- **Inverse Document Frequency (IDF)** — A weighting that increases as document frequency decreases; rarer terms are treated as more informative.
- **TF-IDF** — A relevance scoring function combining term frequency and inverse document frequency.
- **BM25** — A relevance scoring function extending TF-IDF with term-frequency saturation and document-length normalization; the current standard in classical (non-neural) information retrieval.
- **PageRank** — A graph-based algorithm that scores a node's "authority" based on the quantity and quality of other nodes linking to it, originally developed for ranking web pages.
- **Damping Factor** — In PageRank, the probability that a random walk follows an outgoing link rather than jumping to a uniformly random node; conventionally 0.85.
- **Tokenization** — Splitting raw text into a sequence of discrete, normalized terms.
- **Stemming** — Reducing a word to an approximate root form (e.g. "running" → "run") so related word forms match during search.
- **Lemmatization** — Similar to stemming, but produces a real dictionary word rather than an approximate root; more accurate but computationally heavier.
- **Stopword** — A very common word (e.g. "the," "is," "and") typically excluded from indexing to reduce index size and retrieval noise.
- **Edit Distance** — The minimum number of single-character insertions, deletions, or substitutions needed to turn one string into another; the basis of spelling correction.
- **SymSpell** — An edit-distance-based spelling correction algorithm that precomputes delete-variants of dictionary words to make lookup fast.
- **Boolean Retrieval** — Query matching using AND / OR / NOT logic over sets of documents.
- **Candidate Set** — The set of documents that satisfy a query's boolean/phrase constraints, before ranking is applied.
- **Phrase Query** — A query requiring an exact, consecutive sequence of terms to appear in a document.
- **Snippet** — A short excerpt of a document's text, typically shown alongside a search result, often with matched terms highlighted.
- **Highlighting** — Visually marking the specific words within a snippet that matched the user's query.
- **Deduplication (Dedup)** — Detecting and collapsing duplicate or near-duplicate documents in a result set.
- **Fingerprint** — A normalized representation of a document's content, used to detect exact or near duplicates.
- **Pagination** — Splitting a large result set into discrete, sequentially requestable pages.
- **Tie-Breaking** — A secondary, deterministic sort key applied when a primary sort key (e.g. relevance score) produces equal values for multiple items.
- **Score Normalization** — Rescaling raw scores from different sources onto a common scale (e.g. `[0, 1]`) so they can be meaningfully combined.
- **Corpus** — The full collection of documents a search engine indexes and searches over.
- **Query Parsing** — Converting a raw query string into a structured representation the rest of the system can act on.
- **REST API** — An HTTP-based interface where resources are addressed by URL and operated on via standard HTTP methods (here, `GET /search`).
- **FastAPI** — A Python web framework used to implement this project's REST API, chosen for automatic request validation and OpenAPI documentation generation.
- **Startup Initialization** — Expensive setup work (index building, model construction) performed once when a server process starts, rather than repeated per request.
- **Link Graph** — A directed graph representation of documents and the links between them, used as input to PageRank.
- **Authority Score** — A relevance-independent signal (in this project, PageRank) representing how "important" a document is based on structural properties (here, incoming links) rather than its text content.
- **Relevance Score** — A signal (in this project, BM25) representing how well a document's _content_ matches a query.
- **LRU Cache (Least Recently Used)** — A bounded cache that, once full, evicts whichever entry hasn't been accessed most recently, rather than evicting randomly or never.
- **Cache Key Normalization** — Transforming a lookup key (here, a query string) into a canonical form (e.g. lowercased, whitespace-trimmed) before using it, so trivially different inputs still hit the same cache entry.
- **Cache Invalidation / Staleness** — The problem of a cached value no longer matching its source data; solved here for the on-disk index cache via a source-file modification-time check, and explicitly *not* solved for the repeated-query result cache (see Limitations #16).
- **Rate Limiting** — Restricting how many requests a client may make within a time window, to protect a service from accidental or intentional request floods.
- **Autocomplete / Prefix Search** — Suggesting likely completions for a partially-typed input, typically by matching a prefix against a vocabulary of known terms.
- **Binary Search (`bisect`)** — Locating a target (or insertion point) within a *sorted* sequence in O(log n) by repeatedly halving the search range, instead of scanning linearly.
- **Structured Logging** — Emitting log lines in a consistent, machine-parseable format (here, one JSON object per line) rather than free-form text, so logs can be queried and aggregated programmatically instead of only read by a human.
- **Index Persistence** — Saving a built index to durable storage (here, a pickled file on disk) so it can be reloaded on the next process start instead of rebuilt from the source corpus every time.
- **Response Schema (Pydantic Model)** — A declared, typed shape for API input or output, validated automatically by the web framework, as opposed to an ad-hoc dictionary whose shape only exists implicitly in the code that builds it.
- **Reference Implementation** — An existing, working implementation of an algorithm or system used as a concrete guide when building a second implementation, even across languages — in this project, a teammate's C++ `index.cpp` served as the reference for this codebase's hand-rolled BM25 and index-persistence design.
- **Sentence Embedding** — A fixed-length numeric vector representing the *meaning* of a piece of text, produced by a neural network, such that texts with similar meaning produce vectors that are close together in vector space — the basis of semantic (as opposed to purely lexical) search.
- **Cosine Similarity** — A measure of how similar two vectors are in direction, regardless of magnitude; for two L2-normalized vectors, mathematically equivalent to their dot product — the standard way to compare two embeddings.
- **Semantic Re-ranking** — Reordering an already-retrieved set of candidate documents by meaning-based similarity to the query, typically layered on top of (not replacing) a faster lexical retrieval stage.
- **Hybrid Retrieval** — Combining a lexical (e.g. BM25) signal with a semantic (embedding-based) signal, either to re-rank a lexical candidate set or to also surface documents the lexical stage missed entirely (this project's "augmentation" step).
- **Ground Truth** — In evaluation, the accepted correct answer (here, which documents are actually relevant to a query) that a system's output is measured against.
- **Precision@K** — Of the top K results a system returns, the fraction that are actually relevant.
- **Mean Reciprocal Rank (MRR)** — The average, across queries, of one divided by the rank position of the first relevant result — rewards getting a relevant result near the very top, indifferent to anything after it.
- **Normalized Discounted Cumulative Gain (nDCG)** — A ranking-quality metric that rewards relevant results appearing earlier in a ranked list more than the same results appearing later, normalized against the best-possible ordering of the same relevant set.
- **A/B Comparison** — Evaluating two versions of a system (here, BM25-only vs. BM25+semantic) against the same inputs to measure the actual effect of a change, rather than assuming it from a qualitative description.
