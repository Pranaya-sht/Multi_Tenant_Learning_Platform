import { useState } from 'react'
import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { canManageTenants, formatDate } from '../lib/roles.js'
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

export function Institutes({ search }) {
  const { user, request } = useAuth()
  const institutes = useResource('/tenants', true)
  const canEdit = canManageTenants(user)
  const lifecycle = user.role === 'super_admin'
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('all')
  const [dialog, setDialog] = useState(canEdit && search.get('create') ? { type: 'create' } : null)
  const [notice, setNotice] = useState('')
  const rows = (institutes.data || []).filter(
    (tenant) =>
      `${tenant.name} ${tenant.slug}`.toLowerCase().includes(query.toLowerCase()) &&
      (status === 'all' || tenant.status === status),
  )
  function close() {
    setDialog(null)
    if (search.has('create')) window.location.hash = '/organizations'
  }
  function save(values) {
    if (dialog.type === 'create')
      return request('/tenants', {
        method: 'POST',
        body: {
          name: values.name,
          slug: values.slug,
          admin: {
            name: values.admin_name,
            email: values.admin_email,
            password: values.admin_password,
          },
        },
      })
    const path = `/tenants/${dialog.tenant.id}`
    if (dialog.type === 'edit')
      return request(path, { method: 'PATCH', body: { name: values.name } })
    return request(`${path}/${dialog.type}`, {
      method: 'POST',
      ...(dialog.type === 'reactivate' ? { body: { days: Number(values.days) } } : {}),
    })
  }
  return (
    <>
      <PageHeading
        eyebrow="Platform administration"
        title="Institutes"
        description="Each institute, with its own people and learning workspace."
        action={
          canEdit && (
            <Button onClick={() => setDialog({ type: 'create' })}>
              <Icon name="plus" />
              Create institute
            </Button>
          )
        }
      />
      {user.role === 'super_viewer' && (
        <div className="notice">Read-only access. You can review institute details.</div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="filters">
        <Field
          label="Search institutes"
          type="search"
          placeholder="Name or tenant slug"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <Field
          label="Trial status"
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        >
          <option value="all">All statuses</option>
          <option value="trial_active">Trial active</option>
          <option value="expired">Expired</option>
          <option value="created">Created</option>
        </Field>
      </div>
      <section className="surface">
        <ResourceBoundary resource={institutes}>
          <Records
            key={`${query}:${status}`}
            rows={rows}
            empty={
              <Empty icon="organization" title="No institutes found">
                Create an institute or try a different search.
              </Empty>
            }
            render={(tenant) => (
              <li className="institute-record" key={tenant.id}>
                <div className="record-row">
                  <span className="record-icon">
                    <Icon name="organization" />
                  </span>
                  <div className="record-content">
                    <strong>{tenant.name}</strong>
                    <p className="mono">{tenant.slug}</p>
                    <Badge active={tenant.status === 'trial_active'}>
                      {tenant.status === 'trial_active'
                        ? 'Trial active'
                        : tenant.status === 'expired'
                          ? 'Expired'
                          : 'Created'}
                    </Badge>
                  </div>
                  <div className="actions">
                    {canEdit && (
                      <Button kind="secondary" onClick={() => setDialog({ type: 'edit', tenant })}>
                        Rename
                      </Button>
                    )}
                    {lifecycle && (
                      <Button
                        kind="quiet"
                        onClick={() => setDialog({ type: 'reactivate', tenant })}
                      >
                        {tenant.status === 'expired' ? 'Reactivate' : 'Set access window'}
                      </Button>
                    )}
                    {lifecycle && tenant.status !== 'expired' && (
                      <Button kind="quiet" onClick={() => setDialog({ type: 'expire', tenant })}>
                        Expire trial
                      </Button>
                    )}
                  </div>
                </div>
                <details className="record-details">
                  <summary>View institute details</summary>
                  <dl>
                    <div>
                      <dt>Created</dt>
                      <dd>{formatDate(tenant.created_at)}</dd>
                    </div>
                    <div>
                      <dt>Trial ends</dt>
                      <dd>
                        <time dateTime={tenant.trial_expires_at}>
                          {new Date(tenant.trial_expires_at).toLocaleString()}
                        </time>
                      </dd>
                    </div>
                    <div>
                      <dt>Institute ID</dt>
                      <dd className="mono">{tenant.id}</dd>
                    </div>
                  </dl>
                  <p>Dates are shown in your local timezone.</p>
                </details>
              </li>
            )}
          />
        </ResourceBoundary>
      </section>
      {dialog && (
        <ActionDialog
          title={
            dialog.type === 'create'
              ? 'Create institute'
              : dialog.type === 'edit'
                ? 'Rename institute'
                : dialog.type === 'expire'
                  ? 'Expire trial'
                  : 'Reactivate institute'
          }
          onClose={close}
          action={save}
          onSaved={() => {
            close()
            institutes.refresh()
            setNotice('Institute updated.')
          }}
          submitLabel={
            dialog.type === 'create'
              ? 'Create institute'
              : dialog.type === 'expire'
                ? 'Expire trial'
                : dialog.type === 'reactivate'
                  ? 'Start access window'
                  : 'Save changes'
          }
          explanation={
            dialog.type === 'expire'
              ? `Learning access for ${dialog.tenant.name} will stop immediately. Accounts, courses, assignments, and progress are preserved.`
              : dialog.type === 'reactivate'
                ? 'Start a new access window from now. Existing courses and progress are preserved.'
                : dialog.type === 'create'
                  ? 'A new institute starts with a free trial and its own tenant administrator.'
                  : undefined
          }
        >
          {['create', 'edit'].includes(dialog.type) && (
            <Field
              label="Institute name"
              name="name"
              required
              maxLength={150}
              defaultValue={dialog.tenant?.name || ''}
            />
          )}
          {dialog.type === 'create' && (
            <>
              <Field
                label="Tenant slug"
                name="slug"
                required
                minLength={2}
                maxLength={80}
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                placeholder="e.g. river-institute"
                hint="Lowercase letters, numbers, and single hyphens. Used for tenant login."
              />
              <Field label="Administrator name" name="admin_name" required maxLength={150} />
              <Field
                label="Administrator email"
                name="admin_email"
                type="email"
                required
                maxLength={254}
              />
              <Field
                label="Administrator password"
                name="admin_password"
                type="password"
                autoComplete="new-password"
                required
                minLength={12}
                maxLength={128}
                hint="12–128 characters."
              />
            </>
          )}
          {dialog.type === 'reactivate' && (
            <Field
              label="Access window in days"
              name="days"
              type="number"
              required
              min={1}
              max={365}
              defaultValue={14}
            />
          )}
        </ActionDialog>
      )}
    </>
  )
}
