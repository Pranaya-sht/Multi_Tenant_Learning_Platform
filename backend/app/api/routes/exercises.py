"""Questions live inside lessons; course assignments remain access grants."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select

from app.api.dependencies import Db, LearningUser, TenantAdmin
from app.api.routes.learning import scoped_course
from app.core.roles import Role
from app.models import Assignment, Lesson, LessonAnswer, LessonProgress, LessonQuestion
from app.schemas.domain import (
    AnswerOut,
    ExerciseOut,
    ExerciseSubmission,
    PublicQuestionOut,
    QuestionInput,
    QuestionOut,
    SubmissionOut,
)
from app.services.common import commit
from app.services.tenants import as_utc

router = APIRouter(prefix="/tenant/courses/{course_id}", tags=["lesson exercises"])


def scoped_lesson(db, user, course_id, lesson_id):
    lesson = db.scalar(
        select(Lesson).where(
            Lesson.tenant_id == user.tenant_id,
            Lesson.course_id == str(course_id),
            Lesson.id == str(lesson_id),
        )
    )
    if lesson is None:
        raise HTTPException(404, "Lesson not found")
    return lesson


def ensure_unassigned(db, user, course_id):
    if db.scalar(
        select(Assignment.id)
        .where(Assignment.tenant_id == user.tenant_id, Assignment.course_id == str(course_id))
        .limit(1)
    ):
        raise HTTPException(409, "Question structure is locked after assigning the course")


def scoped_question(db, user, lesson, question_id):
    question = db.scalar(
        select(LessonQuestion).where(
            LessonQuestion.tenant_id == user.tenant_id,
            LessonQuestion.course_id == lesson.course_id,
            LessonQuestion.lesson_id == lesson.id,
            LessonQuestion.id == str(question_id),
        )
    )
    if question is None:
        raise HTTPException(404, "Question not found")
    return question


def learner_assignment(db, user, course_id, *, lock=False):
    if user.role != Role.TENANT_USER:
        raise HTTPException(403, "Only learners can submit answers")
    query = select(Assignment).where(
        Assignment.tenant_id == user.tenant_id,
        Assignment.course_id == str(course_id),
        Assignment.user_id == user.id,
    )
    assignment = db.scalar(query.with_for_update() if lock else query)
    if assignment is None:
        raise HTTPException(404, "Course not found")
    return assignment


def exercise_output(db, user, lesson, assignment):
    questions = list(
        db.scalars(
            select(LessonQuestion)
            .where(
                LessonQuestion.tenant_id == user.tenant_id,
                LessonQuestion.course_id == lesson.course_id,
                LessonQuestion.lesson_id == lesson.id,
            )
            .order_by(LessonQuestion.position)
        )
    )
    stored_answers = {
        answer.question_id: answer
        for answer in db.scalars(
            select(LessonAnswer).where(
                LessonAnswer.tenant_id == user.tenant_id,
                LessonAnswer.assignment_id == assignment.id,
                LessonAnswer.lesson_id == lesson.id,
            )
        )
    }
    answers = [stored_answers[item.id] for item in questions if item.id in stored_answers]
    completed = bool(
        db.scalar(
            select(LessonProgress.id).where(
                LessonProgress.tenant_id == user.tenant_id,
                LessonProgress.assignment_id == assignment.id,
                LessonProgress.lesson_id == lesson.id,
            )
        )
    )
    return ExerciseOut(
        lesson_id=lesson.id,
        questions=[PublicQuestionOut.model_validate(question) for question in questions],
        answers=[
            AnswerOut(
                question_id=answer.question_id,
                response=answer.response,
                is_correct=answer.is_correct,
                submitted_at=as_utc(answer.submitted_at),
            )
            for answer in answers
        ],
        completed=completed,
    )


@router.get("/questions", response_model=list[QuestionOut])
def list_course_questions(course_id: UUID, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id)
    return list(
        db.scalars(
            select(LessonQuestion)
            .where(
                LessonQuestion.tenant_id == user.tenant_id,
                LessonQuestion.course_id == course.id,
            )
            .order_by(LessonQuestion.lesson_id, LessonQuestion.position)
        )
    )


@router.post("/lessons/{lesson_id}/questions", response_model=QuestionOut, status_code=201)
def create_question(
    course_id: UUID, lesson_id: UUID, data: QuestionInput, user: TenantAdmin, db: Db
):
    course = scoped_course(db, user, course_id, lock=True)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    ensure_unassigned(db, user, course.id)
    used_positions = set(
        db.scalars(
            select(LessonQuestion.position).where(
                LessonQuestion.tenant_id == user.tenant_id,
                LessonQuestion.course_id == course.id,
                LessonQuestion.lesson_id == lesson.id,
            )
        )
    )
    if len(used_positions) >= 20:
        raise HTTPException(409, "A lesson can have at most 20 questions")
    position = next(position for position in range(1, 21) if position not in used_positions)
    question = LessonQuestion(
        tenant_id=user.tenant_id,
        course_id=course.id,
        lesson_id=lesson.id,
        position=position,
        **data.model_dump(),
    )
    db.add(question)
    course.version += 1
    commit(db)
    return question


@router.put("/lessons/{lesson_id}/questions/{question_id}", response_model=QuestionOut)
def edit_question(
    course_id: UUID,
    lesson_id: UUID,
    question_id: UUID,
    data: QuestionInput,
    user: TenantAdmin,
    db: Db,
):
    course = scoped_course(db, user, course_id, lock=True)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    ensure_unassigned(db, user, course.id)
    question = scoped_question(db, user, lesson, question_id)
    for key, value in data.model_dump().items():
        setattr(question, key, value)
    course.version += 1
    commit(db)
    return question


@router.delete("/lessons/{lesson_id}/questions/{question_id}", status_code=204)
def delete_question(course_id: UUID, lesson_id: UUID, question_id: UUID, user: TenantAdmin, db: Db):
    course = scoped_course(db, user, course_id, lock=True)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    ensure_unassigned(db, user, course.id)
    question = scoped_question(db, user, lesson, question_id)
    db.delete(question)
    course.version += 1
    commit(db)
    return Response(status_code=204)


@router.get("/lessons/{lesson_id}/answers", response_model=list[SubmissionOut])
def list_lesson_answers(
    course_id: UUID,
    lesson_id: UUID,
    user: TenantAdmin,
    db: Db,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    course = scoped_course(db, user, course_id)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    answers = db.scalars(
        select(LessonAnswer)
        .where(
            LessonAnswer.tenant_id == user.tenant_id,
            LessonAnswer.course_id == course.id,
            LessonAnswer.lesson_id == lesson.id,
        )
        .order_by(LessonAnswer.submitted_at, LessonAnswer.id)
        .limit(limit)
        .offset(offset)
    )
    return [
        SubmissionOut(
            user_id=answer.user_id,
            question_id=answer.question_id,
            response=answer.response,
            is_correct=answer.is_correct,
            submitted_at=as_utc(answer.submitted_at),
        )
        for answer in answers
    ]


@router.get("/lessons/{lesson_id}/exercise", response_model=ExerciseOut)
def get_exercise(course_id: UUID, lesson_id: UUID, user: LearningUser, db: Db):
    course = scoped_course(db, user, course_id)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    assignment = learner_assignment(db, user, course.id)
    return exercise_output(db, user, lesson, assignment)


@router.put("/lessons/{lesson_id}/exercise", response_model=ExerciseOut)
def submit_exercise(
    course_id: UUID,
    lesson_id: UUID,
    data: ExerciseSubmission,
    user: LearningUser,
    db: Db,
):
    course = scoped_course(db, user, course_id)
    lesson = scoped_lesson(db, user, course.id, lesson_id)
    assignment = learner_assignment(db, user, course.id, lock=True)
    questions = list(
        db.scalars(
            select(LessonQuestion)
            .where(
                LessonQuestion.tenant_id == user.tenant_id,
                LessonQuestion.course_id == course.id,
                LessonQuestion.lesson_id == lesson.id,
            )
            .order_by(LessonQuestion.position)
        )
    )
    question_ids = {question.id for question in questions}
    answer_ids = [str(answer.question_id) for answer in data.answers]
    if not questions or len(questions) != len(answer_ids) or set(answer_ids) != question_ids:
        raise HTTPException(422, "Submit one answer for every question in this lesson")
    supplied_answers = {str(answer.question_id): answer for answer in data.answers}
    current = exercise_output(db, user, lesson, assignment)
    if current.completed:
        return current
    stored = {
        answer.question_id: answer
        for answer in db.scalars(
            select(LessonAnswer).where(
                LessonAnswer.tenant_id == user.tenant_id,
                LessonAnswer.assignment_id == assignment.id,
                LessonAnswer.lesson_id == lesson.id,
            )
        )
    }
    all_accepted = True
    for question in questions:
        # Match by ID, never by client-provided order.
        supplied = supplied_answers[question.id]
        response = supplied.response.strip()
        if not response:
            raise HTTPException(422, "Answers cannot be blank")
        if question.kind == "multiple_choice":
            if not response.isascii() or not response.isdecimal():
                raise HTTPException(422, "Choose one of the provided options")
            selected = int(response)
            if response != str(selected) or selected >= len(question.options):
                raise HTTPException(422, "Choose one of the provided options")
            is_correct = selected == question.correct_option
            all_accepted = all_accepted and is_correct
        else:
            is_correct = None  # Text is recorded as submitted, not automatically graded.
        answer = stored.get(question.id)
        if answer is None:
            answer = LessonAnswer(
                tenant_id=user.tenant_id,
                assignment_id=assignment.id,
                course_id=course.id,
                user_id=user.id,
                lesson_id=lesson.id,
                question_id=question.id,
            )
            db.add(answer)
        answer.response = response
        answer.is_correct = is_correct
        answer.submitted_at = datetime.now(UTC)
    if all_accepted:
        db.add(
            LessonProgress(
                tenant_id=user.tenant_id,
                assignment_id=assignment.id,
                course_id=course.id,
                user_id=user.id,
                lesson_id=lesson.id,
            )
        )
    commit(db)
    return exercise_output(db, user, lesson, assignment)
