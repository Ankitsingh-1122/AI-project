"""Clustering (SRS FR-07, 7.5).

Method + parameters come from the trained selection in
artifacts/cluster_config.json (see scripts/cluster_compare.py: K-Means vs
DBSCAN, chosen by measured Adjusted Rand Index). Without an artifact, falls
back to the original silhouette-based K-Means k search.

Label convention: -1 = noise (DBSCAN only); the pipeline turns it into an
"Unassigned" cluster so every problem keeps a cluster_id.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score

from . import model_store


def pick_k(matrix: np.ndarray, k_min: int = 2, k_max: int = 8) -> int:
    n = matrix.shape[0]
    hi = min(k_max, n // 2)
    if hi < k_min:
        return k_min
    best_k, best_score = k_min, -2.0
    for k in range(k_min, hi + 1):
        try:
            labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(matrix)
        except ValueError:
            continue
        if len(set(labels)) < 2:
            continue
        s = silhouette_score(matrix, labels)
        if s > best_score:
            best_k, best_score = k, s
    return best_k


def _silhouette(matrix: np.ndarray, labels: np.ndarray) -> float:
    non_noise = np.array([i for i, l in enumerate(labels) if l != -1])
    if len(non_noise) > 2 and len(set(labels[non_noise].tolist())) > 1:
        return float(silhouette_score(matrix[non_noise], labels[non_noise]))
    return 0.0


def run_clustering(matrix: np.ndarray) -> tuple[list[int] | None, int, float]:
    """Returns (labels or None, chosen_k, silhouette_score).

    Returns (None, 1, 0.0) when there is not enough data to cluster.
    """
    n = matrix.shape[0]
    if n < 6:
        return None, 1, 0.0

    cfg = model_store.load_cluster_config()

    if cfg and cfg.get("selected") == "dbscan":
        db = cfg.get("dbscan") or {}
        eps = float(db.get("eps", 0.3))
        min_samples = int(db.get("min_samples", 5))
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(matrix)
        k = int(len({l for l in labels if l != -1}))
        return [int(l) for l in labels], max(k, 1), _silhouette(matrix, labels)

    if cfg and cfg.get("selected") == "kmeans":
        k = int((cfg.get("kmeans") or {}).get("k", 8))
        k = max(2, min(k, max(2, n // 2)))
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(matrix)
        return labels.tolist(), k, float(silhouette_score(matrix, labels)) if n > k else 0.0

    # Fallback (no artifact): original silhouette-based k search.
    k = pick_k(matrix)
    if k < 2:
        return None, 1, 0.0
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(matrix)
    score = float(silhouette_score(matrix, labels)) if n > k else 0.0
    return labels.tolist(), k, score


def cluster_purity(labels: list[int], true_categories: list[str]) -> float:
    """Cluster purity (§11.5): for each cluster, majority category share."""
    if not labels:
        return 0.0
    by_cluster: dict[int, list[str]] = {}
    for lab, cat in zip(labels, true_categories):
        by_cluster.setdefault(lab, []).append(cat)
    correct = 0
    total = 0
    for members in by_cluster.values():
        counts: dict[str, int] = {}
        for c in members:
            counts[c] = counts.get(c, 0) + 1
        correct += max(counts.values())
        total += len(members)
    return correct / total if total else 0.0
