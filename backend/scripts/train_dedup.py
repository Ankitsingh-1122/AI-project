"""Supervised duplicate-detection classifier on HUMAN-LABELLED real data.

Label source: the `real_pairs` table — candidate pairs mined from REAL
Chicago/NYC 311 service requests (scripts/label_mining.py) that a human
reviewer marked as duplicate / not-duplicate through the admin "Data &
Labels" UI. No label is ever generated automatically.

Leakage control: problems are grouped into (source, category, street)
buckets; every bucket is assigned wholesale to ONE of train/val/test
(70/15/15). A pair is usable only when BOTH of its buckets landed in the
same split — so no real problem ever appears in two splits.

Features: the same 7 fit-free features used at serving time
(cosine, L2, Porter unigram/bigram Jaccard, length ratio/delta,
same-category). No category one-hot (real data has 200+ city categories).

Selection: HistGradientBoosting grid + logistic-regression baseline,
chosen by VALIDATION ROC-AUC; the decision threshold comes from the
validation precision-recall curve. Final metrics are computed on TEST only.

Refuses to run below app/config.py MIN_LABELS_DEDUP labelled pairs or if
one class is missing — no training on thin data, no fake metrics.

Artifacts: artifacts/dedup_model.joblib + artifacts/dedup_metrics.json
(same shape as before, so the serving code is unchanged).
"""
from __future__ import annotations

import json
import os
import time

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_recall_curve,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.database import SessionLocal
from app.models import RealPair, RealProblem

from .nlp_common import pair_features, save_json, st

ART = os.path.join(os.path.dirname(__file__), "..", "artifacts")

FEATURE_NAMES = ["cos_sim", "cos_dist", "uni_jaccard", "bi_jaccard",
                 "len_ratio", "len_delta", "cat_eq"]


def _bucket(p: RealProblem) -> str:
    street = (p.location or "").strip().upper()
    return f"{p.source}|{p.category}|{street}"


def _load_labeled():
    db = SessionLocal()
    try:
        pairs = db.scalars(select_labeled_pairs()).all()
        probs = {}
        for p in pairs:
            for pid in (p.problem_a_id, p.problem_b_id):
                if pid not in probs:
                    probs[pid] = db.get(RealProblem, pid)
        return [(p, probs[p.problem_a_id], probs[p.problem_b_id]) for p in pairs]
    finally:
        db.close()


def select_labeled_pairs():
    from sqlalchemy import select
    return select(RealPair).where(RealPair.is_duplicate.is_not(None))


def _split_by_bucket(items: list, random_state: int = 42):
    """Assign each problem's (source, category, street) bucket to one split;
    return per-item split or None (cross-bucket pairs are dropped)."""
    from collections import defaultdict

    bucket_of = {}
    for p, a, b in items:
        bucket_of[p.problem_a_id] = _bucket(a)
        bucket_of[p.problem_b_id] = _bucket(b)
    buckets = sorted(set(bucket_of.values()))
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=random_state)
    tr_b, tmp_b = next(gss1.split(buckets, groups=buckets))
    tmp_set = set(buckets[i] for i in tmp_b)
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=random_state)
    val_i, te_i = next(gss2.split(list(tmp_set), groups=list(tmp_set)))
    split = {}
    for i in tr_b:
        split[buckets[i]] = "train"
    for i in val_i:
        split[list(tmp_set)[i]] = "val"
    for i in te_i:
        split[list(tmp_set)[i]] = "test"

    out = {"train": [], "val": [], "test": []}
    dropped = 0
    for p, a, b in items:
        sa, sb = split[bucket_of[p.problem_a_id]], split[bucket_of[p.problem_b_id]]
        if sa != sb:
            dropped += 1
            continue
        out[sa].append((p, a, b))
    return out, dropped


