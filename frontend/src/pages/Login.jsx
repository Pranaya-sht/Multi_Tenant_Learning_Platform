import { useEffect, useState } from 'react'
import { useAuth } from '../state/context.js'
import { Icon } from '../components/Icon.jsx'
import { Button, ErrorNotice, Field } from '../components/UI.jsx'
import { InstitutePicker } from '../components/InstitutePicker.jsx'

const demos = {
  learner: ['river.learner@example.com', 'river-institute', 'tenant'],
  manager: ['river.admin@example.com', 'river-institute', 'tenant'],
  owner: ['superadmin@example.com', '', 'platform'],
  admin: ['admin@example.com', '', 'platform'],
  viewer: ['viewer@example.com', '', 'platform'],
}

export function Login() {
  useEffect(() => {
    document.title = 'Sign in | SynapseLMS'
  }, [])
  const { login, notice } = useAuth()
  const [scope, setScope] = useState('tenant')
  const [email, setEmail] = useState('')
  const [slug, setSlug] = useState('')
  const [institute, setInstitute] = useState('')
  const [password, setPassword] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [demo, setDemo] = useState('learner')
  async function submit(event) {
    event.preventDefault()
    const instituteSlug = slug || institute.trim().toLowerCase()
    if (scope === 'tenant' && !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(instituteSlug)) {
      setError(new Error('Choose an institute from the suggestions or enter its identifier.'))
      return
    }
    setPending(true)
    setError(null)
    try {
      await login({
        email: email.trim(),
        password,
        tenant_slug: scope === 'tenant' ? instituteSlug : null,
      })
    } catch (failure) {
      setError(failure)
      setPending(false)
    }
  }
  function useDemo() {
    const [account, tenant, mode] = demos[demo]
    setEmail(account)
    setSlug(tenant)
    setInstitute(tenant)
    setScope(mode)
    setPassword('LocalDemo-learning-2026!')
    setError(null)
  }
  return (
    <main className="login-layout">
      <section className="login-story">
        <a className="brand" href="#/overview">
          <span className="brand-mark">
            <Icon name="book" />
          </span>
          <span>
            <strong>SynapseLMS</strong>
            <small>Institute learning</small>
          </span>
        </a>
        <div className="login-story-body">
          <p className="eyebrow">A place to keep growing</p>
          <h1>
            Your institute. <br />
            Every learning <br />
            <span>journey.</span>
          </h1>
          <p>Bring your courses, people, and their next steps into one thoughtful workspace.</p>
          <div className="learning-illustration" aria-hidden="true">
            <div className="illustration-book">
              <Icon name="book" />
            </div>
            <div className="illustration-lines">
              <span />
              <span />
              <span />
            </div>
            <div className="illustration-check">
              <Icon name="check" />
            </div>
          </div>
        </div>
        <p className="login-footnote">Built around your institute. Focused on your progress.</p>
      </section>
      <section className="login-form-area">
        <div className="login-form-wrap">
          <p className="eyebrow">Your learning workspace</p>
          <h2>Welcome back</h2>
          <p className="body-copy">Sign in to pick up where you left off.</p>
          <div className="scope-switch" role="group" aria-label="Account type">
            {['tenant', 'platform'].map((value) => (
              <Button
                key={value}
                kind="quiet"
                aria-pressed={scope === value}
                disabled={pending}
                onClick={() => {
                  setScope(value)
                  setError(null)
                }}
              >
                {value === 'tenant' ? 'Institute account' : 'Platform account'}
              </Button>
            ))}
          </div>
          {notice && (
            <div className="notice" role="status">
              {notice}
            </div>
          )}
          <form onSubmit={submit}>
            <fieldset disabled={pending}>
              {scope === 'tenant' && (
                <InstitutePicker
                  value={institute}
                  selectedSlug={slug}
                  onChange={(value) => {
                    setInstitute(value)
                    setSlug('')
                  }}
                  onSelect={(item) => {
                    setInstitute(item.name)
                    setSlug(item.slug)
                  }}
                />
              )}
              <Field
                label="Email address"
                name="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="username"
                placeholder="you@example.com"
                required
                maxLength={254}
              />
              <Field
                label="Password"
                name="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                autoComplete="current-password"
                required
                maxLength={128}
              />
            </fieldset>
            <ErrorNotice error={error} />
            <Button type="submit" className="full-width" disabled={pending}>
              {pending ? 'Signing in…' : 'Sign in'}
              <Icon name="arrow" />
            </Button>
          </form>
          <p className="login-help">
            {scope === 'tenant'
              ? 'Search for your institute by name, or enter its identifier.'
              : 'For platform administrators and read-only platform viewers.'}
          </p>
          {import.meta.env.DEV && (
            <details className="demo-access">
              <summary>Try the local demo</summary>
              <p>Local development accounts only. Select a role to fill the form.</p>
              <Field
                label="Demo role"
                value={demo}
                onChange={(event) => setDemo(event.target.value)}
              >
                <option value="learner">Tenant User · River Institute</option>
                <option value="manager">Tenant Admin · River Institute</option>
                <option value="owner">Super Admin</option>
                <option value="admin">Platform Admin</option>
                <option value="viewer">Super Viewer</option>
              </Field>
              <Button kind="secondary" onClick={useDemo} disabled={pending}>
                Fill demo credentials
              </Button>
            </details>
          )}
        </div>
      </section>
    </main>
  )
}
