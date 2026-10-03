import { useEffect, useState } from 'react'
import { AuthProvider } from './state/Auth.jsx'
import { useAuth } from './state/context.js'
import { useResource } from './hooks/useResource.js'
import { initials, isPlatform, navigationFor, roleLabels } from './lib/roles.js'
import { Icon } from './components/Icon.jsx'
import { Badge, Button, Empty, ErrorNotice, Loading } from './components/UI.jsx'
import { Login } from './pages/Login.jsx'
import { Overview } from './pages/Overview.jsx'
import { Courses } from './pages/Courses.jsx'
import { CourseDetail } from './pages/CourseDetail.jsx'
import { People } from './pages/People.jsx'
import { Institutes } from './pages/Institutes.jsx'
import { Assignments } from './pages/Assignments.jsx'

function useRoute() {
  const [hash, setHash] = useState(window.location.hash || '#/overview')
  useEffect(() => {
    const changed = () => setHash(window.location.hash || '#/overview')
    window.addEventListener('hashchange', changed)
    return () => window.removeEventListener('hashchange', changed)
  }, [])
  const [path, query] = hash.replace(/^#\/?/, '').split('?')
  const parts = path.split('/').filter(Boolean)
  return {
    page: parts[0] || 'overview',
    id: parts[1],
    parts,
    search: new URLSearchParams(query),
    raw: hash,
  }
}

function Workspace() {
  const { user, logout, expired } = useAuth()
  const platform = isPlatform(user)
  const tenant = useResource(platform ? null : '/tenant')
  const route = useRoute()
  const navigation = navigationFor(user)
  const [signingOut, setSigningOut] = useState(false)
  const [menuPath, setMenuPath] = useState(null)
  const menu = menuPath === route.raw
  useEffect(() => {
    document.getElementById('workspace-main')?.focus()
  }, [route.raw])
  const label = navigation.find(([path]) => path === route.page)?.[1] || 'Workspace'
  useEffect(() => {
    document.title = `${label} | SynapseLMS`
  }, [label])
  const blocked = !platform && (expired || tenant.data?.status === 'expired')
  async function signOut() {
    setSigningOut(true)
    await logout()
  }
  let content
  if (!platform && tenant.loading) content = <Loading />
  else if (tenant.error) content = <ErrorNotice error={tenant.error} retry={tenant.refresh} />
  else if (blocked)
    content = (
      <section className="surface expired-panel">
        <Badge>Trial expired</Badge>
        <h1>A pause in your learning journey.</h1>
        <p>
          Your institute’s trial has ended. Your courses and progress are preserved. Contact a
          platform administrator to reactivate access.
        </p>
        <dl>
          <div>
            <dt>Institute</dt>
            <dd>{tenant.data?.name}</dd>
          </div>
          <div>
            <dt>Tenant slug</dt>
            <dd className="mono">{tenant.data?.slug}</dd>
          </div>
        </dl>
        <Button kind="secondary" onClick={tenant.refresh}>
          Check access again
        </Button>
      </section>
    )
  else if (
    !navigation.some(([path]) => path === route.page) ||
    (route.parts.length > 1 && route.page !== 'courses') ||
    route.parts.length > 2
  )
    content = (
      <Empty title="This page isn’t available">
        Choose a page from your workspace navigation.
        <a className="btn btn-secondary" href="#/overview">
          Back to overview
        </a>
      </Empty>
    )
  else if (route.page === 'overview') content = <Overview tenant={tenant.data} />
  else if (route.page === 'courses')
    content = route.id ? <CourseDetail id={route.id} /> : <Courses search={route.search} />
  else if (route.page === 'people' || route.page === 'accounts')
    content = <People platform={platform} search={route.search} />
  else if (route.page === 'organizations') content = <Institutes search={route.search} />
  else content = <Assignments search={route.search} />
  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#workspace-main"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('workspace-main')?.focus()
        }}
      >
        Skip to main content
      </a>
      <aside className="sidebar">
        <div className="sidebar-top">
          <a className="brand" href="#/overview">
            <span className="brand-mark">
              <Icon name="book" />
            </span>
            <span>
              <strong>SynapseLMS</strong>
              <small>Institute learning</small>
            </span>
          </a>
          <Button
            kind="quiet"
            className="mobile-menu-button"
            aria-label="Toggle workspace menu"
            aria-expanded={menu}
            aria-controls="workspace-navigation"
            onClick={() => setMenuPath(menu ? null : route.raw)}
          >
            <Icon name="menu" />
          </Button>
        </div>
        <div className={`sidebar-content ${menu ? 'menu-open' : ''}`} id="workspace-navigation">
          <nav className="workspace-nav" aria-label="Workspace navigation">
            {navigation.map(([path, title, icon]) => (
              <a
                key={path}
                href={`#/${path}`}
                className={`nav-item ${route.page === path ? 'nav-active' : ''}`}
                aria-current={route.page === path ? 'page' : undefined}
              >
                <Icon name={icon} />
                <span>{title}</span>
              </a>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="tenant-context">
              <span className="status-dot" />
              <div>
                <strong>
                  {platform ? 'Platform workspace' : tenant.data?.name || 'Your institute'}
                </strong>
                <small>
                  {platform ? 'Institute administration' : tenant.data?.slug || 'Loading institute'}
                </small>
              </div>
            </div>
            <Button kind="quiet" className="sign-out" disabled={signingOut} onClick={signOut}>
              <Icon name="logout" />
              {signingOut ? 'Signing out…' : 'Sign out'}
            </Button>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="workspace-header">
          <div className="breadcrumb">
            <span>{platform ? 'Platform' : tenant.data?.name || 'Institute'}</span>
            <span aria-hidden="true">/</span>
            <strong>{label}</strong>
          </div>
          <div className="identity">
            <span className="avatar">{initials(user.name)}</span>
            <div>
              <strong>{user.name}</strong>
              <small>{roleLabels[user.role]}</small>
            </div>
          </div>
        </header>
        <main id="workspace-main" tabIndex={-1} className="workspace-main" key={route.raw}>
          {content}
        </main>
        <footer className="workspace-footer">
          <span>SynapseLMS · Learning, together.</span>
          <span>{platform ? roleLabels[user.role] : tenant.data?.name}</span>
        </footer>
      </div>
    </div>
  )
}

function SessionGate() {
  const auth = useAuth()
  if (auth.restoring)
    return (
      <main className="session-loading">
        <Loading label="Restoring your session" />
      </main>
    )
  if (auth.restoreError)
    return (
      <main className="session-loading">
        <ErrorNotice error={auth.restoreError} retry={auth.retryRestore} />
        <Button kind="secondary" onClick={() => auth.clear()}>
          Return to sign in
        </Button>
      </main>
    )
  return auth.user ? <Workspace key={auth.user.id} /> : <Login />
}

export default function App() {
  return (
    <AuthProvider>
      <SessionGate />
    </AuthProvider>
  )
}
