from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.roles import Role

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Password = Annotated[str, Field(min_length=12, max_length=128)]
TenantRole = Literal["tenant_admin", "tenant_user"]
PlatformRole = Literal["super_admin", "admin", "super_viewer"]
TenantSlug = Annotated[
    str, StringConstraints(min_length=2, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailInput(Input):
    email: EmailStr

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class LoginInput(EmailInput):
    password: str = Field(min_length=1, max_length=128)
    tenant_slug: TenantSlug | None = None


class UserCreate(EmailInput):
    name: Name
    password: Password
    role: TenantRole = "tenant_user"


class PlatformUserCreate(EmailInput):
    name: Name
    password: Password
    role: PlatformRole


class UserUpdate(Input):
    name: Name | None = None
    role: TenantRole | None = None
    is_active: bool | None = None


class PasswordUpdate(Input):
    password: Password


class TenantCreate(Input):
    name: Name
    slug: TenantSlug
    admin: UserCreate


class TenantUpdate(Input):
    name: Name


class ReactivateInput(Input):
    days: int = Field(default=14, ge=1, le=365)


class CourseCreate(Input):
    title: Title
    description: str = Field(default="", max_length=20000)


class CourseUpdate(Input):
    title: Title | None = None
    description: str | None = Field(default=None, max_length=20000)
    is_archived: bool | None = None


class LessonCreate(Input):
    title: Title
    content: str = Field(min_length=1, max_length=100000)
    position: int = Field(ge=1)


class LessonUpdate(Input):
    title: Title
    content: str = Field(min_length=1, max_length=100000)


class QuestionInput(Input):
    kind: Literal["multiple_choice", "text"]
    prompt: str = Field(min_length=1, max_length=5000)
    options: list[str] = Field(default_factory=list, max_length=6)
    correct_option: int | None = None

    @model_validator(mode="after")
    def validate_question(self):
        self.prompt = self.prompt.strip()
        if not self.prompt:
            raise ValueError("Question prompt is required")
        self.options = [option.strip() for option in self.options]
        if self.kind == "multiple_choice":
            if not 2 <= len(self.options) <= 6 or any(
                not option or len(option) > 500 for option in self.options
            ):
                raise ValueError("Multiple-choice questions need 2–6 nonempty options")
            if len(set(self.options)) != len(self.options):
                raise ValueError("Multiple-choice options must be distinct")
            if self.correct_option is None or not 0 <= self.correct_option < len(self.options):
                raise ValueError("Choose a valid correct option")
        elif self.options or self.correct_option is not None:
            raise ValueError("Text questions cannot have options or an answer key")
        return self


class AnswerInput(Input):
    question_id: UUID
    response: str = Field(min_length=1, max_length=5000)


class ExerciseSubmission(Input):
    answers: list[AnswerInput] = Field(min_length=1, max_length=20)


class AssignmentCreate(Input):
    course_id: UUID
    user_id: UUID


class AssignmentBatchCreate(Input):
    course_id: UUID
    user_ids: list[UUID] = Field(min_length=1, max_length=50)

    @field_validator("user_ids")
    @classmethod
    def unique_users(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Choose each learner only once")
        return value


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserOut(Output):
    id: str
    tenant_id: str | None
    email: str
    name: str
    role: Role
    is_active: bool


class TenantOut(Output):
    id: str
    name: str
    slug: str
    status: Literal["created", "trial_active", "expired"]
    created_at: datetime
    trial_expires_at: datetime


class InstituteSuggestion(BaseModel):
    name: str
    slug: str


class CourseOut(Output):
    id: str
    tenant_id: str
    title: str
    description: str
    is_archived: bool


class LessonOut(Output):
    id: str
    course_id: str
    title: str
    content: str
    position: int


class PublicQuestionOut(Output):
    id: str
    lesson_id: str
    position: int
    kind: Literal["multiple_choice", "text"]
    prompt: str
    options: list[str]


class QuestionOut(PublicQuestionOut):
    correct_option: int | None


class AnswerOut(Output):
    question_id: str
    response: str
    is_correct: bool | None
    submitted_at: datetime


class SubmissionOut(AnswerOut):
    user_id: str


class ExerciseOut(BaseModel):
    lesson_id: str
    questions: list[PublicQuestionOut]
    answers: list[AnswerOut]
    completed: bool


class CourseDetail(CourseOut):
    lessons: list[LessonOut]


class CoursePage(BaseModel):
    items: list[CourseOut]
    total: int
    limit: int
    offset: int


class AssignmentOut(Output):
    id: str
    tenant_id: str
    course_id: str
    user_id: str
    assigned_at: datetime


class ProgressOut(BaseModel):
    assignment_id: str
    course_id: str
    user_id: str
    total_lessons: int
    completed_lessons: int
    percent_complete: float
    is_complete: bool
    completed_lesson_ids: list[str]


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut
