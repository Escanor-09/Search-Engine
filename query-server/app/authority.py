# graph library; gives us a ready-made, well-tested pagerank() implementation
import networkx as nx

# Builds the link graph from each doc's "links" field and computes a PageRank authority score per doc.
# Kept in its own module (not folded into ranking.py) so this whole step is easy to swap out or delay --
# per the Phase 3 note: a slow/missing crawler component shouldn't block BM25 or anything else.


# turns {doc_id: {..., "links": [id, id, ...]}} into a directed graph: doc_id -> each id it links to
def build_link_graph(docs: dict) -> nx.DiGraph:
    graph = nx.DiGraph()
    # add every doc as a node up front, even ones with zero in-links or out-links -- otherwise a doc
    # that nothing points to and that points to nothing would never appear in the graph at all
    graph.add_nodes_from(docs.keys())
    for doc_id, doc in docs.items():  # walk every document
        for target_id in doc.get("links", []):  # walk every doc it links out to
            # a directed edge: doc_id "vouches for" target_id
            graph.add_edge(doc_id, target_id)
    return graph  # ready for nx.pagerank()


# runs networkx's PageRank over the graph; returns {doc_id: raw_score}, scores sum to 1 across all docs
def compute_pagerank(graph: nx.DiGraph) -> dict:
    # uses the standard damping factor (0.85) and default convergence settings
    return nx.pagerank(graph)


# min-max scales raw PageRank scores into 0..1, so they're on a comparable scale to normalized BM25
# scores before ranking.py combines the two -- without this, PageRank's tiny raw values (~1/100) would
# be swamped by BM25's larger raw values regardless of the weight we assign
def normalize_pagerank(pagerank_scores: dict) -> dict:
    # empty graph (shouldn't happen with a real corpus, but don't divide by zero)
    if not pagerank_scores:
        return {}
    values = pagerank_scores.values()
    lo, hi = min(values), max(values)
    span = hi - lo
    # every doc has identical authority (e.g. a graph with no links at all)
    if span == 0:
        # nothing to differentiate, treat all as equal
        return {doc_id: 1.0 for doc_id in pagerank_scores}
    return {doc_id: (score - lo) / span for doc_id, score in pagerank_scores.items()}
