import json  # standard library module for parsing JSON text into Python objects
from pathlib import Path  # OS-independent way to read the corpus file from disk
# shared pipeline: lowercase -> strip punctuation -> split -> remove stopwords -> stem
from app.tokenizer import tokenize

# The inverted index structure changes from term → set(doc_id) to term → {doc_id: [positions]} so you can check adjacency for phrase search. Also needs new retrieval logic: currently candidates() only does OR (union) — now you need intersection (AND) and exclusion (NOT) as well, plus a phrase-checker that uses the position lists to confirm terms are consecutive in a doc.


# loads corpus.json and re-keys it by doc id for O(1) lookup
def load_corpus(path: str) -> dict:
    # read the file as text, then parse it into a list of dicts
    docs = json.loads(Path(path).read_text())
    # rebuild as {id: doc} instead of a plain list
    return {d["id"]: d for d in docs}


# builds term -> {doc_id: [positions]} across the whole corpus, PLUS doc lengths and
# corpus-wide length stats, all in a single pass over the corpus.
#
# Ported from index.cpp's InvertedIndex::build(): that function tokenizes each document
# exactly once and derives docLengths, avgDocLength, and the positional postings from
# that single pass. Our Phase 2/3 code tokenized the corpus THREE separate times at
# startup instead (once each in build_inverted_index(), build_doc_lengths(), and
# build_bm25_index()) -- functionally fine at 100 docs, but pure waste, and the kind of
# thing that stops being fine once the corpus is no longer tiny. This merges the first
# two into one pass; build_bm25_index() still tokenizes separately for now since it
# feeds a different library's model, until it's replaced by hand-rolled BM25.
#
# avg_doc_length and total_docs_count are new here -- index.cpp computes both directly
# in build() because BM25 needs them (see its searchBM25()); our own hand-rolled BM25
# needs the exact same two numbers, which is why they're introduced in this pass rather
# than being computed on demand later.
def build_index(docs: dict) -> tuple[dict, dict, float, int]:
    # positional index being constructed: {term: {doc_id: [position, position, ...]}}
    index: dict = {}
    # token count per document, keyed by doc_id
    doc_lengths: dict = {}
    total_tokens = 0

    for doc_id, doc in docs.items():  # walk every document in the corpus, once
        # tokenize WITHOUT deduping — we need every occurrence and its position, not just presence
        tokens = tokenize(doc["title"] + " " + doc["content"])

        doc_lengths[doc_id] = len(tokens)
        total_tokens += len(tokens)

        # position = this token's index within the doc's tokenized stream
        for position, term in enumerate(tokens):
            # ensure this term has a postings dict entry
            index.setdefault(term, {})
            # ensure this term has a position list for this specific doc
            index[term].setdefault(doc_id, [])
            # record that `term` occurs at `position` in `doc_id`
            index[term][doc_id].append(position)

    total_docs_count = len(docs)
    avg_doc_length = (total_tokens / total_docs_count) if total_docs_count else 0.0

    return index, doc_lengths, avg_doc_length, total_docs_count


# which docs contain this single term, regardless of position
def doc_ids_for_term(term: str, inverted_index: dict) -> set:
    # postings dict's keys ARE the doc ids; empty dict (default) gives an empty set for unseen terms
    return set(inverted_index.get(term, {}).keys())


# OR / union: doc matches if it has ANY query term
def candidates(query_terms: list[str], inverted_index: dict) -> set:
    result = set()  # accumulator, starts empty
    for term in query_terms:  # check every query term
        # union in whichever docs contain this term
        result |= doc_ids_for_term(term, inverted_index)
    return result  # docs matching at least one term


# AND: doc matches only if it has EVERY query term
def intersect_candidates(query_terms: list[str], inverted_index: dict) -> set:
    if not query_terms:  # an empty AND-list has no sensible intersection
        return set()  # so return no matches instead of guessing
    # seed with the first term's doc set
    result = doc_ids_for_term(query_terms[0], inverted_index)
    for term in query_terms[1:]:  # then narrow with each remaining term
        # keep only docs present in both sets so far
        result &= doc_ids_for_term(term, inverted_index)
    return result  # docs that contained every required term


# NOT: strip out docs containing any excluded term
def exclude_candidates(doc_ids: set, excluded_terms: list[str], inverted_index: dict) -> set:
    result = set(doc_ids)  # copy so we don't mutate the caller's set
    for term in excluded_terms:  # check each excluded term
        # remove any doc that contains it
        result -= doc_ids_for_term(term, inverted_index)
    return result  # the surviving, filtered doc set


