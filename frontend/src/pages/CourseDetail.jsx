import { useState } from 'react'
import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { formatDate } from '../lib/roles.js'
import { Icon } from '../components/Icon.jsx'
import { LearnerPicker } from '../components/LearnerPicker.jsx'
import {
  ActionDialog,
  Badge,
  Button,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
  ProgressBar,
  Records,
  ResourceBoundary,
} from '../components/UI.jsx'

export function CourseDetail({ id }) {
  const { user, request } = useAuth()
  const course = useResource(`/tenant/courses/${id}`)
  const assignments = useResource('/tenant/assignments', true)
  const admin = user.role === 'tenant_admin'
  const questions = useResource(admin ? `/tenant/courses/${id}/questions` : null)
  const people = useResource(admin ? '/tenant/users' : null, true)
  const [dialog, setDialog] = useState(null)
  const [selectedLearnerIds, setSelectedLearnerIds] = useState([])
  const [notice, setNotice] = useState('')
  const [enrollmentPage, setEnrollmentPage] = useState(0)
  const [responsesLesson, setResponsesLesson] = useState(null)
  const submissions = useResource(
    admin && responsesLesson ? `/tenant/courses/${id}/lessons/${responsesLesson}/answers` : null,
    true,
  )
  const attached = (assignments.data || []).filter((assignment) => assignment.course_id === id)
  const visibleEnrollments = attached.slice(enrollmentPage * 10, enrollmentPage * 10 + 10)
  const enrollmentProgress = useResource(
    admin && visibleEnrollments.length
      ? `/tenant/assignments/progress?${new URLSearchParams(
          visibleEnrollments.map((assignment) => ['assignment_ids', assignment.id]),
        )}`
      : null,
  )
  if (course.loading || assignments.loading || questions.loading || people.loading)
    return <Loading label="Loading course" />
  if (course.error || assignments.error || questions.error || people.error)
    return (
      <ErrorNotice
        error={course.error || assignments.error || questions.error || people.error}
        retry={() => {
          course.refresh()
          assignments.refresh()
          questions.refresh()
          people.refresh()
        }}
      />
    )
  const content = course.data
  const questionRows = questions.data || []
  const questionMap = Object.fromEntries(questionRows.map((question) => [question.id, question]))
  const learnerMap = Object.fromEntries((people.data || []).map((person) => [person.id, person]))
  const availableLearners = (people.data || []).filter(
    (person) =>
      person.role === 'tenant_user' &&
      person.is_active &&
      !attached.some((item) => item.user_id === person.id),
  )
  const progressMap = Object.fromEntries(
    (enrollmentProgress.data || []).map((item) => [item.assignment_id, item]),
  )
  async function save(values) {
    if (dialog.type === 'course')
      return request(`/tenant/courses/${id}`, { method: 'PATCH', body: values })
    if (dialog.type === 'enroll') {
      if (!selectedLearnerIds.length) throw new Error('Select at least one learner.')
      return request('/tenant/assignments/batch', {
        method: 'POST',
        body: { course_id: id, user_ids: selectedLearnerIds },
      })
    }
    if (dialog.type === 'revoke')
      return request(`/tenant/assignments/${dialog.assignment.id}`, { method: 'DELETE' })
    if (dialog.type === 'deleteQuestion')
      return request(
        `/tenant/courses/${id}/lessons/${dialog.lesson.id}/questions/${dialog.question.id}`,
        { method: 'DELETE' },
      )
    if (dialog.type === 'question') {
      const kind = dialog.kind || dialog.question?.kind || 'multiple_choice'
      const body = {
        kind,
        prompt: values.prompt,
        options:
          kind === 'multiple_choice' ? values.options.split('\n').map((item) => item.trim()) : [],
        correct_option: kind === 'multiple_choice' ? Number(values.correct_option) - 1 : null,
      }
      return request(
        `/tenant/courses/${id}/lessons/${dialog.lesson.id}/questions${dialog.question ? `/${dialog.question.id}` : ''}`,
        { method: dialog.question ? 'PUT' : 'POST', body },
      )
    }
    return request(`/tenant/courses/${id}/lessons${dialog.lesson ? `/${dialog.lesson.id}` : ''}`, {
      method: dialog.lesson ? 'PUT' : 'POST',
      body: dialog.lesson ? values : { ...values, position: Number(values.position) },
    })
  }
  return (
    <>
      <a className="back-link" href="#/courses">
        ← All courses
      </a>
      <PageHeading
        eyebrow="Course workspace"
        title={content.title}
        description={content.description}
        action={
          admin && (
            <Button kind="secondary" onClick={() => setDialog({ type: 'course' })}>
              Edit course
            </Button>
          )
        }
      />
      <div className="course-meta">
        <Badge active={!content.is_archived}>
          {content.is_archived ? 'Archived course' : 'Available course'}
        </Badge>
        <span>
          {content.lessons.length} {content.lessons.length === 1 ? 'lesson' : 'lessons'}
        </span>
        {admin && <span>{attached.length} enrolled learners</span>}
      </div>
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      {admin ? (
        <section className="surface">
          <div className="section-heading">
            <div>
              <h2>Course lessons</h2>
              <p>
                {attached.length
                  ? 'Lessons and questions are fixed while learners are enrolled. You can still edit lesson content.'
                  : 'Add lessons and their questions before enrolling learners.'}
              </p>
            </div>
            <Button onClick={() => setDialog({ type: 'lesson' })} disabled={attached.length > 0}>
              <Icon name="plus" />
              Add lesson
            </Button>
          </div>
          {content.lessons.length ? (
            <ol className="lesson-editor-list">
              {content.lessons.map((lesson) => (
                <li key={lesson.id}>
                  <span className="lesson-number">{String(lesson.position).padStart(2, '0')}</span>
                  <div className="record-content">
                    <h3>{lesson.title}</h3>
                    <p className="lesson-preview">{lesson.content}</p>
                    <div className="lesson-questions">
                      <div className="actions">
                        <strong>
                          Lesson assignment (
                          {questionRows.filter((item) => item.lesson_id === lesson.id).length})
                        </strong>
                        <Button
                          kind="quiet"
                          disabled={attached.length > 0}
                          onClick={() =>
                            setDialog({ type: 'question', lesson, kind: 'multiple_choice' })
                          }
                        >
                          Add question
                        </Button>
                        {questionRows.some((item) => item.lesson_id === lesson.id) && (
                          <Button
                            kind="quiet"
                            onClick={() =>
                              setResponsesLesson(responsesLesson === lesson.id ? null : lesson.id)
                            }
                          >
                            {responsesLesson === lesson.id ? 'Hide answers' : 'View answers'}
                          </Button>
                        )}
                      </div>
                      {questionRows
                        .filter((item) => item.lesson_id === lesson.id)
                        .map((question) => (
                          <div className="lesson-question" key={question.id}>
                            <p>
                              {question.position}. {question.prompt}
                            </p>
                            <small>
                              {question.kind === 'multiple_choice'
                                ? `Multiple choice · ${question.options.length} options`
                                : 'Text answer'}
                            </small>
                            {!attached.length && (
                              <div className="actions">
                                <Button
                                  kind="quiet"
                                  onClick={() =>
                                    setDialog({
                                      type: 'question',
                                      lesson,
                                      question,
                                      kind: question.kind,
                                    })
                                  }
                                >
                                  Edit question
                                </Button>
                                <Button
                                  kind="quiet"
                                  onClick={() =>
                                    setDialog({ type: 'deleteQuestion', lesson, question })
                                  }
                                >
                                  Remove question
                                </Button>
                              </div>
                            )}
                          </div>
                        ))}
                      {responsesLesson === lesson.id && (
                        <div className="lesson-submissions">
                          <div className="actions">
                            <strong>Learner answers</strong>
                            <Button kind="quiet" onClick={submissions.refresh}>
                              Refresh answers
                            </Button>
                          </div>
                          <ResourceBoundary resource={submissions}>
                            {submissions.data?.length ? (
                              <ul>
                                {submissions.data.map((answer) => (
                                  <li key={`${answer.user_id}:${answer.question_id}`}>
                                    <strong>
                                      {learnerMap[answer.user_id]?.name || 'Learner unavailable'}
                                    </strong>
                                    <p>
                                      {questionMap[answer.question_id]?.prompt ||
                                        'Question unavailable'}
                                    </p>
                                    <p className="lesson-preview">
                                      {questionMap[answer.question_id]?.kind === 'multiple_choice'
                                        ? questionMap[answer.question_id]?.options[
                                            Number(answer.response)
                                          ] || answer.response
                                        : answer.response}
                                    </p>
                                    <small>
                                      {answer.is_correct === null
                                        ? 'Text submitted'
                                        : answer.is_correct
                                          ? 'Correct'
                                          : 'Needs retry'}
                                    </small>
                                  </li>
                                ))}
                              </ul>
                            ) : (
                              <p>No answers submitted yet.</p>
                            )}
                          </ResourceBoundary>
                        </div>
                      )}
                    </div>
                  </div>
                  <Button kind="secondary" onClick={() => setDialog({ type: 'lesson', lesson })}>
                    Edit lesson
                  </Button>
                </li>
              ))}
            </ol>
          ) : (
            <Empty title="Give this course its first lesson">
              Add a title and learning content. Then assign the course to your learners.
            </Empty>
          )}
        </section>
      ) : attached[0] ? (
        <LessonReader course={content} assignment={attached[0]} />
      ) : (
        <Empty title="Assignment unavailable">
          This course is no longer assigned to your account.
        </Empty>
      )}
      {admin && (
        <section className="surface course-enrollment">
          <div className="section-heading">
            <div>
              <h2>Learners in this course</h2>
              <p>
                Enroll learners here after the lesson questions are ready. Their answers count
                toward lesson progress.
              </p>
            </div>
            <Button
              disabled={!content.lessons.length || content.is_archived || !availableLearners.length}
              onClick={() => {
                setSelectedLearnerIds([])
                setDialog({ type: 'enroll' })
              }}
            >
              <Icon name="plus" /> Enroll learners
            </Button>
          </div>
          <Records
            rows={attached}
            page={enrollmentPage}
            onPageChange={setEnrollmentPage}
            empty={
              <Empty title="No learners enrolled">
                Add lessons and questions, then enroll a learner.
              </Empty>
            }
            render={(assignment) => (
              <li className="record-row" key={assignment.id}>
                <span className="record-icon">
                  <Icon name="learners" />
                </span>
                <div className="record-content">
                  <strong>{learnerMap[assignment.user_id]?.name || 'Learner unavailable'}</strong>
                  <p>{learnerMap[assignment.user_id]?.email || assignment.user_id}</p>
                  <small>Enrolled {formatDate(assignment.assigned_at)}</small>
                  {progressMap[assignment.id] && (
                    <ProgressBar progress={progressMap[assignment.id]} />
                  )}
                </div>
                <Button kind="quiet" onClick={() => setDialog({ type: 'revoke', assignment })}>
                  Revoke access
                </Button>
              </li>
            )}
          />
          {enrollmentProgress.error && (
            <ErrorNotice error={enrollmentProgress.error} retry={enrollmentProgress.refresh} />
          )}
        </section>
      )}
      {dialog && (
        <ActionDialog
          title={
            dialog.type === 'course'
              ? 'Edit course'
              : dialog.type === 'lesson'
                ? dialog.lesson
                  ? 'Edit lesson'
                  : 'Add lesson'
                : dialog.type === 'question'
                  ? dialog.question
                    ? 'Edit question'
                    : 'Add question'
                  : dialog.type === 'deleteQuestion'
                    ? 'Remove question'
                    : dialog.type === 'enroll'
                      ? 'Enroll learners'
                      : 'Revoke access'
          }
          onClose={() => setDialog(null)}
          action={save}
          onSaved={() => {
            setDialog(null)
            course.refresh()
            assignments.refresh()
            questions.refresh()
            setNotice('Changes saved.')
          }}
          submitLabel={
            dialog.type === 'lesson' && !dialog.lesson
              ? 'Add lesson'
              : dialog.type === 'question'
                ? dialog.question
                  ? 'Save question'
                  : 'Add question'
                : dialog.type === 'deleteQuestion'
                  ? 'Remove question'
                  : dialog.type === 'enroll'
                    ? 'Enroll learners'
                    : dialog.type === 'revoke'
                      ? 'Revoke access'
                      : 'Save changes'
          }
          explanation={
            dialog.type === 'revoke'
              ? 'The learner loses course access. Their answers and progress for this enrollment are permanently removed.'
              : dialog.type === 'deleteQuestion'
                ? 'Remove this question before learners enroll. This action cannot be undone.'
                : undefined
          }
        >
          {['course', 'lesson'].includes(dialog.type) && (
            <Field
              label={dialog.type === 'course' ? 'Course title' : 'Lesson title'}
              name="title"
              required
              maxLength={200}
              defaultValue={dialog.type === 'course' ? content.title : dialog.lesson?.title || ''}
            />
          )}
          {dialog.type === 'course' ? (
            <Field
              label="Description"
              name="description"
              multiline
              maxLength={20000}
              defaultValue={content.description}
            />
          ) : dialog.type === 'lesson' ? (
            <>
              <Field
                label="Lesson content"
                name="content"
                multiline
                rows={10}
                required
                maxLength={100000}
                defaultValue={dialog.lesson?.content || ''}
                hint="Plain text. Line breaks are preserved."
              />
              {!dialog.lesson && (
                <Field
                  label="Lesson position"
                  name="position"
                  type="number"
                  required
                  min={1}
                  defaultValue={
                    Math.max(0, ...content.lessons.map((lesson) => lesson.position)) + 1
                  }
                />
              )}
            </>
          ) : dialog.type === 'question' ? (
            <>
              <Field
                label="Question type"
                name="kind"
                value={dialog.kind || 'multiple_choice'}
                onChange={(event) => setDialog({ ...dialog, kind: event.target.value })}
              >
                <option value="multiple_choice">Multiple choice</option>
                <option value="text">Text answer</option>
              </Field>
              <Field
                label="Question"
                name="prompt"
                multiline
                required
                maxLength={5000}
                defaultValue={dialog.question?.prompt || ''}
              />
              {dialog.kind === 'multiple_choice' && (
                <>
                  <Field
                    label="Answer options"
                    name="options"
                    multiline
                    required
                    rows={5}
                    defaultValue={dialog.question?.options.join('\n') || ''}
                    hint="Enter 2–6 options, one per line."
                  />
                  <Field
                    label="Correct option number"
                    name="correct_option"
                    type="number"
                    min={1}
                    max={6}
                    required
                    defaultValue={
                      dialog.question?.correct_option != null
                        ? dialog.question.correct_option + 1
                        : 1
                    }
                  />
                </>
              )}
            </>
          ) : dialog.type === 'enroll' ? (
            <LearnerPicker
              learners={availableLearners}
              selectedIds={selectedLearnerIds}
              onChange={setSelectedLearnerIds}
            />
          ) : null}
        </ActionDialog>
      )}
    </>
  )
}

