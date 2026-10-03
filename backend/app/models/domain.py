from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN ('created', 'trial_active', 'expired')", name="status"),
        CheckConstraint("trial_expires_at > created_at", name="trial_window"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(150))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="trial_active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    trial_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "email"),
        Index(
            "uq_users_platform_email",
            "email",
            unique=True,
            postgresql_where=text("tenant_id IS NULL"),
            sqlite_where=text("tenant_id IS NULL"),
        ),
        Index(
            "uq_users_one_tenant_admin",
            "tenant_id",
            unique=True,
            postgresql_where=text("role = 'tenant_admin'"),
            sqlite_where=text("role = 'tenant_admin'"),
        ),
        CheckConstraint(
            "(role IN ('super_admin', 'admin', 'super_viewer') AND tenant_id IS NULL) OR "
            "(role IN ('tenant_admin', 'tenant_user') AND tenant_id IS NOT NULL)",
            name="role_scope",
        ),
        CheckConstraint("token_version >= 0", name="token_version"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), index=True
    )
    email: Mapped[str] = mapped_column(String(254))
    name: Mapped[str] = mapped_column(String(150))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Course(Base):
    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("tenants.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "course_id"], ["courses.tenant_id", "courses.id"]),
        UniqueConstraint("tenant_id", "course_id", "id"),
        UniqueConstraint("tenant_id", "course_id", "position"),
        CheckConstraint("position >= 1", name="position"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    course_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class LessonQuestion(Base):
    __tablename__ = "lesson_questions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "course_id", "lesson_id"],
            ["lessons.tenant_id", "lessons.course_id", "lessons.id"],
        ),
        UniqueConstraint("tenant_id", "course_id", "lesson_id", "id"),
        UniqueConstraint("tenant_id", "course_id", "lesson_id", "position"),
        CheckConstraint("kind IN ('multiple_choice', 'text')", name="kind"),
        CheckConstraint("position >= 1", name="position"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    course_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    lesson_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSON, default=list)
    correct_option: Mapped[int | None] = mapped_column(Integer)


class Assignment(Base):
    __tablename__ = "assignments"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "course_id"], ["courses.tenant_id", "courses.id"]),
        ForeignKeyConstraint(["tenant_id", "user_id"], ["users.tenant_id", "users.id"]),
        UniqueConstraint("tenant_id", "course_id", "user_id"),
        UniqueConstraint("tenant_id", "id", "course_id", "user_id"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    course_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "assignment_id", "course_id", "user_id"],
            [
                "assignments.tenant_id",
                "assignments.id",
                "assignments.course_id",
                "assignments.user_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "course_id", "lesson_id"],
            ["lessons.tenant_id", "lessons.course_id", "lessons.id"],
        ),
        UniqueConstraint("tenant_id", "assignment_id", "lesson_id"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    assignment_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    course_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    lesson_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LessonAnswer(Base):
    __tablename__ = "lesson_answers"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "assignment_id", "course_id", "user_id"],
            [
                "assignments.tenant_id",
                "assignments.id",
                "assignments.course_id",
                "assignments.user_id",
            ],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "course_id", "lesson_id", "question_id"],
            [
                "lesson_questions.tenant_id",
                "lesson_questions.course_id",
                "lesson_questions.lesson_id",
                "lesson_questions.id",
            ],
        ),
        UniqueConstraint("tenant_id", "assignment_id", "question_id"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    assignment_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    course_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    lesson_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    question_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    response: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
