from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import Feedback, Match, Problem, Team, User
from ..schemas import FeedbackIn

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


def feedback_out(db: Session, f: Feedback) -> dict:
    match_info = None
    if f.match_id:
        m = db.get(Match, f.match_id)
        if m:
            p = db.get(Problem, m.problem_id)
            t = db.get(Team, m.team_id)
            match_info = {
                "match_id": m.id,
                "problem_title": p.title if p else "?",
                "team_name": t.team_name if t else "?",
            }
    return {
        "id": f.id,
        "feedback_type": f.feedback_type,
        "comment": f.comment,
        "match": match_info,
        "problem_id": f.problem_id,
        "user": db.get(User, f.user_id).name if f.user_id and db.get(User, f.user_id) else None,
        "created_at": f.created_at.isoformat() if f.created_at else None,
    }


@router.post("", status_code=201)
def create_feedback(
    body: FeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if body.match_id and not db.get(Match, body.match_id):
        raise HTTPException(404, "Match not found")
    if body.problem_id and not db.get(Problem, body.problem_id):
        raise HTTPException(404, "Problem not found")
    if not body.match_id and not body.problem_id:
        raise HTTPException(400, "Provide match_id or problem_id")
    f = Feedback(
        user_id=user.id,
        match_id=body.match_id,
        problem_id=body.problem_id,
        feedback_type=body.feedback_type,
        comment=body.comment,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return feedback_out(db, f)


@router.get("")
def list_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    return [feedback_out(db, f) for f in db.scalars(select(Feedback).order_by(Feedback.created_at.desc())).all()]


@router.get("/mine")
def my_feedback(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.scalars(select(Feedback).where(Feedback.user_id == user.id).order_by(Feedback.created_at.desc())).all()
    return [feedback_out(db, f) for f in rows]
