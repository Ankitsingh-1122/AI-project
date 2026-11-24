import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import Feedback, Match, Notification, Problem, ProblemCluster, Team, User
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


def assigned_team_info(db: Session, problem: Problem) -> dict | None:
    match = db.scalars(
        select(Match).where(
            Match.problem_id == problem.id,
            Match.status.in_(["accepted", "assigned"])
        ).order_by(
            Match.status.asc()
        )
    ).first()
    if not match:
        return None
    team = db.get(Team, match.team_id)
    if not team:
        return None
    return {
        "id": team.id,
        "team_name": team.team_name,
        "match_id": match.id,
        "status": match.status,
    }


def problem_out(db: Session, p: Problem, user: User | None = None) -> dict:
    upvotes = db.scalars(
        select(func.count(Feedback.id)).where(
            Feedback.problem_id == p.id,
            Feedback.feedback_type == "upvote",
        )
    ).first() or 0
    user_upvoted = False
    if user is not None:
        user_upvoted = bool(
            db.scalars(
                select(Feedback.id).where(
                    Feedback.problem_id == p.id,
                    Feedback.user_id == user.id,
                    Feedback.feedback_type == "upvote",
                )
            ).first()
        )
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
        "assigned_team": assigned_team_info(db, p),
        "upvotes": upvotes,
        "user_upvoted": user_upvoted,
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
    return [problem_out(db, p, user=user) for p in problems]


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
    out = problem_out(db, p, user=user)
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
    user: User = Depends(require_role("citizen", "admin", "team")),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")

    is_admin = user.role == "admin"
    is_owner = p.user_id == user.id
    assigned_team = None

    if user.role == "team":
        team = db.scalars(select(Team).where(Team.user_id == user.id)).first()
        if team:
            match = db.scalars(
                select(Match).where(
                    Match.problem_id == p.id,
                    Match.team_id == team.id,
                    Match.status.in_(["accepted", "assigned"]),
                )
            ).first()
            if match:
                assigned_team = team

    if not (is_admin or is_owner or (assigned_team is not None)):
        raise HTTPException(403, "Not authorized to update this problem")

    data = body.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(400, "No fields to update")

    # Teams can update problem status (e.g. mark completed / resolved)
    if user.role == "team" and not is_admin:
        allowed_team_fields = {"status"}
        disallowed = set(data.keys()) - allowed_team_fields
        if disallowed:
            raise HTTPException(403, f"Teams can only update problem status, not {', '.join(disallowed)}")

    if "status" in data and data["status"] not in ("open", "in_review", "assigned", "resolved"):
        raise HTTPException(400, "Invalid status")

    old_status = p.status
    new_status = data.get("status")

    for field in ("title", "description", "location", "category", "status"):
        if field in data and data[field] is not None:
            setattr(p, field, data[field])
    db.commit()
    db.refresh(p)

    # When marked as resolved, notify the reporter and administrators
    if new_status == "resolved" and old_status != "resolved":
        team_name = assigned_team.team_name if assigned_team else (user.name or "Assigned Team")
        if p.user_id:
            db.add(
                Notification(
                    user_id=p.user_id,
                    type="problem_resolved",
                    title=f"Problem Resolved: {p.title}",
                    body=f"Team “{team_name}” has completed the work and marked your problem #{p.id} as resolved.",
                )
            )
        admins = db.scalars(select(User).where(User.role == "admin")).all()
        for admin in admins:
            db.add(
                Notification(
                    user_id=admin.id,
                    type="problem_resolved",
                    title=f"Problem #{p.id} Resolved",
                    body=f"Team “{team_name}” completed work on '{p.title}' (#{p.id}) and marked it resolved.",
                )
            )
        db.commit()

    content_fields_changed = any(f in data for f in ("title", "description", "category"))
    analysis = None
    if content_fields_changed:
        embedder = get_shared_embedder()
        analysis = analyze_problem(db, embedder, p, persist=True)
        if "status" in data:
            p.status = data["status"]
            db.commit()
    else:
        invalidate_cache()
    return {"problem": problem_out(db, p, user=user), "analysis": public_result(p, analysis, db) if analysis else None}


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

KNOWN_COORDS = {
    "model town": (30.8913, 75.8362),
    "main bazaar": (30.9125, 75.8540),
    "phase 2": (30.8750, 75.8820),
    "gandhi market": (30.9050, 75.8500),
    "sector 14": (30.8800, 75.8200),
    "civil lines": (30.9080, 75.8370),
    "focal point": (30.8850, 75.9100),
    "transport nagar": (30.8980, 75.8950),
    "city mall": (30.8920, 75.8250),
    "naraina": (30.9200, 75.8600),
    "sarabha nagar": (30.8850, 75.8150),
    "brs nagar": (30.8800, 75.8050),
}


def resolve_coords(location: str, problem_id: int) -> tuple[float, float]:
    loc_lower = (location or "").lower()
    base_lat, base_lng = 30.9010, 75.8573
    for name, coords in KNOWN_COORDS.items():
        if name in loc_lower:
            base_lat, base_lng = coords
            break
    jitter_lat = (((problem_id * 17) % 50) - 25) * 0.00018
    jitter_lng = (((problem_id * 31) % 50) - 25) * 0.00018
    return round(base_lat + jitter_lat, 6), round(base_lng + jitter_lng, 6)


@router.get("/map/all")
def map_problems(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    problems = db.scalars(select(Problem).order_by(Problem.created_at.desc(), Problem.id.desc())).all()
    results = []
    for p in problems:
        po = problem_out(db, p, user=user)
        lat, lng = resolve_coords(p.location, p.id)
        po["lat"] = lat
        po["lng"] = lng
        results.append(po)
    return results


@router.post("/{problem_id}/upvote")
def toggle_upvote(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    existing = db.scalars(
        select(Feedback).where(
            Feedback.problem_id == problem_id,
            Feedback.user_id == user.id,
            Feedback.feedback_type == "upvote",
        )
    ).first()
    if existing:
        db.delete(existing)
        upvoted = False
    else:
        f = Feedback(
            user_id=user.id,
            problem_id=problem_id,
            feedback_type="upvote",
            comment="Citizen upvote (I'm affected too)",
        )
        db.add(f)
        upvoted = True
    db.commit()
    count = db.scalars(
        select(func.count(Feedback.id)).where(
            Feedback.problem_id == problem_id,
            Feedback.feedback_type == "upvote",
        )
    ).first() or 0
    return {"upvoted": upvoted, "upvotes": count}
