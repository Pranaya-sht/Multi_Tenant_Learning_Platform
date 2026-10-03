import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { formatDate, isPlatform, roleLabels } from '../lib/roles.js'
import { Icon } from '../components/Icon.jsx'
import {
  Badge,
  Empty,
  ErrorNotice,
  Loading,
  PageHeading,
  ProgressBar,
  ResourceBoundary,
} from '../components/UI.jsx'

export function Overview({ tenant }) {
  const { user } = useAuth()
  const platform = isPlatform(user)
  const admin = user.role === 'tenant_admin'
  const primary = useResource(
    platform ? '/tenants' : '/tenant/courses/page?limit=4&offset=0',
    platform,
  )
  const secondary = useResource(
    platform ? '/platform-users' : admin ? '/tenant/users' : '/tenant/assignments',
    true,
  )
  if (primary.loading || secondary.loading) return <Loading />
  if (primary.error || secondary.error)
    return (
      <ErrorNotice
        error={primary.error || secondary.error}
        retry={() => {
          primary.refresh()
          secondary.refresh()
        }}
      />
    )
  const primaryRows = platform ? primary.data : primary.data.items
  const primaryCount = platform ? primary.data.length : primary.data.total
  return (
    <>
      <PageHeading
        eyebrow={platform ? 'Platform overview' : tenant.name}
        title={
          platform
            ? 'A place for every institute.'
            : admin
              ? 'Good learning starts here.'
              : 'Keep your curiosity moving.'
        }
        description={
          platform
            ? 'Support your institutes through every stage of their learning journey.'
            : admin
              ? 'Manage your courses, people, and their next steps.'
              : `Welcome back, ${user.name}. Your next lesson is waiting.`
        }
      />
      <div className="overview-layout">
        <div className="overview-main">
          <div className="stat-strip">
            <div>
              <strong>{primaryCount}</strong>
              <span>{platform ? 'Institutes' : admin ? 'Courses' : 'Assigned courses'}</span>
            </div>
            <div>
              <strong>{secondary.data.length}</strong>
              <span>
                {platform
                  ? 'Platform accounts'
                  : admin
                    ? 'People in your institute'
                    : 'Course assignments'}
              </span>
            </div>
          </div>
          <section className="surface">
            <div className="section-heading">
              <h2>{platform ? 'Your institutes' : 'Your courses'}</h2>
              <a className="text-link" href={platform ? '#/organizations' : '#/courses'}>
                View all
                <Icon name="arrow" />
              </a>
            </div>
            {primaryRows.length ? (
              <ul className="record-list">
                {primaryRows.slice(0, 4).map((item) => (
                  <li className="record-row" key={item.id}>
                    <span className="record-icon">
                      <Icon name={platform ? 'organization' : 'book'} />
                    </span>
                    <div className="record-content">
                      <a
                        className="record-title"
                        href={platform ? '#/organizations' : `#/courses/${item.id}`}
                      >
                        {platform ? item.name : item.title}
                      </a>
                      <p>
                        {platform ? item.slug : item.description || 'A new learning opportunity.'}
                      </p>
                      <Badge active={platform ? item.status === 'trial_active' : !item.is_archived}>
                        {platform
                          ? item.status === 'trial_active'
                            ? 'Trial active'
                            : item.status === 'expired'
                              ? 'Expired'
                              : 'Created'
                          : item.is_archived
                            ? 'Archived'
                            : 'Available'}
                      </Badge>
                    </div>
                    <a
                      className="btn btn-secondary"
                      href={platform ? '#/organizations' : `#/courses/${item.id}`}
                    >
                      {platform ? 'View institute' : admin ? 'Read course' : 'Continue'}
                      <Icon name="arrow" />
                    </a>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty
                icon={platform ? 'organization' : 'book'}
                title={
                  platform
                    ? 'Your first institute starts here'
                    : admin
                      ? 'Your curriculum starts here'
                      : 'Your learning space is ready'
                }
              >
                {platform
                  ? 'Create an institute and invite its administrator.'
                  : admin
                    ? 'Create a course and add lessons for your learners.'
                    : 'Your administrator will assign courses to you here.'}
              </Empty>
            )}
          </section>
          {!platform && !admin && secondary.data[0] && (
            <CurrentProgress
              assignment={secondary.data[0]}
              course={primaryRows.find((course) => course.id === secondary.data[0].course_id)}
            />
          )}
          {(platform || admin) && (
            <section className="next-steps">
              <h2>A clear next step</h2>
              <a className="next-step" href={platform ? '#/accounts' : '#/courses'}>
                <span className="record-icon">
                  <Icon name={platform ? 'learners' : 'assignment'} />
                </span>
                <div>
                  <strong>
                    {platform ? 'Review platform access' : 'Connect courses with learners'}
                  </strong>
                  <p>
                    {platform
                      ? 'See the people who oversee your platform.'
                      : 'Assign a course and follow each learner’s progress.'}
                  </p>
                </div>
                <Icon name="arrow" />
              </a>
            </section>
          )}
        </div>
        <aside className="workspace-panel surface">
          <p className="eyebrow">{platform ? 'Your platform' : 'Your institute'}</p>
          <h2>{platform ? 'Platform workspace' : tenant.name}</h2>
          <Badge active={!platform && tenant.status === 'trial_active'}>
            {platform ? roleLabels[user.role] : 'Trial active'}
          </Badge>
          {!platform && (
            <dl>
              <div>
                <dt>Trial ends</dt>
                <dd>{formatDate(tenant.trial_expires_at)}</dd>
              </div>
              <div>
                <dt>Tenant slug</dt>
                <dd className="mono">{tenant.slug}</dd>
              </div>
              <div>
                <dt>Your role</dt>
                <dd>{roleLabels[user.role]}</dd>
              </div>
            </dl>
          )}
          <div className="quick-links">
            {platform ? (
              <>
                {user.role !== 'super_viewer' && (
                  <a className="btn btn-primary" href="#/organizations?create=1">
                    <Icon name="plus" />
                    Create institute
                  </a>
                )}
                <a className="btn btn-secondary" href="#/accounts">
                  Platform accounts
                </a>
              </>
            ) : admin ? (
              <>
                <a className="btn btn-primary" href="#/courses?create=1">
                  <Icon name="plus" />
                  Create course
                </a>
                <a className="btn btn-secondary" href="#/people?create=1">
                  Add person
                </a>
              </>
            ) : (
              <>
                <a className="btn btn-primary" href="#/courses">
                  Browse my courses
                </a>
                <a className="btn btn-secondary" href="#/progress">
                  View my progress
                </a>
              </>
            )}
          </div>
          <p className="workspace-note">
            {platform
              ? 'Institute content is managed within its own tenant workspace.'
              : 'You’re working in this institute. To access another, sign out and use its tenant slug.'}
          </p>
        </aside>
      </div>
    </>
  )
}

function CurrentProgress({ assignment, course }) {
  const progress = useResource(`/tenant/assignments/${assignment.id}/progress`)
  const missingCourse = useResource(course ? null : `/tenant/courses/${assignment.course_id}`)
  return (
    <section className="surface current-progress">
      <p className="eyebrow">One step at a time</p>
      <h2>{course?.title || missingCourse.data?.title || 'Your course progress'}</h2>
      <ResourceBoundary resource={progress}>
        <ProgressBar progress={progress.data} />
      </ResourceBoundary>
      <a className="text-link" href={`#/courses/${assignment.course_id}`}>
        Return to this course
        <Icon name="arrow" />
      </a>
    </section>
  )
}
