import { useState } from 'react'
import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { Icon } from '../components/Icon.jsx'
import {
  ActionDialog,
  Badge,
  Button,
  Empty,
  Field,
  PageHeading,
  Records,
  ResourceBoundary,
} from '../components/UI.jsx'

export function Courses({ search }) {
  const { user, request } = useAuth()
  const admin = user.role === 'tenant_admin'
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(0)
  const courses = useResource(
    `/tenant/courses/page?limit=10&offset=${page * 10}&q=${encodeURIComponent(query)}&status=${status}`,
  )
  const [dialog, setDialog] = useState(admin && search.get('create') ? { type: 'create' } : null)
  const [notice, setNotice] = useState('')
  const rows = courses.data?.items || []
  function close() {
    setDialog(null)
    if (search.has('create')) window.location.hash = '/courses'
  }
  return (
    <>
      <PageHeading
        eyebrow={admin ? 'Learning workspace' : 'Your learning'}
        title={admin ? 'Courses' : 'My courses'}
        description={
          admin
            ? 'Build a curriculum worth coming back to.'
            : 'Your assigned courses, ready when you are.'
        }
        action={
          admin && (
            <Button onClick={() => setDialog({ type: 'create' })}>
              <Icon name="plus" />
              Create course
            </Button>
          )
        }
      />
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="filters">
        <Field
          label="Search courses"
          type="search"
          placeholder="Search by title or description"
          value={query}
          maxLength={200}
          onChange={(event) => {
            setQuery(event.target.value)
            setPage(0)
          }}
        />
        <Field
          label="Course status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value)
            setPage(0)
          }}
        >
          <option value="all">All courses</option>
          <option value="active">Available</option>
          <option value="archived">Archived</option>
        </Field>
      </div>
      <section className="surface">
        <ResourceBoundary resource={courses}>
          <Records
            key={`${query}:${status}`}
            page={page}
            onPageChange={setPage}
            total={courses.data?.total}
            rows={rows}
            empty={
              <Empty
                title={
                  query || status !== 'all'
                    ? 'No matching courses'
                    : admin
                      ? 'Make room for your first course'
                      : 'Your next course is on its way'
                }
              >
                {admin
                  ? 'Create a course, add lessons, then assign it to your learners.'
                  : 'Your institute administrator will assign courses to you here.'}
              </Empty>
            }
            render={(course) => (
              <li className="record-row" key={course.id}>
                <span className="record-icon">
                  <Icon name="book" />
                </span>
                <div className="record-content">
                  <a className="record-title" href={`#/courses/${course.id}`}>
                    {course.title}
                  </a>
                  <p>{course.description || 'No description yet.'}</p>
                  <Badge active={!course.is_archived}>
                    {course.is_archived ? 'Archived' : 'Available'}
                  </Badge>
                </div>
                <div className="actions">
                  <a className="btn btn-secondary" href={`#/courses/${course.id}`}>
                    {admin ? 'Read course' : 'Open course'}
                    <Icon name="arrow" />
                  </a>
                  {admin && (
                    <Button kind="quiet" onClick={() => setDialog({ type: 'edit', course })}>
                      Edit
                    </Button>
                  )}
                  {admin && (
                    <Button kind="quiet" onClick={() => setDialog({ type: 'archive', course })}>
                      {course.is_archived ? 'Restore' : 'Archive'}
                    </Button>
                  )}
                </div>
              </li>
            )}
          />
        </ResourceBoundary>
      </section>
      {dialog && (
        <ActionDialog
          title={
            dialog.type === 'create'
              ? 'Create course'
              : dialog.type === 'edit'
                ? 'Edit course'
                : dialog.course.is_archived
                  ? 'Restore course'
                  : 'Archive course'
          }
          onClose={close}
          explanation={
            dialog.type === 'archive'
              ? 'Existing lessons, assignments, and progress are kept. Archived courses remain readable by existing learners and cannot receive new assignments.'
              : undefined
          }
          submitLabel={
            dialog.type === 'create'
              ? 'Create course'
              : dialog.type === 'archive'
                ? dialog.course.is_archived
                  ? 'Restore course'
                  : 'Archive course'
                : 'Save changes'
          }
          action={(values) =>
            request(
              dialog.type === 'create' ? '/tenant/courses' : `/tenant/courses/${dialog.course.id}`,
              {
                method: dialog.type === 'create' ? 'POST' : 'PATCH',
                body:
                  dialog.type === 'archive' ? { is_archived: !dialog.course.is_archived } : values,
              },
            )
          }
          onSaved={(course) => {
            close()
            setNotice('Course saved.')
            setPage(0)
            courses.refresh()
            if (dialog.type === 'create') window.location.hash = `/courses/${course.id}`
          }}
        >
          {dialog.type !== 'archive' && (
            <>
              <Field
                label="Course title"
                name="title"
                required
                maxLength={200}
                defaultValue={dialog.course?.title || ''}
              />
              <Field
                label="Description"
                name="description"
                multiline
                maxLength={20000}
                defaultValue={dialog.course?.description || ''}
              />
            </>
          )}
        </ActionDialog>
      )}
    </>
  )
}
