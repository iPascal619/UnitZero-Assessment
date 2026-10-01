"""SQLAlchemy ORM models for the Dataset Request Desk."""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    Date,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint("role IN ('client', 'operator', 'admin')", name="ck_user_role"),
    )

    requests = relationship("Request", back_populates="client")


class Episode(Base):
    __tablename__ = "episodes"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(String(100), unique=True, nullable=False, index=True)
    robot_id = Column(String(100), nullable=False)
    task_name = Column(String(255), nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    operator_name = Column(String(255), nullable=True)
    quality = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "quality IN ('good', 'usable', 'bad')", name="ck_episode_quality"
        ),
        Index("ix_episodes_task_name", "task_name"),
        Index("ix_episodes_quality", "quality"),
        Index("ix_episodes_robot_id", "robot_id"),
        Index("ix_episodes_recorded_at", "recorded_at"),
    )

    assignment = relationship("Assignment", back_populates="episode", uselist=False)


class Request(Base):
    __tablename__ = "requests"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    task_name = Column(String(255), nullable=False)
    episodes_requested = Column(Integer, nullable=False)
    deadline = Column(Date, nullable=False)
    notes = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="submitted")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('submitted', 'in_progress', 'delivered', 'accepted', 'rejected')",
            name="ck_request_status",
        ),
        CheckConstraint("episodes_requested > 0", name="ck_episodes_requested_positive"),
        Index("ix_requests_status", "status"),
    )

    client = relationship("User", back_populates="requests")
    assignments = relationship("Assignment", back_populates="request")
    status_history = relationship(
        "StatusHistory", back_populates="request", order_by="StatusHistory.changed_at"
    )


class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)
    episode_id = Column(Integer, ForeignKey("episodes.id"), nullable=False)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False, index=True)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_by = Column(Integer, ForeignKey("users.id"), nullable=False)

    __table_args__ = (
        UniqueConstraint("episode_id", name="uq_assignment_episode"),
    )

    episode = relationship("Episode", back_populates="assignment")
    request = relationship("Request", back_populates="assignments")
    assigner = relationship("User")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("requests.id"), nullable=False, index=True)
    from_status = Column(String(20), nullable=True)
    to_status = Column(String(20), nullable=False)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text, nullable=True)

    request = relationship("Request", back_populates="status_history")
    user = relationship("User")
