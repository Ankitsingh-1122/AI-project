"""Human labelling API for REAL ML training data.

Duplicate pairs and (problem, team) relevance rows are labelled ONLY by
human reviewers (admin role) through the "Data & Labels" admin UI. The
mined candidates come from real Chicago/NYC 311 records (scripts/label_mining.py);
the `source` column records which mining rule proposed a pair. No endpoint in
this module ever creates a label automatically.

Minimum label counts before a supervised model may be trained are
configuration values (app/config.py).
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import SessionLocal, get_db
from ..deps import require_role
from ..models import RealPair, RealProblem, RealRelevance, Team, User

router = APIRouter(prefix="/api/labels", tags=["labels"])


# ---- status ----------------------------------------------------------------

def label_status(db: Session) -> dict:
    """Human-labelling progress on the real dataset (also embedded in the
    admin /api/admin/model-performance response)."""
    pair_counts = {
        (src, label): n
        for src, label, n in db.execute(
            select(RealPair.source, RealPair.is_duplicate, func.count())
            .group_by(RealPair.source, RealPair.is_duplicate)
        ).all()
    }
    per_source: dict[str, dict] = {}
    for (src, label), n in pair_counts.items():
        d = per_source.setdefault(src, {"pending": 0, "labeled": 0})
        d["pending" if label is None else "labeled"] += n
    labeled = sum(n for (src, label), n in pair_counts.items() if label is not None)
    pending = sum(n for (src, label), n in pair_counts.items() if label is None)

    rel_total = db.scalar(select(func.count(RealRelevance.id))) or 0
    rel_labeled = db.scalar(select(func.count(RealRelevance.id)).where(RealRelevance.relevant.is_not(None))) or 0
    rel_problems = db.scalar(select(func.count(func.distinct(RealRelevance.problem_id)))) or 0

    from ..ml import model_store
    dedup_art = model_store.load_dedup_artifact()
    ranker_art = model_store.load_ranker_artifact()

    return {
        "pairs": {"total_pending": pending, "total_labeled": labeled, "per_source": per_source},
        "relevance": {
            "grid_rows": rel_total,
            "labeled_rows": rel_labeled,
            "problems_sampled": rel_problems,
        },
        "minima_for_training": {
            "dedup_pairs": settings.MIN_LABELS_DEDUP,
            "relevance_rows": settings.MIN_LABELS_RELEVANCE,
        },
        "ready_to_train": {
            "dedup": labeled >= settings.MIN_LABELS_DEDUP,
            "relevance": rel_labeled >= settings.MIN_LABELS_RELEVANCE,
        },
        "trained_models": {
            "dedup_classifier": bool(dedup_art),
            "team_ranker": bool(ranker_art),
        },
        "real_corpus_rows": db.scalar(select(func.count(RealProblem.id))) or 0,
    }


@router.get("/status")
def labels_status(db: Session = Depends(get_db), _: User = Depends(require_role("admin", "team"))):
    return label_status(db)


# ---- duplicate-pair review queue -------------------------------------------

def _pair_out(p: RealPair) -> dict:
    def prob(rp: RealProblem | None) -> dict:
        return {
            "id": rp.id, "source": rp.source, "source_id": rp.source_id,
            "date": rp.date, "category": rp.category, "title": rp.title,
            "text": rp.text, "location": rp.location,
            "duplicate_flag": rp.duplicate_flag,
        } if rp else {}
    return {
        "id": p.id,
        "source": p.source,
        "similarity": p.similarity,
        "is_duplicate": p.is_duplicate,
        "labeled_by": p.labeled_by,
        "labeled_at": p.labeled_at.isoformat() if p.labeled_at else None,
        "a": prob(p.problem_a),
        "b": prob(p.problem_b),
    }


@router.get("/pairs")
def list_pairs(
    source: str | None = None,
    labeled: str | None = None,  # 'pending' | 'labeled'
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    q = select(RealPair)
    if source:
        q = q.where(RealPair.source == source)
    if labeled == "labeled":
        q = q.where(RealPair.is_duplicate.is_not(None))
    elif labeled == "pending":
        q = q.where(RealPair.is_duplicate.is_(None))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(RealPair.id).limit(min(limit, 100)).offset(offset)).all()
    return {"total": total, "offset": offset, "limit": min(limit, 100), "pairs": [_pair_out(p) for p in rows]}


class PairLabelIn(BaseModel):
    is_duplicate: bool


@router.post("/pairs/{pair_id}")
def label_pair(
    pair_id: int,
    body: PairLabelIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    p = db.get(RealPair, pair_id)
    if p is None:
        raise HTTPException(404, "Pair not found")
    p.is_duplicate = body.is_duplicate
    p.labeled_by = user.id
    from ..models import utcnow
    p.labeled_at = utcnow()
    db.commit()
    return _pair_out(p)


@router.delete("/pairs/{pair_id}")
def delete_pair(pair_id: int, db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    p = db.get(RealPair, pair_id)
    if p is None:
        raise HTTPException(404, "Pair not found")
    db.delete(p)
    db.commit()
    return {"deleted": pair_id}


# ---- team-relevance labelling grid -----------------------------------------

@router.get("/relevance")
def list_relevance(
    status: str = "pending",  # pending | labeled | all
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Problems (with all their team rows) for the relevance grid."""
    problem_ids_q = select(RealRelevance.problem_id).distinct()
    if status == "pending":
        problem_ids_q = (
            select(RealRelevance.problem_id)
            .where(RealRelevance.relevant.is_(None))
            .distinct()
        )
    elif status == "labeled":
        problem_ids_q = (
            select(RealRelevance.problem_id)
            .where(RealRelevance.relevant.is_not(None))
            .distinct()
        )
    pid_rows = db.scalars(problem_ids_q.order_by(RealRelevance.problem_id)
                          .limit(min(limit, 100)).offset(offset)).all()
    teams = {t.id: t for t in db.scalars(select(Team)).all()}
    out = []
    for pid in pid_rows:
        prob = db.get(RealProblem, pid)
        if prob is None:
            continue
        rows = db.scalars(select(RealRelevance).where(RealRelevance.problem_id == pid)).all()
        out.append({
            "problem": {
                "id": prob.id, "source": prob.source, "source_id": prob.source_id,
                "date": prob.date, "category": prob.category, "title": prob.title,
                "text": prob.text, "location": prob.location,
            },
            "teams": [
                {
                    "team_id": r.team_id,
                    "team_name": teams[r.team_id].team_name if r.team_id in teams else "?",
                    "relevant": r.relevant,
                    "labeled_by": r.labeled_by,
                }
                for r in rows
            ],
        })
    return {"items": out, "offset": offset, "limit": min(limit, 100)}


