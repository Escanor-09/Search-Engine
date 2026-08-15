"""Standalone PageRank pass over crawler.db's `links` table.

Run once after a crawl finishes: `.venv/bin/python crawler/ranking/pagerank.py`.
Not part of the live crawl pipeline — reads `links`, writes a `pagerank(url, score)`
table back into the same database for downstream consumers to join on.
"""

import logging
import os
import sqlite3
import sys

import numpy as np
import scipy.sparse as sp

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logging.basicConfig(level=config.LOG_LEVEL)
logger = logging.getLogger(__name__)

DAMPING = 0.85
MAX_ITERATIONS = 30
CONVERGENCE_THRESHOLD = 1e-6


def load_edges(conn):
    cursor = conn.execute("SELECT from_url, to_url FROM links")
    return cursor.fetchall()


def build_graph(edges):
    """Map every URL seen as either endpoint to an index; build a CSR out-link matrix."""
    urls = set()
    for from_url, to_url in edges:
        urls.add(from_url)
        urls.add(to_url)

    url_to_idx = {url: i for i, url in enumerate(sorted(urls))}
    n = len(url_to_idx)

    rows = [url_to_idx[from_url] for from_url, _ in edges]
    cols = [url_to_idx[to_url] for _, to_url in edges]
    data = np.ones(len(edges), dtype=np.float64)
    adjacency = sp.csr_matrix((data, (rows, cols)), shape=(n, n))

    return url_to_idx, adjacency


def power_iteration(adjacency):
    n = adjacency.shape[0]
    out_degree = np.asarray(adjacency.sum(axis=1)).flatten()

    dangling_mask = out_degree == 0
    safe_out_degree = np.where(dangling_mask, 1.0, out_degree)

    # Row-normalize so each row sums to 1 (a column-stochastic transpose used below).
    transition = adjacency.multiply(1.0 / safe_out_degree[:, None]).tocsr()

    rank = np.full(n, 1.0 / n, dtype=np.float64)
    teleport = (1.0 - DAMPING) / n

    for iteration in range(1, MAX_ITERATIONS + 1):
        dangling_mass = rank[dangling_mask].sum()
        # transition.T @ rank == sum over inbound neighbours of rank(v) / outdegree(v)
        new_rank = teleport + DAMPING * (transition.T @ rank + dangling_mass / n)

        delta = np.abs(new_rank - rank).sum()
        rank = new_rank
        logger.info(f"iteration {iteration}: L1 delta = {delta:.2e}")
        if delta < CONVERGENCE_THRESHOLD:
            break

    return rank


def save_scores(conn, url_to_idx, rank):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS pagerank (url TEXT PRIMARY KEY, score REAL NOT NULL)"
    )
    conn.executemany(
        "INSERT OR REPLACE INTO pagerank (url, score) VALUES (?,?)",
        [(url, float(rank[idx])) for url, idx in url_to_idx.items()],
    )
    conn.commit()


def main():
    conn = sqlite3.connect(config.DB_PATH)
    try:
        edges = load_edges(conn)
        if not edges:
            logger.warning("No rows in `links` — nothing to rank.")
            return

        url_to_idx, adjacency = build_graph(edges)
        logger.info(f"graph: {len(url_to_idx)} nodes, {len(edges)} edges")

        rank = power_iteration(adjacency)

        total = rank.sum()
        assert abs(total - 1.0) < 1e-6, f"PageRank scores should sum to 1.0, got {total}"
        logger.info(f"score sum = {total:.6f}")

        idx_to_url = {idx: url for url, idx in url_to_idx.items()}
        top = np.argsort(rank)[::-1][:10]
        logger.info("top 10 by PageRank:")
        for idx in top:
            logger.info(f"  {rank[idx]:.6e}  {idx_to_url[idx]}")

        save_scores(conn, url_to_idx, rank)
        logger.info(f"wrote {len(url_to_idx)} rows to `pagerank`")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
