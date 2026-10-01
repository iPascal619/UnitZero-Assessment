"""Pydantic schemas for request/response validation."""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, EmailStr


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Users ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: str = Field(..., pattern=r"^(client|operator|admin)$")


class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern=r"^(client|operator|admin)$")
    is_active: Optional[bool] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Episodes ──────────────────────────────────────────────────────────────────

class EpisodeOut(BaseModel):
    id: int
    episode_id: str
    robot_id: str
    task_name: str
    recorded_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    operator_name: Optional[str] = None
    quality: str
    is_assigned: bool = False

    model_config = {"from_attributes": True}


class ImportResult(BaseModel):
    imported: int
    skipped: int
    errors: list[dict]
    details: list[str]


# ── Requests ──────────────────────────────────────────────────────────────────

class RequestCreate(BaseModel):
    task_name: str = Field(..., min_length=1, max_length=255)
    episodes_requested: int = Field(..., gt=0)
    deadline: date
    notes: Optional[str] = None


class RequestOut(BaseModel):
    id: int
    client_id: int
    client_username: Optional[str] = None
    task_name: str
    episodes_requested: int
    deadline: date
    notes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    assigned_count: int = 0

    model_config = {"from_attributes": True}


class StatusTransition(BaseModel):
    status: str = Field(
        ...,
        pattern=r"^(in_progress|delivered|accepted|rejected)$",
    )
    notes: Optional[str] = None


# ── Assignments ───────────────────────────────────────────────────────────────

class AssignmentCreate(BaseModel):
    episode_ids: list[int] = Field(..., min_length=1)


class AssignmentOut(BaseModel):
    id: int
    episode_id: int
    request_id: int
    assigned_at: datetime
    assigned_by: int
    episode: Optional[EpisodeOut] = None

    model_config = {"from_attributes": True}


# ── Status History ────────────────────────────────────────────────────────────

class StatusHistoryOut(BaseModel):
    id: int
    request_id: int
    from_status: Optional[str] = None
    to_status: str
    changed_by: int
    changed_at: datetime
    notes: Optional[str] = None
    username: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Analytics ─────────────────────────────────────────────────────────────────

class EpisodesPerDayPerRobot(BaseModel):
    date: date
    robot_id: str
    count: int


class RequestsByStatus(BaseModel):
    status: str
    count: int


class TopTask(BaseModel):
    task_name: str
    good_episode_count: int


class AnalyticsResponse(BaseModel):
    episodes_per_day_per_robot: list[EpisodesPerDayPerRobot]
    requests_by_status: list[RequestsByStatus]
    median_fulfilment_hours: Optional[float] = None
    top_tasks: list[TopTask]
