import { useState } from 'react'
import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { formatDate } from '../lib/roles.js'
import { Icon } from '../components/Icon.jsx'
import {
  ActionDialog,
  Badge,
  Empty,
  ErrorNotice,
  Field,
  Loading,
  PageHeading,
  ProgressBar,
  Records,
} from '../components/UI.jsx'

export function Assignments({ search }) {
  const { user, request } = useAuth()
  const admin = user.role === 'tenant_admin'
  const assignments = useResource('/tenant/assignments', true)
  const courses = useResource('/tenant/courses', true)
  const people = useResource(admin ? '/tenant/users' : null, true)
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(0)
  const [dialog, setDialog] = useState(
    admin && search.get('course') ? { type: 'create', courseId: search.get('course') } : null,
  )
  const [notice, setNotice] = useState('')
  function close() {
    setDialog(null)
    if (search.has('course')) window.location.hash = '/assignments'
  }
  const courseMap = Object.fromEntries((courses.data || []).map((course) => [course.id, course]))
  const peopleMap = Object.fromEntries((people.data || []).map((person) => [person.id, person]))
  const rows = (assignments.data || []).filter((assignment) =>
    `${courseMap[assignment.course_id]?.title || ''} ${peopleMap[assignment.user_id]?.name || ''}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  )
  const visiblePage = Math.min(page, Math.max(0, Math.ceil(rows.length / 10) - 1))
  const visibleRows = rows.slice(visiblePage * 10, visiblePage * 10 + 10)
  const progressPath = visibleRows.length
    ? `/tenant/assignments/progress?${new URLSearchParams(
        visibleRows.map((assignment) => ['assignment_ids', assignment.id]),
      )}`
    : null
  const progress = useResource(progressPath)
  const progressMap = Object.fromEntries(
    (progress.data || []).map((item) => [item.assignment_id, item]),
  )
  if (assignments.loading || courses.loading || (admin && people.loading))
    return <Loading label="Loading assignments" />
  if (assignments.error || courses.error || people.error)
    return (
      <ErrorNotice
        error={assignments.error || courses.error || people.error}
        retry={() => {
          assignments.refresh()
          courses.refresh()
          people.refresh()
        }}
      />
    )
  if (progress.error) return <ErrorNotice error={progress.error} retry={progress.refresh} />
  const available = courses.data.filter((course) => !course.is_archived)
  const learners = (people.data || []).filter(
    (person) => person.role === 'tenant_user' && person.is_active,
  )
  return (
    <>
      <PageHeading
        eyebrow={admin ? 'Learning workspace' : 'Your learning'}
        title={admin ? 'Progress' : 'My progress'}
        description={
          admin
            ? 'Follow learner progress across courses. Open a course to enroll learners.'
            : 'Every lesson is another step forward.'
        }
      />
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="filters">
        <Field
          label="Search progress"
          type="search"
          placeholder={admin ? 'Course or learner name' : 'Course title'}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(0)
          }}
        />
      </div>
      <section className="surface">
        <Records
          key={query}
          page={page}
          onPageChange={setPage}
          rows={rows}
          empty={
            <Empty icon="assignment" title="No course progress yet">
              {admin
                ? 'Open a course to enroll a learner after adding lessons and questions.'
                : 'Your assigned course progress will appear here.'}
            </Empty>
          }
          render={(assignment) => (
            <AssignmentRow
              key={assignment.id}
              assignment={assignment}
              course={courseMap[assignment.course_id]}
              person={peopleMap[assignment.user_id]}
              admin={admin}
              progress={progressMap[assignment.id]}
              progressLoading={progress.loading}
            />
          )}
        />
      </section>
      {dialog && (
        <ActionDialog
          title={dialog.type === 'create' ? 'Assign course' : 'Revoke assignment'}
          onClose={close}
          submitLabel={dialog.type === 'create' ? 'Assign course' : 'Revoke assignment'}
          explanation={
            dialog.type === 'create'
              ? 'Courses must contain at least one lesson. The learner must be active in this institute.'
              : 'This learner will lose access to the course. This assignment’s saved progress will be permanently removed; the course and account are kept.'
          }
          action={(values) =>
            request(
              dialog.type === 'create'
                ? '/tenant/assignments'
                : `/tenant/assignments/${dialog.assignment.id}`,
              {
                method: dialog.type === 'create' ? 'POST' : 'DELETE',
                ...(dialog.type === 'create' ? { body: values } : {}),
              },
            )
          }
          onSaved={() => {
            close()
            assignments.refresh()
            setNotice('Assignments updated.')
          }}
        >
          {dialog.type === 'create' && (
            <>
              {(!available.length || !learners.length) && (
                <div className="notice">
                  Add an available course and an active learner before assigning.
                </div>
              )}
              <Field label="Course" name="course_id" required defaultValue={dialog.courseId || ''}>
                <option value="" disabled>
                  Select a course
                </option>
                {available.map((course) => (
                  <option key={course.id} value={course.id}>
                    {course.title}
                  </option>
                ))}
              </Field>
              <Field label="Learner" name="user_id" required defaultValue="">
                <option value="" disabled>
                  Select a learner
                </option>
                {learners.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.name} · {person.email}
                  </option>
                ))}
              </Field>
            </>
          )}
        </ActionDialog>
      )}
    </>
  )
}

function AssignmentRow({ assignment, course, person, admin, progress, progressLoading }) {
  return (
    <li className="assignment-row">
      <div className="record-row">
        <span className="record-icon">
          <Icon name="assignment" />
        </span>
        <div className="record-content">
          <a className="record-title" href={`#/courses/${assignment.course_id}`}>
            {course?.title || 'Course unavailable'}
          </a>
          {admin && (
            <p>
              {person?.name || 'Account unavailable'} · {person?.email}
            </p>
          )}
          <small>Assigned {formatDate(assignment.assigned_at)}</small>
        </div>
        <div className="actions">
          <a className="btn btn-secondary" href={`#/courses/${assignment.course_id}`}>
            {admin ? 'Read course' : 'Continue learning'}
            <Icon name="arrow" />
          </a>
        </div>
      </div>
      <div className="assignment-progress">
        {progressLoading ? (
          <Loading label="Loading progress" />
        ) : (
          <ProgressBar progress={progress} />
        )}
        {progress?.is_complete && <Badge active>Course complete</Badge>}
      </div>
    </li>
  )
}
