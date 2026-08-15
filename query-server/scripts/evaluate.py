"""
Phase 5 evaluation framework: BM25-only vs. BM25+semantic re-ranking,
scored with Precision@10, MRR, and nDCG@10 against a judgment set.

GROUND-TRUTH METHODOLOGY -- read this before trusting the numbers below.
This corpus (data/corpus.json) is synthetically generated (scripts/generate_corpus.py)
from a small, fixed phrase bank per domain/topic/company. Because the generation
process is known, "relevant" documents for a given test query can be determined
PROGRAMMATICALLY and reproducibly, rather than by a human eyeballing 1000+ documents
(which wouldn't be more rigorous here -- it would just be re-deriving the same
metadata by pattern-matching titles). Two judgment types are used:

  - "lexical" queries: relevance = the document's title contains the exact topic
    phrase the query names (e.g. query "climate research" -> every doc titled
    "... Climate Research"). These are a sanity/control group -- BM25 should
    already do very well here, since the query IS the literal indexed phrase.

  - "semantic" queries: relevance = the document's `category` field matches the
    query's target domain (e.g. query "fighting global warming with clean power"
    -> every science_environment doc). These are paraphrases that deliberately
    avoid the corpus's exact template vocabulary, testing whether meaning-based
    retrieval finds the right general topic area even without literal overlap.

This methodology is honest about being reproducible-by-construction rather than
independent human judgment -- which is the tradeoff of evaluating against a
synthetic corpus. It is NOT reproducible in the sense of "capturing a diverse
range of user relevance opinions." See the evaluation report / write-up for how
this limitation is disclosed.

BM25-only and BM25+semantic are each run through the SAME code paths main.py's
/search endpoint uses (including the unknown-word rejection that only applies to
the non-rerank path), not an idealized bypass -- so this reflects what a real
client actually gets from each mode, not a hypothetical best case.
"""
import json
import math
from pathlib import Path

from app.index import load_corpus, build_index, retrieve_candidates
from app.query_parser import parse_query
from app.validation import validate_query
from app.ranking import score_documents
from app.spellcheck import build_symspell, correct_query
from app.authority import build_link_graph, compute_pagerank, normalize_pagerank
from app.semantic import load_model, build_doc_embeddings, semantic_rerank

CORPUS_PATH = "data/corpus.json"
K = 10  # Precision@K and nDCG@K cutoff


# ---------------------------------------------------------------------------
# Judgment set
# ---------------------------------------------------------------------------

def _docs_with_title_containing(docs: dict, phrase: str) -> set:
    phrase_lower = phrase.lower()
    return {doc_id for doc_id, doc in docs.items() if phrase_lower in doc["title"].lower()}


def _docs_in_category(docs: dict, category: str) -> set:
    return {doc_id for doc_id, doc in docs.items() if doc.get("category") == category}


def build_judgments(docs: dict) -> list:
    judgments = []

    lexical = [
        ("renewable grid development", "Renewable Grid Development"),
        ("climate research", "Climate Research"),
        ("online learning", "Online Learning"),
        ("transfer window", "Transfer Window"),
        ("streaming series", "Streaming Series"),
        ("data privacy law", "Data Privacy Law"),
        ("cryptocurrency regulation", "Cryptocurrency Regulation"),
        ("plant-based menu", "Plant-Based Menu"),
        ("sustainable tourism", "Sustainable Tourism"),
        ("vaccination", "Vaccination"),
    ]
    for query, title_phrase in lexical:
        judgments.append({
            "query": query,
            "type": "lexical",
            "relevant_ids": _docs_with_title_containing(docs, title_phrase),
        })

    semantic = [
        ("fighting global warming with clean power", "science_environment"),
        ("helping sick people get better faster", "healthcare"),
        ("teaching kids to read and do math better", "education"),
        ("protecting the environment and reducing pollution", "science_environment"),
        ("keeping bank customers money and data safe", "finance"),
        ("watching movies and TV shows at home", "entertainment"),
        ("planning a trip abroad and finding good hotels", "travel"),
        ("cooking great food and running a restaurant", "food"),
        ("legal reforms and government policy changes", "law_government"),
        ("building software and writing good code", "tech"),
    ]
    for query, category in semantic:
        judgments.append({
            "query": query,
            "type": "semantic",
            "relevant_ids": _docs_in_category(docs, category),
        })

    return judgments


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def precision_at_k(ranked_ids: list, relevant_ids: set, k: int = K) -> float:
    top_k = ranked_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(top_k)


