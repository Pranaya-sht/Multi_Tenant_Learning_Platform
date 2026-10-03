from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import ValidationError
from redis.exceptions import RedisError
from sqlalchemy import func, or_, select

from app.api.dependencies import Db, LearningUser, TenantAdmin, TenantIdentity
from app.api.routes.platform import tenant_output
from app.core.roles import Role
from app.core.security import hash_password
from app.models import Assignment, Course, Lesson, LessonProgress, LessonQuestion, Tenant, User
from app.schemas.domain import (
    AssignmentBatchCreate,
    AssignmentCreate,
    AssignmentOut,
    CourseCreate,
    CourseDetail,
    CourseOut,
    CoursePage,
    CourseUpdate,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    PasswordUpdate,
    ProgressOut,
    TenantOut,
    UserCreate,
    UserOut,
    UserUpdate,
)
from app.services.common import commit

router = APIRouter(prefix="/tenant", tags=["tenant learning"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def scoped_course(db, user, course_id, *, lock=False):
    query = select(Course).where(Course.id == str(course_id), Course.tenant_id == user.tenant_id)
    course = db.scalar(query.with_for_update() if lock else query)
    if course is None:
        raise HTTPException(404, "Course not found")
    if user.role == Role.TENANT_USER and not db.scalar(
        select(Assignment.id).where(
            Assignment.tenant_id == user.tenant_id,
            Assignment.course_id == course.id,
            Assignment.user_id == user.id,
        )
    ):
        raise HTTPException(404, "Course not found")
    return course


def scoped_user(db, actor, identifier):
    user = db.scalar(
        select(User)
        .where(User.id == str(identifier), User.tenant_id == actor.tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        raise HTTPException(404, "User not found")
    return user


def scoped_assignment(db, user, identifier, *, lock=False):
    query = select(Assignment).where(
        Assignment.id == str(identifier), Assignment.tenant_id == user.tenant_id
    )
    if user.role == Role.TENANT_USER:
        query = query.where(Assignment.user_id == user.id)
    assignment = db.scalar(query.with_for_update() if lock else query)
    if assignment is None:
        raise HTTPException(404, "Assignment not found")
    return assignment


def assignment_progress(db, assignment):
    total = db.scalar(
        select(func.count())
        .select_from(Lesson)
        .where(Lesson.tenant_id == assignment.tenant_id, Lesson.course_id == assignment.course_id)
    )
    completed = list(
        db.scalars(
            select(LessonProgress.lesson_id)
            .where(
                LessonProgress.tenant_id == assignment.tenant_id,
                LessonProgress.assignment_id == assignment.id,
            )
            .order_by(LessonProgress.lesson_id)
        )
    )
    return ProgressOut(
        assignment_id=assignment.id,
        course_id=assignment.course_id,
        user_id=assignment.user_id,
        total_lessons=total,
        completed_lessons=len(completed),
        percent_complete=round(len(completed) * 100 / total, 2) if total else 0,
        is_complete=bool(total) and len(completed) == total,
        completed_lesson_ids=completed,
    )


@router.get("", response_model=TenantOut)
def tenant_info(user: TenantIdentity, db: Db):
    return tenant_output(db.get(Tenant, user.tenant_id))


@router.get("/users", response_model=list[UserOut])
def list_users(user: TenantAdmin, db: Db, limit: Limit = 50, offset: Offset = 0):
    return list(
        db.scalars(
            select(User)
            .where(User.tenant_id == user.tenant_id)
            .order_by(User.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, user: TenantAdmin, db: Db):
    if data.role == Role.TENANT_ADMIN:
        raise HTTPException(409, "Each institute has one Tenant Admin; transfer the role instead")
    created = User(
        tenant_id=user.tenant_id,
        email=str(data.email),
        name=data.name,
        role=data.role,
        password_hash=hash_password(data.password),
    )
    db.add(created)
    commit(db)
    return created


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, data: UserUpdate, user: TenantAdmin, db: Db):
    target = scoped_user(db, user, user_id)
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if target.role != Role.TENANT_ADMIN and changes.get("role") == Role.TENANT_ADMIN:
        raise HTTPException(409, "Each institute has one Tenant Admin; transfer the role instead")
    removing_admin = (
        target.role == Role.TENANT_ADMIN
        and target.is_active
        and (
            changes.get("role", target.role) != Role.TENANT_ADMIN
            or not changes.get("is_active", True)
        )
    )
    if removing_admin:
        active_admins = db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == user.tenant_id,
                User.role == Role.TENANT_ADMIN,
                User.is_active.is_(True),
            )
        )
        if active_admins <= 1:
            raise HTTPException(409, "Cannot remove the last active tenant administrator")
    for field, value in changes.items():
        setattr(target, field, value)
    if "role" in changes or "is_active" in changes:
        target.token_version += 1
    commit(db)
    return target


@router.post("/users/{user_id}/transfer-admin", response_model=UserOut)
def transfer_admin(user_id: UUID, user: TenantAdmin, db: Db):
    if str(user_id) == user.id:
        raise HTTPException(409, "Choose another active learner to receive the administrator role")
    target = scoped_user(db, user, user_id)
    if target.role != Role.TENANT_USER or not target.is_active:
        raise HTTPException(409, "Administrator role can transfer only to an active learner")

    current_admin = scoped_user(db, user, user.id)
    current_admin.role = Role.TENANT_USER
    current_admin.token_version += 1
    db.flush()  # Release the unique administrator slot inside this transaction.
    target.role = Role.TENANT_ADMIN
    target.token_version += 1
    commit(db)
    return target


@router.put("/users/{user_id}/password", status_code=204)
def reset_password(user_id: UUID, data: PasswordUpdate, user: TenantAdmin, db: Db):
    target = scoped_user(db, user, user_id)
    target.password_hash = hash_password(data.password)
    target.token_version += 1
    commit(db)
    return Response(status_code=204)


@router.get("/courses", response_model=list[CourseOut])
def list_courses(user: LearningUser, db: Db, limit: Limit = 50, offset: Offset = 0):
    query = select(Course).where(Course.tenant_id == user.tenant_id)
    if user.role == Role.TENANT_USER:
        query = query.where(
            Course.id.in_(
                select(Assignment.course_id).where(
                    Assignment.tenant_id == user.tenant_id, Assignment.user_id == user.id
                )
            )
        )
    return list(
        db.scalars(query.order_by(Course.created_at, Course.id).limit(limit).offset(offset))
    )


@router.get("/courses/page", response_model=CoursePage)
def page_courses(
    user: LearningUser,
    db: Db,
    limit: Limit = 10,
    offset: Offset = 0,
    q: Annotated[str, Query(max_length=200)] = "",
    status: Literal["all", "active", "archived"] = "all",
):
    filters = [Course.tenant_id == user.tenant_id]
    if user.role == Role.TENANT_USER:
        filters.append(
            Course.id.in_(
                select(Assignment.course_id).where(
                    Assignment.tenant_id == user.tenant_id, Assignment.user_id == user.id
                )
            )
        )
    if q:
        # Treat SQL LIKE wildcards as literal search text, as the client-side filter did.
        needle = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{needle}%"
        filters.append(
            or_(
                Course.title.ilike(pattern, escape="\\"),
                Course.description.ilike(pattern, escape="\\"),
            )
        )
    if status != "all":
        filters.append(Course.is_archived.is_(status == "archived"))
    total = db.scalar(select(func.count()).select_from(Course).where(*filters))
    items = list(
        db.scalars(
            select(Course)
            .where(*filters)
            .order_by(Course.created_at, Course.id)
            .limit(limit)
            .offset(offset)
        )
    )
    return CoursePage(items=items, total=total, limit=limit, offset=offset)


@router.post("/courses", response_model=CourseOut, status_code=201)
def create_course(data: CourseCreate, user: TenantAdmin, db: Db):
    course = Course(tenant_id=user.tenant_id, **data.model_dump())
    db.add(course)
    commit(db)
    return course


@router.get("/courses/{course_id}", response_model=CourseDetail)
def course_detail(course_id: UUID, user: LearningUser, db: Db, request: Request):
    course = scoped_course(db, user, course_id)
    key = f"tenant:{user.tenant_id}:course:{course.id}:v{course.version}"
    try:
        cached = request.app.state.cache.get(key)
        if cached:
            result = CourseDetail.model_validate_json(cached)
            if result.id == course.id and result.tenant_id == user.tenant_id:
                return result
    except (RedisError, ValidationError):
        pass  # Cache outages cannot bypass authorization or prevent learning.
    lessons = db.scalars(
        select(Lesson)
        .where(Lesson.tenant_id == user.tenant_id, Lesson.course_id == course.id)
        .order_by(Lesson.position)
    )
    result = CourseDetail(
        **CourseOut.model_validate(course).model_dump(),
        lessons=[LessonOut.model_validate(lesson) for lesson in lessons],
    )
    try:
        request.app.state.cache.setex(
            key, request.app.state.settings.cache_seconds, result.model_dump_json()
        )
    except RedisError:
        pass
    return result


@router.patch("/courses/{course_id}", response_model=CourseOut)
def update_course(course_id: UUID, data: CourseUpdate, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id, lock=True)
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(course, field, value)
    course.version += 1
    commit(db)
    return course


@router.delete("/courses/{course_id}", status_code=204)
def archive_course(course_id: UUID, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id, lock=True)
    course.is_archived = True
    course.version += 1
    commit(db)
    return Response(status_code=204)


@router.post("/courses/{course_id}/lessons", response_model=LessonOut, status_code=201)
def create_lesson(course_id: UUID, data: LessonCreate, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id, lock=True)
    if db.scalar(
        select(Assignment.id)
        .where(Assignment.tenant_id == user.tenant_id, Assignment.course_id == course.id)
        .limit(1)
    ):
        raise HTTPException(
            409, "Lesson structure is locked after assignment; edit content instead"
        )
    lesson = Lesson(tenant_id=user.tenant_id, course_id=course.id, **data.model_dump())
    db.add(lesson)
    course.version += 1
    commit(db)
    return lesson


@router.put("/courses/{course_id}/lessons/{lesson_id}", response_model=LessonOut)
def edit_lesson(course_id: UUID, lesson_id: UUID, data: LessonUpdate, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id, lock=True)
    lesson = db.scalar(
        select(Lesson).where(
            Lesson.id == str(lesson_id),
            Lesson.course_id == course.id,
            Lesson.tenant_id == user.tenant_id,
        )
    )
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    lesson.title, lesson.content = data.title, data.content
    course.version += 1
    commit(db)
    return lesson


@router.post("/assignments", response_model=AssignmentOut, status_code=201)
def assign(data: AssignmentCreate, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, data.course_id, lock=True)
    learner = scoped_user(db, user, data.user_id)
    if learner.role != Role.TENANT_USER or not learner.is_active:
        raise HTTPException(409, "Assignments require an active tenant learner")
    if course.is_archived:
        raise HTTPException(409, "Archived courses cannot receive new assignments")
    if not db.scalar(
        select(Lesson.id)
        .where(Lesson.tenant_id == user.tenant_id, Lesson.course_id == course.id)
        .limit(1)
    ):
        raise HTTPException(409, "Add at least one lesson before assigning the course")
    assignment = Assignment(tenant_id=user.tenant_id, course_id=course.id, user_id=learner.id)
    db.add(assignment)
    commit(db)
    return assignment


@router.post("/assignments/batch", response_model=list[AssignmentOut], status_code=201)
def assign_batch(data: AssignmentBatchCreate, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, data.course_id, lock=True)
    if course.is_archived:
        raise HTTPException(409, "Archived courses cannot receive new assignments")
    if not db.scalar(
        select(Lesson.id)
        .where(Lesson.tenant_id == user.tenant_id, Lesson.course_id == course.id)
        .limit(1)
    ):
        raise HTTPException(409, "Add at least one lesson before assigning the course")

    identifiers = [str(identifier) for identifier in data.user_ids]
    learners = {
        learner.id: learner
        for learner in db.scalars(
            select(User)
            .where(User.tenant_id == user.tenant_id, User.id.in_(identifiers))
            .order_by(User.id)
            .with_for_update()
        )
    }
    if len(learners) != len(identifiers):
        raise HTTPException(404, "User not found")
    if any(
        learner.role != Role.TENANT_USER or not learner.is_active for learner in learners.values()
    ):
        raise HTTPException(409, "Assignments require active tenant learners")
    if db.scalar(
        select(Assignment.id)
        .where(
            Assignment.tenant_id == user.tenant_id,
            Assignment.course_id == course.id,
            Assignment.user_id.in_(identifiers),
        )
        .limit(1)
    ):
        raise HTTPException(409, "One or more learners are already enrolled")

    assignments = [
        Assignment(tenant_id=user.tenant_id, course_id=course.id, user_id=identifier)
        for identifier in identifiers
    ]
    db.add_all(assignments)
    commit(db)
    return assignments


@router.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(user: LearningUser, db: Db, limit: Limit = 50, offset: Offset = 0):
    query = select(Assignment).where(Assignment.tenant_id == user.tenant_id)
    if user.role == Role.TENANT_USER:
        query = query.where(Assignment.user_id == user.id)
    return list(
        db.scalars(
            query.order_by(Assignment.assigned_at, Assignment.id).limit(limit).offset(offset)
        )
    )


@router.get("/assignments/progress", response_model=list[ProgressOut])
def list_assignment_progress(
    user: LearningUser,
    db: Db,
    assignment_ids: Annotated[list[UUID], Query(min_length=1, max_length=10)],
):
    identifiers = list(dict.fromkeys(str(identifier) for identifier in assignment_ids))
    query = select(Assignment).where(
        Assignment.tenant_id == user.tenant_id, Assignment.id.in_(identifiers)
    )
    if user.role == Role.TENANT_USER:
        query = query.where(Assignment.user_id == user.id)
    assignments = {assignment.id: assignment for assignment in db.scalars(query)}
    if len(assignments) != len(identifiers):
        raise HTTPException(404, "Assignment not found")

    course_ids = {assignment.course_id for assignment in assignments.values()}
    totals = {
        course_id: total
        for course_id, total in db.execute(
            select(Lesson.course_id, func.count())
            .where(Lesson.tenant_id == user.tenant_id, Lesson.course_id.in_(course_ids))
            .group_by(Lesson.course_id)
        )
    }
    completed = {identifier: [] for identifier in identifiers}
    for assignment_id, lesson_id in db.execute(
        select(LessonProgress.assignment_id, LessonProgress.lesson_id)
        .where(
            LessonProgress.tenant_id == user.tenant_id,
            LessonProgress.assignment_id.in_(identifiers),
        )
        .order_by(LessonProgress.assignment_id, LessonProgress.lesson_id)
    ):
        completed[assignment_id].append(lesson_id)

    results = []
    for identifier in identifiers:
        assignment = assignments[identifier]
        total = totals.get(assignment.course_id, 0)
        lesson_ids = completed[identifier]
        results.append(
            ProgressOut(
                assignment_id=identifier,
                course_id=assignment.course_id,
                user_id=assignment.user_id,
                total_lessons=total,
                completed_lessons=len(lesson_ids),
                percent_complete=round(len(lesson_ids) * 100 / total, 2) if total else 0,
                is_complete=bool(total) and len(lesson_ids) == total,
                completed_lesson_ids=lesson_ids,
            )
        )
    return results


@router.delete("/assignments/{assignment_id}", status_code=204)
def revoke_assignment(assignment_id: UUID, user: TenantAdmin, db: Db):
    assignment = scoped_assignment(db, user, assignment_id, lock=True)
    db.delete(assignment)
    commit(db)
    return Response(status_code=204)


@router.get("/assignments/{assignment_id}/progress", response_model=ProgressOut)
def get_progress(assignment_id: UUID, user: LearningUser, db: Db):
    return assignment_progress(db, scoped_assignment(db, user, assignment_id))


@router.put("/assignments/{assignment_id}/lessons/{lesson_id}/complete", response_model=ProgressOut)
def complete_lesson(assignment_id: UUID, lesson_id: UUID, user: LearningUser, db: Db):
    assignment = scoped_assignment(db, user, assignment_id, lock=True)
    if assignment.user_id != user.id or user.role != Role.TENANT_USER:
        raise HTTPException(403, "Only the assigned learner can record completion")
    if not db.scalar(
        select(Lesson.id).where(
            Lesson.id == str(lesson_id),
            Lesson.course_id == assignment.course_id,
            Lesson.tenant_id == user.tenant_id,
        )
    ):
        raise HTTPException(404, "Lesson not found")
    if db.scalar(
        select(LessonQuestion.id)
        .where(
            LessonQuestion.tenant_id == user.tenant_id,
            LessonQuestion.course_id == assignment.course_id,
            LessonQuestion.lesson_id == str(lesson_id),
        )
        .limit(1)
    ):
        raise HTTPException(409, "Answer this lesson's questions to complete it")
    if not db.scalar(
        select(LessonProgress.id).where(
            LessonProgress.tenant_id == user.tenant_id,
            LessonProgress.assignment_id == assignment.id,
            LessonProgress.lesson_id == str(lesson_id),
        )
    ):
        db.add(
            LessonProgress(
                tenant_id=user.tenant_id,
                assignment_id=assignment.id,
                course_id=assignment.course_id,
                user_id=user.id,
                lesson_id=str(lesson_id),
            )
        )
        commit(db)
    return assignment_progress(db, assignment)
