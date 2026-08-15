import re  # used to normalize whitespace before fingerprinting a doc's text

# Your corpus actually contains duplicate postings (e.g. doc 27 and doc 49 are both "Backend Engineer at
# Tower Research" in Noida with identical content) -- this collapses them so a user doesn't see the same
# job twice in their results.


# builds a normalized fingerprint of a doc's searchable text: lowercased, whitespace-collapsed, so two
# docs with identical content but different formatting (extra spaces, different casing) still match
def _fingerprint(doc: dict) -> str:
    combined = f"{doc['title']} {doc['content']}".lower()
    return re.sub(r"\s+", " ", combined).strip()


# removes duplicate docs from an already-sorted (best-score-first) result list, keeping only the
# first (i.e. highest-scoring) copy of each distinct fingerprint
def dedup_results(scored_results: list, docs: dict) -> list:
    seen_fingerprints = set()  # fingerprints already kept
    deduped = []
    for result in scored_results:  # caller must pass results already sorted best-first
        fingerprint = _fingerprint(docs[result["doc_id"]])
        if fingerprint in seen_fingerprints:  # a better- or equally-scored duplicate already got kept
            continue
        seen_fingerprints.add(fingerprint)
        deduped.append(result)
    return deduped