def mrr(ranked_ids: list, relevant_ids: set) -> float:
    for rank, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant_ids:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(ranked_ids: list, relevant_ids: set, k: int = K) -> float:
    top_k = ranked_ids[:k]
    dcg = sum(1.0 / math.log2(i + 2)
              for i, doc_id in enumerate(top_k) if doc_id in relevant_ids)
    ideal_hits = min(len(relevant_ids), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Search pipelines -- mirrors main.py's /search logic exactly for each mode
# ---------------------------------------------------------------------------

def search_bm25_only(query: str, ctx: dict) -> list:
    if validate_query(query):
        return []
    correction = correct_query(query, ctx["sym_spell"])
    if correction["unknown_words"]:  # same hard rejection main.py applies when rerank=False
        return []
    search_query = correction["corrected_query"] if correction["suggestions"] else query
    structured = parse_query(search_query)
    if not any([structured["required"], structured["optional"], structured["phrases"]]):
        return []
    candidate_ids = retrieve_candidates(structured, ctx["docs"], ctx["inverted_index"])
    scores = score_documents(candidate_ids, structured, ctx["inverted_index"],
                             ctx["doc_lengths"], ctx["avg_doc_length"], ctx["total_docs_count"],
                             ctx["pagerank_norm"])
    return sorted(candidate_ids, key=lambda d: (-scores[d], d))


def search_bm25_plus_semantic(query: str, ctx: dict) -> list:
    if validate_query(query):
        return []
    correction = correct_query(query, ctx["sym_spell"])
    # unknown-word rejection is bypassed for rerank=True, exactly as in main.py
    search_query = correction["corrected_query"] if correction["suggestions"] else query
    structured = parse_query(search_query)
    if not any([structured["required"], structured["optional"], structured["phrases"]]):
        # even semantic mode needs SOME parseable query shape; if truly nothing
        # parsed (e.g. pure stopwords), there's no candidate set at all to
        # rerank -- but augmentation can still run over an empty ranked_ids
        structured = {"required": [], "optional": [], "excluded": [],
                      "phrases": [], "excluded_phrases": []}
    candidate_ids = retrieve_candidates(structured, ctx["docs"], ctx["inverted_index"])
    scores = score_documents(candidate_ids, structured, ctx["inverted_index"],
                             ctx["doc_lengths"], ctx["avg_doc_length"], ctx["total_docs_count"],
                             ctx["pagerank_norm"])
    ranked_ids = sorted(candidate_ids, key=lambda d: (-scores[d], d))
    allow_augmentation = not (structured["required"] or structured["excluded"]
                             or structured["excluded_phrases"] or structured["phrases"])
    # embed the RAW query, not the spell-corrected one (see app/main.py's comment
    # on this exact point -- correction can turn a valid-but-out-of-vocabulary
    # word into an unrelated in-vocabulary one)
    new_ranked_ids, _ = semantic_rerank(
        query, ranked_ids, scores, ctx["semantic_model"], ctx["doc_embeddings"],
        ctx["doc_id_to_index"], ctx["embedding_doc_id_order"],
        allow_augmentation=allow_augmentation)
    return new_ranked_ids


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def build_context() -> dict:
    docs = load_corpus(CORPUS_PATH)
    inverted_index, doc_lengths, avg_doc_length, total_docs_count = build_index(docs)
    sym_spell = build_symspell(docs)
    link_graph = build_link_graph(docs)
    pagerank_norm = normalize_pagerank(compute_pagerank(link_graph))
    semantic_model = load_model()
    doc_embeddings, embedding_doc_id_order = build_doc_embeddings(docs, semantic_model)
    doc_id_to_index = {doc_id: i for i, doc_id in enumerate(embedding_doc_id_order)}
    return {
        "docs": docs, "inverted_index": inverted_index, "doc_lengths": doc_lengths,
        "avg_doc_length": avg_doc_length, "total_docs_count": total_docs_count,
        "sym_spell": sym_spell, "pagerank_norm": pagerank_norm,
        "semantic_model": semantic_model, "doc_embeddings": doc_embeddings,
        "doc_id_to_index": doc_id_to_index, "embedding_doc_id_order": embedding_doc_id_order,
    }


def run_evaluation():
    ctx = build_context()
    judgments = build_judgments(ctx["docs"])

    rows = []
    for judgment in judgments:
        query = judgment["query"]
        relevant_ids = judgment["relevant_ids"]

        bm25_ranked = search_bm25_only(query, ctx)
        semantic_ranked = search_bm25_plus_semantic(query, ctx)

        row = {
            "query": query,
            "type": judgment["type"],
            "num_relevant": len(relevant_ids),
            "bm25": {
                "precision_at_10": precision_at_k(bm25_ranked, relevant_ids),
                "mrr": mrr(bm25_ranked, relevant_ids),
                "ndcg_at_10": ndcg_at_k(bm25_ranked, relevant_ids),
                "num_results": len(bm25_ranked),
            },
            "semantic": {
                "precision_at_10": precision_at_k(semantic_ranked, relevant_ids),
                "mrr": mrr(semantic_ranked, relevant_ids),
                "ndcg_at_10": ndcg_at_k(semantic_ranked, relevant_ids),
                "num_results": len(semantic_ranked),
            },
        }
        rows.append(row)

    return rows


def summarize(rows: list) -> dict:
    def avg(rows_subset, method, metric):
        values = [r[method][metric] for r in rows_subset]
        return sum(values) / len(values) if values else 0.0

    subsets = {
        "overall": rows,
        "lexical": [r for r in rows if r["type"] == "lexical"],
        "semantic": [r for r in rows if r["type"] == "semantic"],
    }
    summary = {}
    for name, subset in subsets.items():
        summary[name] = {
            "bm25": {m: avg(subset, "bm25", m) for m in ["precision_at_10", "mrr", "ndcg_at_10"]},
            "semantic": {m: avg(subset, "semantic", m) for m in ["precision_at_10", "mrr", "ndcg_at_10"]},
        }
    return summary


def main():
    rows = run_evaluation()
    summary = summarize(rows)

    print(f"{'Query':<55} {'Type':<10} {'BM25 P@10':>10} {'Sem P@10':>10} {'BM25 MRR':>10} {'Sem MRR':>10} {'BM25 nDCG':>10} {'Sem nDCG':>10}")
    for r in rows:
        print(f"{r['query']:<55} {r['type']:<10} "
              f"{r['bm25']['precision_at_10']:>10.3f} {r['semantic']['precision_at_10']:>10.3f} "
              f"{r['bm25']['mrr']:>10.3f} {r['semantic']['mrr']:>10.3f} "
              f"{r['bm25']['ndcg_at_10']:>10.3f} {r['semantic']['ndcg_at_10']:>10.3f}")

    print()
    for name in ["overall", "lexical", "semantic"]:
        s = summary[name]
        print(f"--- {name} ---")
        print(f"  BM25-only:      P@10={s['bm25']['precision_at_10']:.3f}  MRR={s['bm25']['mrr']:.3f}  nDCG@10={s['bm25']['ndcg_at_10']:.3f}")
        print(f"  BM25+semantic:  P@10={s['semantic']['precision_at_10']:.3f}  MRR={s['semantic']['mrr']:.3f}  nDCG@10={s['semantic']['ndcg_at_10']:.3f}")

    out_path = Path(__file__).resolve().parent.parent / "data" / "evaluation_results.json"
    out_path.write_text(json.dumps({
        "rows": [{**r, "bm25": r["bm25"], "semantic": r["semantic"]} for r in rows],
        "summary": summary,
    }, indent=2, default=list))
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    main()