class RelLabelIn(BaseModel):
    problem_id: int
    team_id: int
    relevant: int  # 0 or 1


@router.post("/relevance")
def label_relevance(
    body: RelLabelIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    if body.relevant not in (0, 1):
        raise HTTPException(422, "relevant must be 0 or 1")
    row = db.scalar(
        select(RealRelevance).where(
            RealRelevance.problem_id == body.problem_id,
            RealRelevance.team_id == body.team_id,
        )
    )
    if row is None:
        row = RealRelevance(problem_id=body.problem_id, team_id=body.team_id)
        db.add(row)
        db.flush()
    row.relevant = body.relevant
    row.labeled_by = user.id
    from ..models import utcnow
    row.labeled_at = utcnow()
    db.commit()
    return {"ok": True}


# ---- maintenance actions (admin) -------------------------------------------

class MineIn(BaseModel):
    pairs: int = 300
    relevance_problems: int = 60


@router.post("/mine")
def mine_candidates(body: MineIn, db: Session = Depends(get_db), _: User = Depends(require_role("admin"))):
    """(Re)run candidate mining + corpus upsert from data/real/corpus_all.csv."""
    from scripts import label_mining
    import os

    corpus = os.path.join(os.path.dirname(__file__), "..", "..", "data", "real", "corpus_all.csv")
    if not os.path.exists(corpus):
        raise HTTPException(400, "Real corpus not found — run scripts.ingest_real first")
    rows = label_mining.load_corpus()
    up = label_mining.upsert_problems(db, rows)
    stats = label_mining.mine_pairs(db, up["ids"], rows, body.pairs)
    n_rel = label_mining.sample_relevance(db, rows, up["ids"], body.relevance_problems)
    return {"problems_added": up["added"], "pairs_mined": stats, "relevance_rows_created": n_rel}


@router.post("/retrain")
def retrain(_: User = Depends(require_role("admin"))):
    """Train supervised models on the human labels collected so far.
    Refuses (400) if the minimum label counts are not met — no training on
    thin data, no fake metrics."""
    sdb = SessionLocal()
    try:
        labeled_pairs = sdb.scalar(
            select(func.count(RealPair.id)).where(RealPair.is_duplicate.is_not(None))) or 0
        labeled_rel = sdb.scalar(
            select(func.count(RealRelevance.id)).where(RealRelevance.relevant.is_not(None))) or 0
    finally:
        sdb.close()

    result: dict = {}
    if labeled_pairs >= settings.MIN_LABELS_DEDUP:
        from scripts import train_dedup
        t0 = time.time()
        train_dedup.main()
        result["dedup"] = {"trained": True, "seconds": round(time.time() - t0, 1)}
    else:
        result["dedup"] = {
            "trained": False,
            "reason": f"need {settings.MIN_LABELS_DEDUP} labelled pairs, have {labeled_pairs}",
        }
    if labeled_rel >= settings.MIN_LABELS_RELEVANCE:
        from scripts import train_ranker
        t0 = time.time()
        train_ranker.main()
        result["relevance"] = {"trained": True, "seconds": round(time.time() - t0, 1)}
    else:
        result["relevance"] = {
            "trained": False,
            "reason": f"need {settings.MIN_LABELS_RELEVANCE} labelled relevance rows, have {labeled_rel}",
        }
    return result