# how many times `term` occurs in `doc_id`
def term_frequency_in_doc(term: str, doc_id: int, inverted_index: dict) -> int:
    # this term's position list within this doc (empty if absent)
    positions = inverted_index.get(term, {}).get(doc_id, [])
    # count of positions = term frequency; we'll use this in ranking.py instead of re-tokenizing the doc
    return len(positions)


# does this exact term sequence occur contiguously in this doc?
def phrase_match(phrase_terms: list[str], doc_id: int, inverted_index: dict) -> bool:
    if not phrase_terms:  # an empty phrase can't match anything
        return False  # bail out immediately
    # every position where the phrase's first word occurs in this doc
    first_term_positions = inverted_index.get(phrase_terms[0], {}).get(doc_id)
    if not first_term_positions:  # if the first word isn't even in this doc
        return False  # the whole phrase can't be, so stop here
    for start_pos in first_term_positions:  # try each occurrence of the first word as a candidate phrase start
        is_match = True  # assume it works until a term breaks the chain
        # check that every phrase term sits at the right consecutive offset
        for offset, term in enumerate(phrase_terms):
            term_doc_positions = inverted_index.get(term, {}).get(
                doc_id, [])  # this term's positions within this doc
            # term should appear exactly `offset` slots after the phrase start
            if (start_pos + offset) not in term_doc_positions:
                is_match = False  # this start position doesn't produce a contiguous phrase
                break  # no point checking further terms from this start position
        if is_match:  # every term lined up consecutively
            return True  # found a match, done
    return False  # no start position produced a full match


# combines required/optional/excluded/phrase logic into one final candidate doc-id set


def retrieve_candidates(structured_query: dict, docs: dict, inverted_index: dict) -> set:
    # docs satisfying ALL required terms, or empty set if there are none
    required_ids = intersect_candidates(
        structured_query["required"], inverted_index) if structured_query["required"] else set()
    # docs matching ANY optional term, or empty set if there are none
    optional_ids = candidates(
        structured_query["optional"], inverted_index) if structured_query["optional"] else set()
    # a doc qualifies if it fully satisfies the AND clause OR matches at least one OR term
    base = required_ids | optional_ids
    # special case: a pure exclusion query like "NOT rust" has nothing to union from
    if not structured_query["required"] and not structured_query["optional"]:
        # so start from the whole corpus and let the NOT-filtering below narrow it down
        base = set(docs.keys())
    # remove docs containing any excluded single term
    base = exclude_candidates(
        base, structured_query["excluded"], inverted_index)
    base = {  # remove docs matching any excluded phrase
        doc_id for doc_id in base
        if not any(phrase_match(p, doc_id, inverted_index) for p in structured_query["excluded_phrases"])
    }
    # an included phrase is a REQUIREMENT, not just a later scoring boost -- a doc
    # must contain every quoted phrase to qualify at all. Without this, a phrase-only
    # query (no bare required/optional words) fell through to the "whole corpus"
    # fallback above with nothing left to narrow it back down, so e.g. a single
    # 3-word phrase query against a 1000-doc corpus returned nearly all 1000 docs.
    if structured_query["phrases"]:
        base = {
            doc_id for doc_id in base
            if all(phrase_match(p, doc_id, inverted_index) for p in structured_query["phrases"])
        }
    return base  # final set of doc ids eligible for scoring

# Phrase matching operates on the processed token stream, not raw text. Since tokenize() now removes stopwords and stems, "adjacent" here means adjacent after stopwords are stripped and words are stemmed. Concretely: a doc containing "machine learning of the future" will register "machine" and "learning" as adjacent (positions 0 and 1) because "of", "the" get filtered out before positions are assigned. This is a deliberate simplification, not a bug — real search engines make the same tradeoff — but it's worth stating explicitly in your Phase 6 writeup as a known limitation of exact phrase search on a stopword-stripped index.

# Good news: nothing else breaks right now. main.py still calls candidates(query_terms, inverted_index) with the same signature and gets back the same type (a set of doc IDs) — only the internals changed. ranking.py's len(inverted_index.get(term, set())) for document frequency still works correctly too, since len() of the new postings dict equals the doc count, same as before. You can restart the server right now and /search will behave exactly as it did before this file — the new functions (intersect_candidates, exclude_candidates, phrase_match, term_frequency_in_doc) just aren't wired into anything yet. That wiring happens in query_parser.py and then ranking.py/main.py.
