"""AI/ML evaluation (SRS §11): dedup precision/recall/F1 + confusion matrix,
Precision@K for team matching, cluster purity. Computed live on the
labelled evaluation data in the database."""

from __future__ import annotations

from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import EvalPair, EvalRelevance, Problem, Team, ModelState
from . import cluster as cluster_mod
from . import embed, preprocess


def _problem_text(p: Problem, semantic: bool = False) -> str:
    return preprocess.doc_text(p.title, p.description, semantic)


def get_tuned_threshold(db: Session, fallback: float) -> float:
    row = db.get(ModelState, "dedup_threshold")
    if row and row.value:
        try:
            return float(row.value)
        except ValueError:
            pass
    return fallback


def set_tuned_threshold(db: Session, value: float):
    row = db.get(ModelState, "dedup_threshold")
    if row is None:
        row = ModelState(key="dedup_threshold", value=str(value))
        db.add(row)
    else:
        row.value = str(value)
    db.commit()


def dedup_evaluation(db: Session, threshold: float, embedder) -> dict:
    """Evaluate duplicate detection against labelled pairs.

    Uses the trained classifier (artifacts/dedup_model.joblib) when present —
    same model, threshold and features as the live pipeline — otherwise the
    classic cosine-threshold rule. `threshold` is the cosine fallback.
    """
    pairs = db.scalars(select(EvalPair)).all()
    problems = {p.id: p for p in db.scalars(select(Problem)).all()}
    if not pairs:
        return {"error": "no labelled evaluation pairs"}

    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    texts = [_problem_text(p, semantic) for p in problems.values()]
    matrix = embedder.transform(texts)
    order = list(problems.keys())
    idx = {pid: i for i, pid in enumerate(order)}

    from . import model_store

    artifact = model_store.load_dedup_artifact() if semantic else None
    if artifact is not None:
        import numpy as np

        from scripts.nlp_common import pair_features

        model = artifact["model"]
        thr = float(artifact["threshold"])
        cats = artifact.get("categories")
        raw = {pid: f"{p.title}. {p.description}" for pid, p in problems.items()}
        cat = {pid: p.category for pid, p in problems.items()}
        method = "trained_classifier"
    else:
        model, thr, cats, raw, cat = None, threshold, None, None, None
        method = "cosine_threshold"

    tp = fp = fn = tn = 0
    all_labels, all_scores = [], []
    examples = {"true_positives": [], "false_positives": [], "false_negatives": []}
    for pair in pairs:
        a, b = pair.problem_a_id, pair.problem_b_id
        if a not in idx or b not in idx:
            continue
        if model is not None:
            feat = pair_features(
                matrix[idx[a]], matrix[idx[b]], raw[a], raw[b],
                cat[a] or "", cat[b] or "", cats,
            )
            score = float(model.predict_proba(np.asarray([feat], dtype=np.float32))[0, 1])
        else:
            score = float(cosine_similarity(matrix[idx[a]][None, :], matrix[idx[b]][None, :])[0, 0])
        all_labels.append(1 if pair.is_duplicate else 0)
        all_scores.append(score)
        pred = score >= thr
        if pred and pair.is_duplicate:
            tp += 1
            examples["true_positives"].append({"a": a, "b": b, "score": round(score, 3)})
        elif pred:
            fp += 1
            examples["false_positives"].append({"a": a, "b": b, "score": round(score, 3)})
        elif pair.is_duplicate:
            fn += 1
            examples["false_negatives"].append({"a": a, "b": b, "score": round(score, 3)})
        else:
            tn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    out = {
        "method": method,
        "threshold": round(thr, 3),
        "pairs_evaluated": len(pairs),
        "confusion_matrix": {"TP": tp, "FP": fp, "FN": fn, "TN": tn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "examples": examples,
    }
    if len(set(all_labels)) > 1 and all_scores:
        from sklearn.metrics import roc_auc_score

        out["roc_auc"] = round(float(roc_auc_score(all_labels, all_scores)), 4)
    return out


def precision_at_k_evaluation(db: Session, embedder, k_values=(3, 5)) -> dict:
    """Precision@K for team recommendations against labelled relevant teams."""
    from . import matching

    problems = db.scalars(select(Problem)).all()
    pmap = {p.id: p for p in problems}
    rel_rows = db.scalars(select(EvalRelevance)).all()
    if not rel_rows:
        return {"error": "no labelled relevance data"}
    relevance: dict[int, set[int]] = {}
    for r in rel_rows:
        relevance.setdefault(r.problem_id, set()).add(r.team_id)

    teams = db.scalars(select(Team)).all()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    texts = [_problem_text(p, semantic) for p in pmap.values()]
    matrix = embedder.transform(texts)

    from . import model_store

    method = (
        "trained_ranker"
        if (model_store.load_ranker_artifact() is not None and semantic)
        else "weighted_formula"
    )
    results = {f"precision_at_{k}": [] for k in k_values}
    recall_results = {f"recall_at_{k}": [] for k in k_values}
    for pid, rel in relevance.items():
        p = pmap.get(pid)
        if not p:
            continue
        p_vec = matrix[list(pmap.keys()).index(pid)]
        recs = matching.recommend(p, list(teams), embedder, p_vec, k=max(k_values))
        for k in k_values:
            topk = {r["team_id"] for r in recs[:k]}
            hit = len(topk & rel)
            results[f"precision_at_{k}"].append(
                {"problem_id": pid, "relevant": len(rel), "hits": hit, "precision": round(hit / k, 4)}
            )
            recall_results[f"recall_at_{k}"].append(
                {"problem_id": pid, "relevant": len(rel), "hits": hit,
                 "recall": round(hit / max(len(rel), 1), 4)}
            )
    summary = {}
    rsummary = {}
    for k in k_values:
        vals = [v["precision"] for v in results[f"precision_at_{k}"]]
        summary[f"precision_at_{k}"] = round(sum(vals) / len(vals), 4) if vals else None
        rvals = [v["recall"] for v in recall_results[f"recall_at_{k}"]]
        rsummary[f"recall_at_{k}"] = round(sum(rvals) / len(rvals), 4) if rvals else None
    return {
        "method": method,
        "details": results,
        "recall_details": recall_results,
        "mean": summary,
        "mean_recall": rsummary,
    }


def clustering_evaluation(db: Session, embedder) -> dict:
    """Cluster purity using problem categories as ground truth."""
    problems = db.scalars(select(Problem)).all()
    if len(problems) < 6:
        return {"error": "not enough problems"}
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    texts = [_problem_text(p, semantic) for p in problems]
    matrix = embedder.transform(texts)
    labels, k, sil = cluster_mod.run_clustering(matrix)
    if labels is None:
        return {"error": "clustering not run (insufficient data)"}
    purity = cluster_mod.cluster_purity(labels, [p.category for p in problems])
    # intra-cluster category consistency table
    by_cluster: dict[int, dict[str, int]] = {}
    for lab, p in zip(labels, problems):
        by_cluster.setdefault(lab, {}).setdefault(p.category, 0)
        by_cluster[lab][p.category] += 1
    detail = {
        str(lab): {"size": sum(c.values()), "categories": c}
        for lab, c in sorted(by_cluster.items())
    }
    return {
        "clusters": k,
        "silhouette_score": round(sil, 4),
        "purity": round(purity, 4),
        "detail": detail,
    }


def run_full_evaluation(db: Session, threshold: float, embedder) -> dict:
    from . import model_store

    return {
        "embedder": embedder.name,
        "duplicate_detection": dedup_evaluation(db, threshold, embedder),
        "team_matching": precision_at_k_evaluation(db, embedder),
        "clustering": clustering_evaluation(db, embedder),
        "trained_models": model_store.model_summary(),
    }
