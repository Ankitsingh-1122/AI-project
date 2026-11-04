import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import Match, Problem, ProblemCluster, Team, User
from ..pipeline import analyze_problem, invalidate_cache, public_result
from ..schemas import ProblemIn, ProblemUpdate
from ..ml.embed import get_shared_embedder

router = APIRouter(prefix="/api/problems", tags=["problems"])


def cluster_name(db: Session, problem: Problem) -> str | None:
    if not problem.cluster_id:
        return None
    c = db.get(ProblemCluster, problem.cluster_id)
    return c.name if c else None


def dup_info(db: Session, problem: Problem) -> dict | None:
    if not problem.duplicate_of_id:
        return None
    d = db.get(Problem, problem.duplicate_of_id)
    return {"id": d.id, "title": d.title} if d else None


def problem_out(db: Session, p: Problem) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "description": p.description,
        "location": p.location,
        "category": p.category,
        "status": p.status,
        "is_duplicate": p.is_duplicate,
        "duplicate_score": p.duplicate_score,
        "duplicate_of": dup_info(db, p),
        "cluster": cluster_name(db, p),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "owner_id": p.user_id,
    }


@router.post("", status_code=201)
def create_problem(
    body: ProblemIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("citizen", "admin")),
):
    problem = Problem(
        title=body.title.strip(),
        description=body.description.strip(),
        location=(body.location or "").strip(),
        category=(body.category or "uncategorized").strip() or "uncategorized",
        user_id=user.id,
    )
    db.add(problem)
    db.commit()
    db.refresh(problem)
    embedder = get_shared_embedder()
    analysis = analyze_problem(db, embedder, problem, persist=True)
    db.commit()
    return {"problem": problem_out(db, problem), "analysis": public_result(problem, analysis, db)}


@router.get("")
def list_problems(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    category: str | None = None,
    status: str | None = None,
    q: str | None = None,
):
    stmt = select(Problem).order_by(Problem.created_at.desc(), Problem.id.desc())
    if user.role != "admin":
        stmt = stmt.where(Problem.user_id == user.id)
    if category:
        stmt = stmt.where(Problem.category == category)
    if status:
        stmt = stmt.where(Problem.status == status)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            Problem.title.ilike(like) | Problem.description.ilike(like)
        )
    problems = db.scalars(stmt).all()
    return [problem_out(db, p) for p in problems]


@router.get("/{problem_id}")
def get_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if user.role not in ("admin", "team") and p.user_id != user.id:
        raise HTTPException(403, "Not your problem")
    embedder = get_shared_embedder()
    out = problem_out(db, p)
    out["similar"] = similar_out(db, p, embedder)
    out["recommended_teams"] = recs_out(db, p, k=5)
    return out


def similar_out(db: Session, p: Problem, embedder, k: int = 5) -> list[dict]:
    from ..ml import dedup, preprocess

    invalidate_cache()
    from ..pipeline import _with_cache

    ids, matrix, texts, pmap = _with_cache(db, embedder)
    if p.id not in ids:
        return []
    vec = matrix[ids.index(p.id)]
    scores = dedup.nearest_scores(vec, matrix)
    out = []
    for pid, s in dedup.pick_duplicates(ids, scores, 0.30, exclude_id=p.id)[:k]:
        q = pmap[pid]
        out.append({"id": q.id, "title": q.title, "category": q.category, "score": round(float(s), 4)})
    return out


def recs_out(db: Session, p: Problem, k: int | None = None) -> list[dict]:
    out = []
    matches = db.scalars(
        select(Match).where(Match.problem_id == p.id).order_by(Match.ranking)
    ).all()
    if k is not None:
        matches = matches[:k]
    for m in matches:
        team = db.get(Team, m.team_id)
        try:
            expl = json.loads(m.explanation or "{}")
        except json.JSONDecodeError:
            expl = {}
        out.append(
            {
                "match_id": m.id,
                "team_id": m.team_id,
                "team_name": team.team_name if team else "?",
                "score": m.similarity_score,
                "ranking": m.ranking,
                "status": m.status,
                "explanation": expl.get("reason", ""),
                "matched_keywords": expl.get("matched_keywords", []),
            }
        )
    return out


@router.put("/{problem_id}")
def update_problem(
    problem_id: int,
    body: ProblemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("citizen", "admin")),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if p.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not your problem")
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No fields to update")
    if "status" in data and data["status"] not in ("open", "in_review", "assigned", "resolved"):
        raise HTTPException(400, "Invalid status")
    for field in ("title", "description", "location", "category", "status"):
        if field in data and data[field] is not None:
            setattr(p, field, data[field])
    db.commit()
    db.refresh(p)
    embedder = get_shared_embedder()
    analysis = analyze_problem(db, embedder, p, persist=True)
    db.commit()
    return {"problem": problem_out(db, p), "analysis": public_result(p, analysis, db)}


@router.delete("/{problem_id}", status_code=204)
def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("citizen", "admin")),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if p.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not your problem")
    db.delete(p)
    db.commit()
    invalidate_cache()
    return None
