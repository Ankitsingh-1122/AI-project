import json
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="citizen")  # citizen | team | admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problems = relationship("Problem", back_populates="owner")
    team = relationship("Team", back_populates="owner", uselist=False)


class Problem(Base):
    __tablename__ = "problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(255), default="")
    category: Mapped[str] = mapped_column(String(100), default="uncategorized", index=True)
    status: Mapped[str] = mapped_column(String(30), default="open")  # open | in_review | assigned | resolved
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("problems.id", ondelete="SET NULL"), nullable=True
    )
    duplicate_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cluster_id: Mapped[int | None] = mapped_column(
        ForeignKey("problem_clusters.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    owner = relationship("User", back_populates="problems")
    duplicate_of = relationship("Problem", remote_side=[id], foreign_keys=[duplicate_of_id])
    cluster = relationship("ProblemCluster", back_populates="problems")


class ProblemCluster(Base):
    __tablename__ = "problem_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problems = relationship("Problem", back_populates="cluster")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True)
    team_name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str] = mapped_column(Text, default="")
    skills: Mapped[str] = mapped_column(Text, default="[]")        # JSON list
    interests: Mapped[str] = mapped_column(Text, default="[]")     # JSON list
    experience: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner = relationship("User", back_populates="team")
    members = relationship("TeamMember", back_populates="team", cascade="all, delete-orphan")

    @property
    def skills_list(self):
        try:
            return json.loads(self.skills or "[]")
        except json.JSONDecodeError:
            return []

    @property
    def interests_list(self):
        try:
            return json.loads(self.interests or "[]")
        except json.JSONDecodeError:
            return []


class TeamMember(Base):
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(80), default="member")

    team = relationship("Team", back_populates="members")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    similarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    ranking: Mapped[int] = mapped_column(Integer, default=0)
    explanation: Mapped[str] = mapped_column(Text, default="{}")   # JSON
    status: Mapped[str] = mapped_column(String(20), default="suggested")  # suggested | accepted | rejected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problem = relationship("Problem")
    team = relationship("Team")
    feedback = relationship("Feedback", back_populates="match")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True
    )
    problem_id: Mapped[int | None] = mapped_column(
        ForeignKey("problems.id", ondelete="CASCADE"), nullable=True
    )
    feedback_type: Mapped[str] = mapped_column(String(40))  # good_match | bad_match | correct_duplicate | wrong_duplicate | other
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User")
    match = relationship("Match", back_populates="feedback")


class Notification(Base):
    """In-app notification addressed to one user (bell icon, persistent record)."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(40), default="info")  # team_deleted | message | match_decision | info
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user = relationship("User")


class Message(Base):
    """Team-inbox message. Addressed to a TEAM: shared among all of its members."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    team = relationship("Team")
    sender = relationship("User")


# ---- Evaluation / labelled data -------------------------------------------


class EvalPair(Base):
    """Manually labelled duplicate / non-duplicate problem pairs (§8, §11)."""

    __tablename__ = "eval_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_a_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    problem_b_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    is_duplicate: Mapped[bool] = mapped_column(Boolean)


class EvalRelevance(Base):
    """Manually labelled relevant teams per problem (for Precision@K)."""

    __tablename__ = "eval_relevance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("problems.id", ondelete="CASCADE"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"))


class ModelState(Base):
    """Persisted model hyper-parameters (e.g. experimentally tuned threshold)."""

    __tablename__ = "model_state"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


# ---- REAL municipal dataset + human labels (real-data ML upgrade) ----------
#
# These tables hold REAL service requests (Chicago/NYC 311, see
# scripts/ingest_real.py) and the HUMAN labels that train the duplicate
# classifier and team-matching ranker. No labels are generated
# automatically — every label row is created by a human reviewer through
# the admin "Data & Labels" UI (scripts/label_mining.py only proposes
# CANDIDATE pairs, with the mining rule recorded in `source`).


class RealProblem(Base):
    """One real service request from an open-data 311 corpus."""

    __tablename__ = "real_problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source: Mapped[str] = mapped_column(String(20))  # chicago | nyc
    source_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    date: Mapped[str] = mapped_column(String(12), default="")
    category: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(255), default="")
    area: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(40), default="")
    duplicate_flag: Mapped[int] = mapped_column(Integer, default=0)  # Chicago's official flag


class RealPair(Base):
    """Candidate duplicate pair for human review (mined, never auto-labelled)."""

    __tablename__ = "real_pairs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_a_id: Mapped[int] = mapped_column(ForeignKey("real_problems.id", ondelete="CASCADE"), index=True)
    problem_b_id: Mapped[int] = mapped_column(ForeignKey("real_problems.id", ondelete="CASCADE"), index=True)
    similarity: Mapped[float | None] = mapped_column(Float, nullable=True)  # embedding cos, if computed
    source: Mapped[str] = mapped_column(String(40), default="mined")  # dup_flag | same_address | embedding | manual
    # label state: NULL = pending review
    is_duplicate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    labeled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problem_a = relationship("RealProblem", foreign_keys=[problem_a_id])
    problem_b = relationship("RealProblem", foreign_keys=[problem_b_id])
    reviewer = relationship("User", foreign_keys=[labeled_by])


class RealRelevance(Base):
    """Human-labelled (real problem, student team) relevance row."""

    __tablename__ = "real_relevance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    problem_id: Mapped[int] = mapped_column(ForeignKey("real_problems.id", ondelete="CASCADE"), index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), index=True)
    relevant: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL = unlabeled
    labeled_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    problem = relationship("RealProblem")
    team = relationship("Team")
    reviewer = relationship("User", foreign_keys=[labeled_by])
