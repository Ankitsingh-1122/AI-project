import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_role
from ..models import Match, Message, Notification, Problem, Team, TeamMember, User
from ..schemas import MatchDecision, MessageIn, TeamIn
from ..pipeline import invalidate_cache

router = APIRouter(prefix="/api/teams", tags=["teams"])

MAX_TEAM_MEMBERS = 10


def _check_member_limit(members) -> None:
    if len(members) > MAX_TEAM_MEMBERS:
        raise HTTPException(
            400, f"Maximum {MAX_TEAM_MEMBERS} members are allowed per team"
        )


def team_out(db: Session, t: Team, include_members: bool = True) -> dict:
    out = {
        "id": t.id,
        "team_name": t.team_name,
        "description": t.description,
        "skills": t.skills_list,
        "interests": t.interests_list,
        "experience": t.experience,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
    if include_members:
        out["members"] = [
            {"id": m.id, "name": m.name, "role": m.role} for m in t.members
        ]
    return out


@router.post("", status_code=201)
def create_team(
    body: TeamIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("team", "admin")),
):
    _check_member_limit(body.members)
    if user.role == "team":
        existing = db.scalars(select(Team).where(Team.user_id == user.id)).first()
        if existing:
            raise HTTPException(409, "You already have a team - use PUT to update it")
    team = Team(
        user_id=user.id,
        team_name=body.team_name.strip(),
        description=body.description.strip(),
        skills=json.dumps(body.skills),
        interests=json.dumps(body.interests),
        experience=body.experience.strip(),
    )
    for m in body.members:
        team.members.append(TeamMember(name=m.name, role=m.role))
    db.add(team)
    db.commit()
    db.refresh(team)
    return team_out(db, team)


