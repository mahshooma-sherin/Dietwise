"""Variety: Maximal Marginal Relevance (MMR) over recipe-to-recipe TF-IDF cosine similarity.

Each pick maximises  lambda * relevance - (1 - lambda) * (max similarity to anything already picked),
so the candidate pool handed to the optimizer is relevant but not a pile of near-identical dishes.
"""
from __future__ import annotations

import numpy as np


def mmr(relevance: np.ndarray, sim: np.ndarray, k: int, lam: float = 0.7) -> list:
    n = len(relevance)
    k = min(k, n)
    rel = (relevance - relevance.min()) / (np.ptp(relevance) + 1e-9)
    selected: list = []
    remaining = list(range(n))
    while len(selected) < k:
        best, best_val = None, -1e9
        for j in remaining:
            redundancy = max((sim[j, s] for s in selected), default=0.0)
            val = lam * rel[j] - (1 - lam) * redundancy
            if val > best_val:
                best, best_val = j, val
        selected.append(best)
        remaining.remove(best)
    return selected


def mean_pairwise_distance(sim_sub: np.ndarray) -> float:
    """Average (1 - cosine similarity) over distinct pairs; higher = more varied."""
    n = len(sim_sub)
    if n < 2:
        return 0.0
    iu = np.triu_indices(n, k=1)
    return float(np.mean(1.0 - sim_sub[iu]))