def main() -> None:
    t0 = time.time()
    items = _load_labeled()
    if len(items) < settings.MIN_LABELS_DEDUP:
        raise SystemExit(
            f"REFUSED: only {len(items)} human-labelled pairs; "
            f"need >= {settings.MIN_LABELS_DEDUP} (admin 'Data & Labels' -> Duplicate review)"
        )
    labels = {p.id: (1 if p.is_duplicate else 0) for p, _, _ in items}
    pos = sum(labels.values())
    if pos == 0 or pos == len(labels):
        raise SystemExit("REFUSED: labelled pairs contain only one class")

    splits, dropped = _split_by_bucket(items)
    if len(splits["train"]) < 30 or len(splits["test"]) < 10:
        raise SystemExit(
            f"REFUSED: after bucket-safe splitting train={len(splits['train'])} "
            f"test={len(splits['test'])} — label more pairs"
        )
    print(f"labeled pairs: {len(items)} (dup {pos} / non-dup {len(items)-pos}) | "
          f"dropped cross-bucket pairs: {dropped} | "
          f"train {len(splits['train'])} / val {len(splits['val'])} / test {len(splits['test'])}")

    def build(split_items, emb):
        X, y = [], []
        for p, a, b in split_items:
            ta, tb = a.text, b.text
            X.append(pair_features(emb[a.id], emb[b.id], ta, tb,
                                   a.category, b.category, cats=[]))
            y.append(labels[p.id])
        return np.asarray(X, dtype=np.float32), np.asarray(y)

    all_probs = {}
    for key in splits:
        for p, a, b in splits[key]:
            all_probs[a.id] = a
            all_probs[b.id] = b
    unique_texts = {pid: pr.text for pid, pr in all_probs.items()}
    emb = {pid: v for pid, v in zip(unique_texts, st.encode(list(unique_texts.values()), tag="real_pairs"))}

    Xtr, ytr = build(splits["train"], emb)
    Xval, yval = build(splits["val"], emb) if splits["val"] else (np.zeros((0, 7), np.float32), np.zeros(0, int))
    Xte, yte = build(splits["test"], emb)

    candidates = {
        "logreg": make_pipeline(StandardScaler(),
                                LogisticRegression(max_iter=2000, class_weight="balanced")),
    }
    grid = {
        "hgb": [
            dict(learning_rate=0.05, max_iter=200, l2_regularization=1.0, max_depth=3),
            dict(learning_rate=0.1, max_iter=300, l2_regularization=1.0, max_depth=None),
            dict(learning_rate=0.1, max_iter=300, l2_regularization=10.0, max_depth=3),
            dict(learning_rate=0.15, max_iter=400, l2_regularization=1.0, max_depth=None),
        ],
    }
    for params in grid["hgb"]:
        import copy
        m = copy.deepcopy(HistGradientBoostingClassifier(random_state=42))
        m.set_params(**params)
        candidates[f"hgb_{params['learning_rate']}_{params['max_depth']}"] = m

    best = None
    for name, model in candidates.items():
        model.fit(Xtr, ytr)
        pval = model.predict_proba(Xval)[:, 1]
        auc = float(roc_auc_score(yval, pval)) if len(set(yval.tolist())) > 1 else 0.0
        if best is None or auc > best["val_auc"]:
            best = {"name": name, "model": model, "val_auc": auc}
    model = best["model"]
    print(f"selected: {best['name']} (val AUC {best['val_auc']:.4f})")

    pval = model.predict_proba(Xval)[:, 1]
    pte = model.predict_proba(Xte)[:, 1]
    thr = _threshold(yval, pval)
    pred = (pte >= thr).astype(int)
    cm = confusion_matrix(yte, pred, labels=[0, 1]).ravel()

    res = {
        "model": best["name"],
        "threshold": round(thr, 4),
        "val_auc": round(best["val_auc"], 4),
        "test": {
            "precision": round(precision_score(yte, pred, zero_division=0), 4),
            "recall": round(recall_score(yte, pred, zero_division=0), 4),
            "f1": round(f1_score(yte, pred, zero_division=0), 4),
            "accuracy": round(accuracy_score(yte, pred), 4),
            "roc_auc": round(float(roc_auc_score(yte, pte)), 4),
            "confusion": {"TP": int(cm[3]), "FP": int(cm[2]), "FN": int(cm[1]), "TN": int(cm[0])},
        },
        "train_seconds": round(time.time() - t0, 1),
        "split": "70/15/15 assigned at (source, category, street) bucket level; "
                 "cross-bucket pairs dropped (no problem in two splits)",
        "dataset": f"REAL Chicago/NYC 311, human-labelled pairs "
                   f"(n={len(items)}; dup {pos} / non-dup {len(items)-pos}; "
                   f"dropped cross-bucket {dropped}) — see data/real/provenance.md",
        "label_provenance": "every label entered by a human reviewer via the admin "
                            "Data & Labels UI (real_pairs table); no automatic labelling",
    }

    joblib.dump({
        "model": model,
        "model_name": best["name"],
        "params": model.get_params(),
        "features": FEATURE_NAMES,
        "threshold": thr,
        "categories": [],  # serving builds the same 7-feature vector with cats=[]
        "metrics": res["test"],
        "val_auc": res["val_auc"],
    }, os.path.join(ART, "dedup_model.joblib"))
    save_json("dedup_metrics.json", res)
    print(json.dumps(res, indent=2))


def _threshold(y_true, scores) -> float:
    if len(set(y_true.tolist())) < 2:
        return float(np.median(scores))
    precision, recall, thr = precision_recall_curve(y_true, scores)
    n = min(len(precision), len(thr))
    precision, recall, thr = precision[:n], recall[:n], thr[:n]
    if n == 0:
        return float(np.median(scores))
    f1 = 2 * precision * recall / np.clip(precision + recall, 1e-9, None)
    f1[thr == 0] = 0
    return float(thr[int(np.argmax(f1))])


if __name__ == "__main__":
    main()