@router.get("")
def list_teams(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    teams = db.scalars(select(Team).order_by(Team.id)).all()
    return [team_out(db, t, include_members=False) for t in teams]


@router.get("/my-recommendations")
def my_recommendations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "team":
        raise HTTPException(403, "Only team accounts")
    team = db.scalars(select(Team).where(Team.user_id == user.id)).first()
    if not team:
        return []
    matches = (
        db.scalars(
            select(Match)
            .where(Match.team_id == team.id)
            .order_by(
                case((Match.status == "assigned", 1), (Match.status == "suggested", 2), else_=3),
                Match.created_at.desc(),
                Match.id.desc(),
            )
        )
        .all()
    )
    out = []
    for m in matches:
        p = db.get(Problem, m.problem_id)
        if not p:
            continue
        # If this recommendation is still 'suggested' but the problem was already accepted
        # by another team or resolved, do not offer it as an open task.
        if m.status == "suggested" and p.status in ("assigned", "resolved"):
            continue
        try:
            expl = json.loads(m.explanation or "{}")
        except json.JSONDecodeError:
            expl = {}
        out.append(
            {
                "match_id": m.id,
                "problem_id": p.id,
                "title": p.title,
                "description": p.description,
                "location": p.location,
                "category": p.category,
                "status": p.status,
                "score": m.similarity_score,
                "match_status": m.status,
                "explanation": expl.get("reason", ""),
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return out


@router.get("/{team_id}")
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.get(Team, team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    return team_out(db, t)


@router.put("/{team_id}")
def update_team(
    team_id: int,
    body: TeamIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("team", "admin")),
):
    _check_member_limit(body.members)
    t = db.get(Team, team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    if t.user_id != user.id and user.role != "admin":
        raise HTTPException(403, "Not your team")
    t.team_name = body.team_name.strip()
    t.description = body.description.strip()
    t.skills = json.dumps(body.skills)
    t.interests = json.dumps(body.interests)
    t.experience = body.experience.strip()
    t.members = [TeamMember(name=m.name, role=m.role) for m in body.members]
    db.commit()
    db.refresh(t)
    invalidate_cache()
    return team_out(db, t)


def message_out(m: Message) -> dict:
    return {
        "id": m.id,
        "team_id": m.team_id,
        "sender_id": m.sender_id,
        "sender_name": m.sender.name if m.sender else "Unknown",
        "body": m.body,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("/{team_id}/messages")
def team_messages(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Shared team inbox: every message addressed to the team, for all members."""
    t = db.get(Team, team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    rows = (
        db.scalars(
            select(Message)
            .where(Message.team_id == team_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .all()
    )
    return [message_out(m) for m in rows]


@router.post("/{team_id}/messages", status_code=201)
def send_message(
    team_id: int,
    body: MessageIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a message to a team. Shared among all of the team's members; the
    team lead also gets a bell notification. Kept as a persistent record."""
    t = db.get(Team, team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    text = body.body.strip()
    if not text:
        raise HTTPException(400, "Message cannot be empty")
    # Who is this a reply to? The latest message in this thread from a
    # different user (e.g. a citizen writing to the team) — so the thread
    # pings both sides in their bells.
    previous = db.scalars(
        select(Message)
        .where(Message.team_id == t.id, Message.sender_id != user.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    ).first()

    msg = Message(team_id=t.id, sender_id=user.id, body=text)
    db.add(msg)
    db.add(
        Notification(
            user_id=t.user_id,
            type="message",
            title=f"New message from {user.name}",
            body=text[:160],
        )
    )
    if previous is not None and previous.sender_id is not None and previous.sender_id != t.user_id:
        db.add(
            Notification(
                user_id=previous.sender_id,
                type="message",
                title=f"Team {t.team_name} replied",
                body=f"In the “{t.team_name}” conversation: {text[:120]}",
            )
        )
    db.commit()
    db.refresh(msg)
    return message_out(msg)


@router.delete("/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("admin")),
):
    """Admin-only: remove a team from the directory. The team's members and
    pending matches are removed (cascade), and the team's owner is left a
    notification so they are told when they next log in."""
    t = db.get(Team, team_id)
    if not t:
        raise HTTPException(404, "Team not found")
    owner = db.get(User, t.user_id)
    name = t.team_name
    # Members cascade with the team; drop pending matches explicitly.
    db.query(Match).filter(Match.team_id == t.id).delete()
    db.delete(t)
    db.flush()
    if owner is not None:
        db.add(
            Notification(
                user_id=owner.id,
                type="team_deleted",
                title="Your team was removed",
                body=(
                    f"Your team “{name}” was removed by an administrator on "
                    f"{datetime.now(timezone.utc):%d %b %Y}. You can register a "
                    f"new team from Team Home."
                ),
            )
        )
    db.commit()
    invalidate_cache()
    return {"detail": f"Team “{name}” removed", "team_id": team_id}


@router.post("/matches/{match_id}/decision")
def match_decision(
    match_id: int,
    body: MatchDecision,
    db: Session = Depends(get_db),
    user: User = Depends(require_role("team", "admin")),
):
    m = db.get(Match, match_id)
    if not m:
        raise HTTPException(404, "Match not found")
    team = db.get(Team, m.team_id)
    if user.role != "admin" and (team is None or team.user_id != user.id):
        raise HTTPException(403, "Not your team's match")
    if body.status == "accept":
        existing_accepted = db.scalars(
            select(Match).where(
                Match.problem_id == m.problem_id,
                Match.status == "accepted",
                Match.id != m.id,
            )
        ).first()
        if existing_accepted:
            raise HTTPException(400, "This problem has already been accepted by another team")
    m.status = "accepted" if body.status == "accept" else "rejected"
    problem = db.get(Problem, m.problem_id)
    admins = db.scalars(select(User).where(User.role == "admin")).all()

    if body.status == "accept":
        if problem:
            problem.status = "assigned"

        # 1. Notify citizen reporter
        if problem and team and problem.user_id:
            db.add(
                Notification(
                    user_id=problem.user_id,
                    type="team_accepted",
                    title=f"Team {team.team_name} accepted your problem",
                    body=f"“{problem.title}” (#{problem.id}) was confirmed and accepted by {team.team_name}. Work is underway.",
                )
            )
        # 2. Notify admin
        if problem and team:
            for admin in admins:
                db.add(
                    Notification(
                        user_id=admin.id,
                        type="team_accepted",
                        title=f"Team {team.team_name} Accepted #{problem.id}",
                        body=f"Team {team.team_name} confirmed the assignment for '{problem.title}' (#{problem.id}).",
                    )
                )
    else:  # REJECT / DECLINE
        if problem:
            problem.status = "open"  # Reset status so it can be reassigned

        # 1. REPORT TO ADMIN (Alert for reassignment)
        if problem and team:
            for admin in admins:
                db.add(
                    Notification(
                        user_id=admin.id,
                        type="team_rejected",
                        title=f"ALERT: Team {team.team_name} Declined #{problem.id}",
                        body=(
                            f"Team {team.team_name} has declined assignment for '{problem.title}' (#{problem.id}). "
                            f"Problem status has been reset to 'Open'. Please review or manually reassign."
                        ),
                    )
                )
        # 2. Notify citizen reporter
        if problem and team and problem.user_id:
            db.add(
                Notification(
                    user_id=problem.user_id,
                    type="team_rejected",
                    title=f"Update on Report #{problem.id}",
                    body=f"Team {team.team_name} was unable to take on '{problem.title}'. The report has returned to the queue for reassignment.",
                )
            )
    db.commit()
    return {
        "match_id": m.id,
        "status": m.status,
        "problem_status": problem.status if problem else None,
    }
