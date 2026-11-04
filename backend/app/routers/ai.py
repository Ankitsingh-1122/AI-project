from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import Match, Problem, ProblemCluster, Team, User
from ..ml import preprocess
from ..ml.embed import get_shared_embedder
from ..ml import dedup as dedup_mod, evaluate
from ..pipeline import _with_cache, invalidate_cache, analyze_problem, public_result
from ..schemas import CheckDuplicateIn
from ..routers.problems import problem_out, recs_out
import json

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/analysis/{problem_id}")
def analysis_detail(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    k: int = Query(default=5, ge=1, le=20),
):
    """Full transparency view of the NLP/ML pipeline for one problem:
    preprocessed tokens, top keywords, embedder, tuned threshold,
    similarity scores, cluster, and team score breakdowns."""
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if user.role not in ("admin", "team") and p.user_id != user.id:
        raise HTTPException(403, "Not your problem")

    embedder = get_shared_embedder()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    doc = preprocess.doc_text(p.title, p.description, semantic)
    # NLP pipeline output (stop-words removed) for display; the embedder
    # itself consumes `doc` (light cleaning only, for semantic models).
    pipeline_tokens = preprocess.process(f"{p.title}. {p.description}").split()
    top_keywords = embedder.top_terms(doc, 10)
    threshold = evaluate.get_tuned_threshold(db, settings.DEDUP_THRESHOLD)

    from ..routers.problems import similar_out

    similar = similar_out(db, p, embedder, k=k)

    matches = []
    for m in db.scalars(
        select(Match).where(Match.problem_id == p.id).order_by(Match.ranking)
    ).all():
        team = db.get(Team, m.team_id)
        try:
            expl = json.loads(m.explanation or "{}")
        except json.JSONDecodeError:
            expl = {}
        matches.append(
            {
                "match_id": m.id,
                "team_id": m.team_id,
                "team_name": team.team_name if team else "?",
                "score": m.similarity_score,
                "ranking": m.ranking,
                "status": m.status,
                "breakdown": {
                    "text_similarity": expl.get("text_similarity"),
                    "keyword_coverage": expl.get("keyword_coverage"),
                    "experience_bonus": expl.get("experience_bonus"),
                    "model_score": expl.get("model_score"),
                    "formula_score": expl.get("formula_score"),
                },
                "scoring_model": expl.get("scoring_model"),
                "matched_keywords": expl.get("matched_keywords", []),
                "team_skills": expl.get("team_skills", []),
                "reason": expl.get("reason", ""),
            }
        )

    cluster = None
    if p.cluster_id:
        c = db.get(ProblemCluster, p.cluster_id)
        if c:
            member_ids = db.scalars(select(Problem.id).where(Problem.cluster_id == c.id)).all()
            cluster = {"id": c.id, "name": c.name, "size": len(member_ids)}

    from ..ml import model_store

    artifact = model_store.load_dedup_artifact() if semantic else None
    dup_method = "trained_classifier" if artifact else "cosine_threshold"
    dup_probability = None
    if artifact is not None:
        ids2, matrix2, _texts2, pmap2 = _with_cache(db, embedder)
        raw_texts2 = [f"{pm.title}. {pm.description}" for pm in pmap2.values()]
        cats2 = [pm.category for pm in pmap2.values()]
        cands2 = dedup_mod.classifier_decisions(
            artifact, matrix2[ids2.index(p.id)], f"{p.title}. {p.description}",
            p.category, ids2, matrix2, raw_texts2, cats2, top_n=12, exclude_id=p.id,
        )
        if cands2:
            dup_probability = round(cands2[0][1], 4)

    return {
        "problem_id": p.id,
        "embedder": embedder.name,
        "sentence_model": "sentence-transformers/all-MiniLM-L6-v2" if semantic else None,
        "threshold": threshold,
        "nlp": {
            "cleaned_text": doc,
            "tokens": pipeline_tokens,
            "token_count": len(pipeline_tokens),
            "top_keywords": top_keywords,
        },
        "duplicate": {
            "is_duplicate": p.is_duplicate,
            "score": p.duplicate_score,
            "duplicate_of": p.duplicate_of_id,
            "method": dup_method,
            "probability": dup_probability,
        },
        "similar": similar,
        "cluster": cluster,
        "matches": matches,
    }


@router.post("/check-duplicate")
def check_duplicate(
    body: CheckDuplicateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.get(Problem, body.problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if user.role not in ("admin", "team") and p.user_id != user.id:
        raise HTTPException(403, "Not your problem")
    embedder = get_shared_embedder()
    semantic = getattr(embedder, "name", "tfidf") == "sentence"
    invalidate_cache()
    ids, matrix, texts, pmap = _with_cache(db, embedder)
    if p.id not in ids:
        raise HTTPException(404, "Problem not in index")
    vec = matrix[ids.index(p.id)]
    scores = dedup_mod.nearest_scores(vec, matrix)
    threshold = evaluate.get_tuned_threshold(db, settings.DEDUP_THRESHOLD)

    from ..ml import model_store

    artifact = model_store.load_dedup_artifact() if semantic else None
    if artifact is not None:
        raw_texts = [f"{pm.title}. {pm.description}" for pm in pmap.values()]
        cats = [pm.category for pm in pmap.values()]
        cands = dedup_mod.classifier_decisions(
            artifact, vec, f"{p.title}. {p.description}", p.category,
            ids, matrix, raw_texts, cats, top_n=12, exclude_id=p.id,
        )
        thr = float(artifact["threshold"])
        dups = [(pid, prob) for pid, prob, _c in cands if prob >= thr]
        method = "trained_classifier"
        probability = round(cands[0][1], 4) if cands else None
    else:
        dups = dedup_mod.pick_duplicates(ids, scores, threshold, exclude_id=p.id)
        thr = threshold
        method = "cosine_threshold"
        probability = None

    return {
        "problem_id": p.id,
        "threshold": thr,
        "method": method,
        "probability": probability,
        "is_duplicate": bool(dups),
        "duplicate_of": (
            {"id": dups[0][0], "title": pmap[dups[0][0]].title, "score": round(dups[0][1], 4)}
            if dups
            else None
        ),
    }


@router.get("/similar-problems/{problem_id}")
def similar_problems(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    k: int = Query(default=5, ge=1, le=20),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    embedder = get_shared_embedder()
    from ..routers.problems import similar_out

    return {"problem_id": p.id, "similar": similar_out(db, p, embedder, k=k)}


@router.get("/clusters")
def clusters(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    out = []
    for c in db.scalars(select(ProblemCluster).order_by(ProblemCluster.id)).all():
        members = db.scalars(
            select(Problem).where(Problem.cluster_id == c.id).order_by(Problem.id)
        ).all()
        out.append(
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "size": len(members),
                "members": [
                    {"id": m.id, "title": m.title, "category": m.category, "status": m.status}
                    for m in members
                ],
            }
        )
    return out


@router.get("/recommend-teams/{problem_id}")
def recommend_teams(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    k: int = Query(default=5, ge=1, le=20),
    recompute: bool = False,
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if user.role not in ("admin", "team") and p.user_id != user.id:
        raise HTTPException(403, "Not your problem")
    if recompute:
        embedder = get_shared_embedder()
        analyze_problem(db, embedder, p, persist=True)
        db.commit()
    return {"problem_id": p.id, "recommendations": recs_out(db, p, k=k)}
