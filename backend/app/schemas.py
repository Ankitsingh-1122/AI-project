from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    password: str = Field(min_length=6, max_length=128)
    role: str = Field(default="citizen", pattern="^(citizen|team)$")


class LoginIn(BaseModel):
    email: str
    password: str


class ProblemIn(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10)
    location: str = ""
    category: str = "uncategorized"


class ProblemUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    location: str | None = None
    category: str | None = None
    status: str | None = None


class TeamMemberIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    role: str = "member"


class TeamIn(BaseModel):
    team_name: str = Field(min_length=2, max_length=150)
    description: str = ""
    skills: list[str] = []
    interests: list[str] = []
    experience: str = ""
    members: list[TeamMemberIn] = []


class MatchDecision(BaseModel):
    status: str = Field(pattern="^(accept|reject)$")


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class FeedbackIn(BaseModel):
    feedback_type: str = Field(pattern="^(good_match|bad_match|correct_duplicate|wrong_duplicate|other)$")
    match_id: int | None = None
    problem_id: int | None = None
    comment: str = ""


class CheckDuplicateIn(BaseModel):
    problem_id: int