function LessonReader({ course, assignment }) {
  const { request } = useAuth()
  const progress = useResource(`/tenant/assignments/${assignment.id}/progress`)
  const [selected, setSelected] = useState(course.lessons[0]?.id)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState('')
  const lesson = course.lessons.find((item) => item.id === selected) || course.lessons[0]
  const exercise = useResource(
    lesson ? `/tenant/courses/${course.id}/lessons/${lesson.id}/exercise` : null,
  )
  const [draft, setDraft] = useState({ lessonId: null, values: {} })
  const responses = {
    ...Object.fromEntries(
      (exercise.data?.answers || []).map((answer) => [answer.question_id, answer.response]),
    ),
    ...(draft.lessonId === lesson?.id ? draft.values : {}),
  }
  function updateResponse(questionId, value) {
    setDraft((current) => ({
      lessonId: lesson.id,
      values: { ...(current.lessonId === lesson.id ? current.values : {}), [questionId]: value },
    }))
  }
  const completed = progress.data?.completed_lesson_ids || []
  const currentIndex = course.lessons.findIndex((item) => item.id === lesson?.id)
  async function complete() {
    setPending(true)
    setError(null)
    try {
      await request(`/tenant/assignments/${assignment.id}/lessons/${lesson.id}/complete`, {
        method: 'PUT',
      })
      progress.refresh()
      setNotice('Lesson completed. Your progress is saved.')
    } catch (failure) {
      setError(failure)
    } finally {
      setPending(false)
    }
  }
  async function submitExercise(event) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      const result = await request(`/tenant/courses/${course.id}/lessons/${lesson.id}/exercise`, {
        method: 'PUT',
        body: {
          answers: exercise.data.questions.map((question) => ({
            question_id: question.id,
            response: responses[question.id] || '',
          })),
        },
      })
      exercise.refresh()
      progress.refresh()
      setNotice(
        result.completed
          ? 'Answers saved. This lesson now counts toward your progress.'
          : 'Answers saved. Try the multiple-choice questions marked incorrect.',
      )
    } catch (failure) {
      setError(failure)
    } finally {
      setPending(false)
    }
  }
  if (!lesson)
    return (
      <Empty title="No lessons yet">Your institute administrator is preparing this course.</Empty>
    )
  return (
    <div className="reader-layout">
      <aside className="surface lesson-outline">
        <div className="section-heading">
          <h2>Your course</h2>
        </div>
        <div className="outline-progress">
          <ResourceBoundary resource={progress}>
            <ProgressBar progress={progress.data} />
          </ResourceBoundary>
        </div>
        <nav aria-label="Course lessons">
          {course.lessons.map((item) => (
            <button
              className={`lesson-nav ${item.id === lesson.id ? 'selected' : ''}`}
              key={item.id}
              type="button"
              aria-current={item.id === lesson.id ? 'step' : undefined}
              onClick={() => {
                setSelected(item.id)
                setNotice('')
                setError(null)
              }}
              disabled={pending}
            >
              <span className="lesson-step">
                {completed.includes(item.id) ? <Icon name="check" /> : item.position}
              </span>
              <span>
                {item.title}
                {completed.includes(item.id) && <small>Completed</small>}
              </span>
            </button>
          ))}
        </nav>
      </aside>
      <article className="surface lesson-reading">
        <p className="eyebrow">
          Lesson {lesson.position} of {course.lessons.length}
        </p>
        <h2>{lesson.title}</h2>
        <div className="lesson-body">{lesson.content}</div>
        {exercise.loading && <Loading label="Loading lesson questions" />}
        {exercise.error && <ErrorNotice error={exercise.error} retry={exercise.refresh} />}
        {exercise.data?.questions.length > 0 && (
          <section className="lesson-exercise" aria-label="Lesson assignment">
            <h3>Lesson assignment</h3>
            <p>
              Answer every question. Multiple-choice answers must be correct; text answers count
              when submitted.
            </p>
            <form onSubmit={submitExercise}>
              <fieldset disabled={pending || exercise.data.completed}>
                {exercise.data.questions.map((question) => {
                  const saved = exercise.data.answers.find(
                    (answer) => answer.question_id === question.id,
                  )
                  return (
                    <div className="exercise-question" key={question.id}>
                      {question.kind === 'multiple_choice' ? (
                        <fieldset>
                          <legend>
                            {question.position}. {question.prompt}
                          </legend>
                          {question.options.map((option, index) => (
                            <label className="exercise-option" key={index}>
                              <input
                                type="radio"
                                name={`question-${question.id}`}
                                value={index}
                                checked={responses[question.id] === String(index)}
                                onChange={() => updateResponse(question.id, String(index))}
                                required
                              />
                              {option}
                            </label>
                          ))}
                        </fieldset>
                      ) : (
                        <Field
                          label={`${question.position}. ${question.prompt}`}
                          name={`question-${question.id}`}
                          multiline
                          required
                          maxLength={5000}
                          value={responses[question.id] || ''}
                          onChange={(event) => updateResponse(question.id, event.target.value)}
                        />
                      )}
                      {saved?.is_correct === false && (
                        <p className="exercise-feedback">Try another answer.</p>
                      )}
                      {saved && saved.is_correct === null && (
                        <p className="exercise-feedback">Text answer submitted.</p>
                      )}
                    </div>
                  )
                })}
              </fieldset>
              {!exercise.data.completed && (
                <Button type="submit" disabled={pending}>
                  {pending ? 'Saving answers…' : 'Submit answers'}
                </Button>
              )}
            </form>
          </section>
        )}
        <ErrorNotice error={error} />
        {notice && (
          <p className="notice" role="status">
            {notice}
          </p>
        )}
        <div className="lesson-footer">
          {completed.includes(lesson.id) ? (
            <Badge active>Lesson complete</Badge>
          ) : exercise.data?.questions.length ? null : (
            <Button
              onClick={complete}
              disabled={
                pending ||
                progress.loading ||
                Boolean(progress.error) ||
                exercise.loading ||
                Boolean(exercise.error)
              }
            >
              {pending ? 'Saving progress…' : 'Complete lesson'}
              <Icon name="check" />
            </Button>
          )}
          {currentIndex < course.lessons.length - 1 && (
            <Button
              kind="secondary"
              disabled={pending}
              onClick={() => {
                setSelected(course.lessons[currentIndex + 1].id)
                setNotice('')
                setError(null)
              }}
            >
              Next lesson
              <Icon name="arrow" />
            </Button>
          )}
        </div>
      </article>
    </div>
  )
}
