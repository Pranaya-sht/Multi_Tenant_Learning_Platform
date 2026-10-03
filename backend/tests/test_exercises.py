import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import LessonAnswer
from tests.support import assign, course, request


def question_payload(kind="multiple_choice"):
    if kind == "text":
        return {"kind": "text", "prompt": "Explain the idea in your own words."}
    return {
        "kind": "multiple_choice",
        "prompt": "Which value is true?",
        "options": ["False", "True", "Unknown"],
        "correct_option": 1,
    }


def test_lesson_questions_drive_progress_and_hide_answer_key(api):
    data = course(api)
    lesson_id = data["lessons"][0]["id"]
    base = f"/tenant/courses/{data['id']}/lessons/{lesson_id}"
    mcq = request(api, "POST", base + "/questions", json=question_payload()).json()
    text = request(api, "POST", base + "/questions", json=question_payload("text")).json()
    assignment = assign(api, data).json()
    exercise_path = base + "/exercise"
    exercise = request(api, "GET", exercise_path, "la")
    assert exercise.status_code == 200
    assert [item["id"] for item in exercise.json()["questions"]] == [mcq["id"], text["id"]]
    assert "correct_option" not in exercise.text
    assert (
        request(
            api,
            "PUT",
            f"/tenant/assignments/{assignment['id']}/lessons/{lesson_id}/complete",
            "la",
        ).status_code
        == 409
    )

    answers = [
        {"question_id": mcq["id"], "response": "0"},
        {"question_id": text["id"], "response": "  My explanation.  "},
    ]
    attempt = request(api, "PUT", exercise_path, "la", json={"answers": answers})
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["completed"] is False
    assert [item["is_correct"] for item in attempt.json()["answers"]] == [False, None]
    assert (
        request(api, "GET", f"/tenant/assignments/{assignment['id']}/progress", "la").json()[
            "completed_lessons"
        ]
        == 0
    )

    answers[0]["response"] = "1"
    passed = request(api, "PUT", exercise_path, "la", json={"answers": answers})
    assert passed.status_code == 200, passed.text
    assert passed.json()["completed"] is True
    assert (
        request(api, "PUT", exercise_path, "la", json={"answers": answers}).json() == passed.json()
    )
    progress = request(api, "GET", f"/tenant/assignments/{assignment['id']}/progress", "la").json()
    assert progress["total_lessons"] == 2
    assert progress["completed_lessons"] == 1
    assert progress["percent_complete"] == 50
    submissions = request(api, "GET", base + "/answers")
    assert submissions.status_code == 200
    assert {item["question_id"]: item["response"] for item in submissions.json()} == {
        mcq["id"]: "1",
        text["id"]: "My explanation.",
    }
    assert all(item["user_id"] == api.users["la"].id for item in submissions.json())
    assert request(api, "GET", base + "/answers", "la").status_code == 403
    assert request(api, "GET", base + "/answers", "tb").status_code == 404
    assert (
        request(api, "GET", f"/tenant/courses/{data['id']}/questions").json()[0]["correct_option"]
        == 1
    )


def test_question_mutations_are_admin_only_tenant_scoped_and_locked_after_enrollment(api):
    data = course(api)
    lesson_id = data["lessons"][0]["id"]
    base = f"/tenant/courses/{data['id']}/lessons/{lesson_id}"
    payload = question_payload()
    assert request(api, "POST", base + "/questions", "la", json=payload).status_code == 403
    assert request(api, "POST", base + "/questions", "tb", json=payload).status_code == 404
    assert request(api, "GET", f"/tenant/courses/{data['id']}/questions", "la").status_code == 403
    assert (
        request(api, "POST", base + "/questions", json={**payload, "correct_option": 3}).status_code
        == 422
    )
    question = request(api, "POST", base + "/questions", json=payload).json()
    edited = request(
        api,
        "PUT",
        base + f"/questions/{question['id']}",
        json={**payload, "prompt": "Updated prompt"},
    )
    assert edited.status_code == 200
    assert edited.json()["prompt"] == "Updated prompt"
    assert (
        request(api, "GET", base + "/exercise", "la").status_code == 404
    )  # Learner is not enrolled yet.
    assign(api, data)
    assert request(api, "POST", base + "/questions", json=payload).status_code == 409
    assert (
        request(api, "PUT", base + f"/questions/{question['id']}", json=payload).status_code == 409
    )
    assert request(api, "DELETE", base + f"/questions/{question['id']}").status_code == 409
    assert request(api, "GET", base + "/exercise", "lb").status_code == 404
    assert request(api, "GET", base + "/exercise", "la2").status_code == 404


def test_answer_ids_and_options_are_validated_and_revoke_cascades_answers(api):
    data = course(api)
    lesson_id = data["lessons"][0]["id"]
    base = f"/tenant/courses/{data['id']}/lessons/{lesson_id}"
    question = request(api, "POST", base + "/questions", json=question_payload()).json()
    assignment = assign(api, data).json()
    path = base + "/exercise"
    for answer in (
        {"question_id": question["id"], "response": "7"},
        {"question_id": question["id"], "response": "-1"},
        {"question_id": data["lessons"][1]["id"], "response": "1"},
    ):
        assert request(api, "PUT", path, "la", json={"answers": [answer]}).status_code == 422
    answer = {"question_id": question["id"], "response": "1"}
    assert request(api, "PUT", path, "la", json={"answers": [answer, answer]}).status_code == 422
    assert request(api, "PUT", path, "la", json={"answers": [answer]}).status_code == 200
    with Session(api.database) as session:
        assert session.scalar(select(func.count()).select_from(LessonAnswer)) == 1
    assert request(api, "DELETE", f"/tenant/assignments/{assignment['id']}").status_code == 204
    with Session(api.database) as session:
        assert session.scalar(select(func.count()).select_from(LessonAnswer)) == 0


def test_expiration_blocks_question_access_and_submission_until_reactivated(api):
    data = course(api)
    lesson_id = data["lessons"][0]["id"]
    base = f"/tenant/courses/{data['id']}/lessons/{lesson_id}"
    question = request(api, "POST", base + "/questions", json=question_payload()).json()
    assign(api, data)
    tenant_id = api.tenants["a"].id
    assert request(api, "POST", f"/tenants/{tenant_id}/expire", "root").status_code == 200
    assert request(api, "GET", base + "/exercise", "la").status_code == 403
    assert (
        request(
            api,
            "PUT",
            base + "/exercise",
            "la",
            json={"answers": [{"question_id": question["id"], "response": "1"}]},
        ).status_code
        == 403
    )
    assert request(api, "GET", f"/tenant/courses/{data['id']}/questions").status_code == 403
    assert (
        request(
            api, "POST", f"/tenants/{tenant_id}/reactivate", "root", json={"days": 7}
        ).status_code
        == 200
    )
    assert request(api, "GET", base + "/exercise", "la").status_code == 200


def test_database_rejects_answer_link_to_another_tenants_question(api):
    own = course(api)
    other = course(api, "tb")
    other_lesson = other["lessons"][0]["id"]
    foreign_question = request(
        api,
        "POST",
        f"/tenant/courses/{other['id']}/lessons/{other_lesson}/questions",
        "tb",
        json=question_payload(),
    ).json()
    enrollment = assign(api, own).json()
    with Session(api.database) as session:
        session.add(
            LessonAnswer(
                tenant_id=api.tenants["a"].id,
                assignment_id=enrollment["id"],
                course_id=own["id"],
                user_id=api.users["la"].id,
                lesson_id=own["lessons"][0]["id"],
                question_id=foreign_question["id"],
                response="1",
                is_correct=True,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
