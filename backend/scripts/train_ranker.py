"""Team-matching ranker on HUMAN-LABELLED real data.

Label source: the `real_relevance` table — real Chicago/NYC 311 problems
(scripts/label_mining.py samples them) paired with the app's student teams,
where a human reviewer marked each (problem, team) row relevant (1) or not (0)
via the admin "Data & Labels" UI. No label is ever generated automatically.
The old category->team rule mapping is GONE as a label source.

Teams: the live teams from the app database (real team profiles), embedded
the same way at serving time (app/ml/matching.py + nlp_common.ranker_features).

Leakage control: 70/15/15 grouped by problem — every (problem, team) row of a
problem stays in ONE split, so a problem is never ranked in two splits.

Metrics on TEST only: ROC-AUC (all rows) + Precision@K / Recall@K computed
per problem on problems where ALL of their team rows are labelled (complete
problems); the count of complete problems is reported.

Refuses to run below app/config.py MIN_LABELS_RELEVANCE labelled rows.

Artifacts: artifacts/ranker.joblib + artifacts/ranker_metrics.json
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
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from app.config import settings
from app.database import SessionLocal
from app.models import RealProblem, RealRelevance, Team

from sqlalchemy import select

from . import nlp_common as nc
from .nlp_common import save_json, st, team_profile_parts

FEAT_NAMES = nc.RANKER_FEATURE_NAMES


def main() -> None:
    t0 = time.time()
    db = SessionLocal()
    try:
        teams = {t.id: t for t in db.scalars(select(Team).order_by(Team.id)).all()}
        rows = db.scalars(
            select(RealRelevance).where(RealRelevance.relevant.is_not(None))
        ).all()
        problems = {}
        for r in rows:
            if r.problem_id not in problems:
                problems[r.problem_id] = db.get(RealProblem, r.problem_id)
    finally:
        db.close()

    if len(rows) < settings.MIN_LABELS_RELEVANCE:
        raise SystemExit(
            f"REFUSED: only {len(rows)} human-labelled relevance rows; "
            f"need >= {settings.MIN_LABELS_RELEVANCE} (admin 'Data & Labels' -> Team relevance)"
        )
    if len(teams) == 0 or len(problems) == 0:
        raise SystemExit("REFUSED: no teams or no labelled problems found")
    pos = sum(1 for r in rows if r.relevant == 1)
    print(f"labeled rows: {len(rows)} (relevant {pos} / not {len(rows)-pos}) "
          f"across {len(problems)} problems x {len(teams)} teams")

    # ---- features (exactly the serving-time definitions) ----
    p_texts = {pid: p.text for pid, p in problems.items() if p}
    p_vecs = {pid: v for pid, v in zip(p_texts, st.encode(list(p_texts.values()), tag="real_rel_problems"))}
    t_parts = {
        tid: team_profile_parts(t.team_name, t.description, t.skills_list,
                                t.interests_list, t.experience)
        for tid, t in teams.items()
    }
    t_texts = {tid: (full if full.strip() else "empty") for tid, (full, _sd) in t_parts.items()}
    t_vecs = {tid: v for tid, v in zip(t_texts, st.encode(list(t_texts.values()), tag="real_rel_teams"))}

    X, y, groups = [], [], []
    for r in rows:
        p = problems.get(r.problem_id)
        t = teams.get(r.team_id)
        if p is None or t is None:
            continue
        full, sd = t_parts[r.team_id]
        f = nc.ranker_features(p.text, full, sd, t.experience or "",
                               p_vecs[p.id], t_vecs[r.team_id])
        X.append(f)
        y.append(int(r.relevant))
        groups.append(r.problem_id)

    X = np.asarray(X, dtype=np.float32)
    y = np.asarray(y)
    if len(set(y.tolist())) < 2:
        raise SystemExit("REFUSED: labelled rows contain only one class")

    # ---- grouped 70/15/15 by problem (no leakage) ----
    uniq = list(dict.fromkeys(groups))
    gss1 = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=42)
    tr_g, tmp_g = next(gss1.split(uniq, groups=uniq))
    tmp_set = [uniq[i] for i in tmp_g]
    gss2 = GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=42)
    val_i, te_i = next(gss2.split(tmp_set, groups=tmp_set))
    split_of = {}
    for i in tr_g:
        split_of[uniq[i]] = "train"
    for i in val_i:
        split_of[tmp_set[i]] = "val"
    for i in te_i:
        split_of[tmp_set[i]] = "test"
    idx = {"train": [], "val": [], "test": []}
    for i, g in enumerate(groups):
        idx[split_of[g]].append(i)
    print(f"split: train {len(idx['train'])} / val {len(idx['val'])} / test {len(idx['test'])} rows")

    Xtr, ytr = X[idx["train"]], y[idx["train"]]
    Xva, yva = X[idx["val"]], y[idx["val"]]
    Xte, yte = X[idx["test"]], y[idx["test"]]
    if len(Xtr) < 30 or len(Xte) < 10:
        raise SystemExit(f"REFUSED: split too small (train {len(Xtr)}, test {len(Xte)})")

    scaler = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=2000, C=1.0)
    lr.fit(scaler.transform(Xtr), ytr)
    lr_va = float(roc_auc_score(yva, lr.predict_proba(scaler.transform(Xva))[:, 1]))

    hgb = HistGradientBoostingClassifier(learning_rate=0.05, max_iter=200,
                                         max_depth=3, l2_regularization=1.0,
                                         random_state=42)
    hgb.fit(Xtr, ytr)
    hgb_va = float(roc_auc_score(yva, hgb.predict_proba(Xva)[:, 1]))

    best_name = "logreg" if lr_va >= hgb_va else "hgb"
    model = lr if best_name == "logreg" else hgb
    use_scaler = best_name == "logreg"

    def proba(Xm):
        return model.predict_proba(scaler.transform(Xm) if use_scaler else Xm)[:, 1]

    test_scores = proba(Xte)
    te_groups = [groups[i] for i in idx["test"]]

    # ---- P@K / R@K on COMPLETE test problems (all team rows labelled) ----
    def rank_metrics():
        by_prob: dict[int, list] = {}
        for sc, lab, gid in zip(test_scores, yte, te_groups):
            by_prob.setdefault(gid, []).append((float(sc), int(lab)))
        # completeness: problems whose labelled rows in test == all teams
        n_teams = len(teams)
        p_at = {k: [] for k in (1, 3, 5)}
        r_at = {k: [] for k in (1, 3, 5)}
        n_complete = 0
        for gid, entries in by_prob.items():
            if len(entries) < n_teams:
                continue
            n_complete += 1
            ranked = sorted(entries, key=lambda e: -e[0])
            n_rel = sum(1 for e in ranked if e[1] == 1)
            for k in (1, 3, 5):
                hits = sum(1 for e in ranked[:k] if e[1] == 1)
                p_at[k].append(hits / k)
                r_at[k].append(hits / max(n_rel, 1))
        mean = lambda xs: round(float(np.mean(xs)), 4) if xs else None
        return {
            "n_complete_problems": n_complete,
            "precision_at": {str(k): mean(v) for k, v in p_at.items()},
            "recall_at": {str(k): mean(v) for k, v in r_at.items()},
        }

    rk = rank_metrics()
    if use_scaler:
        weights = {n: round(float(c), 4) for n, c in zip(FEAT_NAMES, model.coef_[0])}
        weights_key = "learned_weights"
    else:
        from sklearn.inspection import permutation_importance
        imp = permutation_importance(model, Xva, yva, n_repeats=10,
                                     random_state=42, scoring="roc_auc")
        weights = {n: round(float(v), 4) for n, v in zip(FEAT_NAMES, imp.importances_mean)}
        weights_key = "permutation_importance"

    metrics = {
        "model": best_name,
        "candidates_val_auc": {"logreg": round(lr_va, 4), "hgb": round(hgb_va, 4)},
        "n_test_rows": int(len(yte)),
        "n_test_problems": len(set(te_groups)),
        "auc": round(float(roc_auc_score(yte, test_scores)), 4),
        "precision_at": rk["precision_at"],
        "recall_at": rk["recall_at"],
        "complete_problems_note": f"P@K/R@K over test problems where all {len(teams)} team rows are labelled ({rk['n_complete_problems']} problems)",
        weights_key: weights,
        "features": FEAT_NAMES,
        "train_seconds": round(time.time() - t0, 1),
        "split": "70/15/15 grouped by problem (all team rows of a problem in one split)",
        "dataset": f"REAL Chicago/NYC 311 problems x app student teams, "
                   f"human-labelled relevance rows (n={len(rows)}, "
                   f"relevant {pos}) — see data/real/provenance.md",
        "label_provenance": "every label entered by a human reviewer via the admin "
                            "Data & Labels UI (real_relevance table); the old "
                            "category->team rule mapping is no longer used as labels",
    }

    os.makedirs(os.path.join(os.path.dirname(__file__), "..", "artifacts"), exist_ok=True)
    save_json("ranker_metrics.json", metrics)
    joblib.dump({"model": model, "scaler": scaler if use_scaler else None,
                 "features": FEAT_NAMES, "model_name": best_name},
                os.path.join(os.path.dirname(__file__), "..", "artifacts", "ranker.joblib"))
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
