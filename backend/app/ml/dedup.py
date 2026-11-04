"""Duplicate detection (SRS FR-05, 7.4) and experimental threshold tuning."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import pairwise as sk_pair


def nearest_scores(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarity of query vector against a matrix of (n, d) vectors."""
    if matrix.shape[0] == 0:
        return np.zeros(0, dtype=np.float32)
    return sk_pair.cosine_similarity(query[None, :], matrix)[0]


def pick_duplicates(
    ids: list[int],
    scores: np.ndarray,
    threshold: float,
    exclude_id: int | None = None,
) -> list[tuple[int, float]]:
    """Return (problem_id, score) pairs at/above threshold, best first."""
    out = []
    for pid, s in zip(ids, scores):
        if pid == exclude_id:
            continue
        if s >= threshold:
            out.append((int(pid), float(s)))
    out.sort(key=lambda x: -x[1])
    return out


def classifier_decisions(
    artifact: dict,
    query_vec: np.ndarray,
    query_raw_text: str,
    query_category: str,
    ids: list[int],
    matrix: np.ndarray,
    raw_texts: list[str],
    categories: list[str],
    top_n: int = 12,
    exclude_id: int | None = None,
) -> list[tuple[int, float, float]]:
    """Duplicate probabilities from the trained classifier.

    Candidates are the top_n nearest neighbours by cosine (the classifier
    only adds discriminative power among already-similar texts; this keeps
    serving fast). Returns [(problem_id, probability, cosine), ...] sorted
    by probability, best first.
    """
    from scripts.nlp_common import pair_features

    model = artifact["model"]
    cats = artifact.get("categories")
    cos = nearest_scores(query_vec, matrix)
    order = np.argsort(-cos)
    out: list[tuple[int, float, float]] = []
    for i in order:
        if ids[i] == exclude_id:
            continue
        feat = pair_features(
            query_vec, matrix[i],
            query_raw_text, raw_texts[i],
            query_category or "", categories[i] or "",
            cats,
        )
        prob = float(model.predict_proba(np.asarray([feat], dtype=np.float32))[0, 1])
        out.append((int(ids[i]), prob, float(cos[i])))
        if len(out) >= top_n:
            break
    out.sort(key=lambda x: -x[1])
    return out


def f1_from_counts(tp: int, fp: int, fn: int) -> float:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def tune_threshold(
    pair_scores: dict[tuple[int, int], float],
    labels: dict[tuple[int, int], bool],
) -> tuple[float, float]:
    """Pick the similarity threshold that maximizes F1 on labelled pairs.

    pair_scores: {(a, b): cosine}   labels: {(a, b): is_duplicate}
    Returns (threshold, best_f1).
    """
    candidates = np.round(np.arange(0.10, 0.98, 0.01), 2)
    best_thr, best_f1 = 0.75, -1.0
    for thr in candidates:
        tp = fp = fn = 0
        for key, label in labels.items():
            score = pair_scores.get(key)
            if score is None:
                continue
            pred = score >= thr
            if pred and label:
                tp += 1
            elif pred and not label:
                fp += 1
            elif not pred and label:
                fn += 1
        f1 = f1_from_counts(tp, fp, fn)
        if f1 > best_f1:
            best_f1, best_thr = f1, float(thr)
    return best_thr, best_f1
