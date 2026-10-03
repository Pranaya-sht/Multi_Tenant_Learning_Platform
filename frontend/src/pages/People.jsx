import { useState } from 'react'
import { useAuth } from '../state/context.js'
import { useResource } from '../hooks/useResource.js'
import { initials, roleLabels } from '../lib/roles.js'
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

export function People({ platform = false, search }) {
  const { user, request, clear } = useAuth()
  const path = platform ? '/platform-users' : '/tenant/users'
  const people = useResource(path, true)
  const canCreate = !platform || user.role === 'super_admin'
  const [query, setQuery] = useState('')
  const [dialog, setDialog] = useState(
    canCreate && search.get('create') ? { type: 'create' } : null,
  )
  const [notice, setNotice] = useState('')
  const rows = (people.data || []).filter((person) =>
    `${person.name} ${person.email}`.toLowerCase().includes(query.toLowerCase()),
  )
  function close() {
    setDialog(null)
    if (search.has('create')) window.location.hash = platform ? '/accounts' : '/people'
  }
  function save(values) {
    if (dialog.type === 'transfer')
      return request(`/tenant/users/${dialog.person.id}/transfer-admin`, { method: 'POST' })
    if (dialog.type === 'password')
      return request(`${path}/${dialog.person.id}/password`, { method: 'PUT', body: values })
    if (dialog.type === 'status')
      return request(`${path}/${dialog.person.id}`, {
        method: 'PATCH',
        body: { is_active: !dialog.person.is_active },
      })
    if (dialog.type === 'create') return request(path, { method: 'POST', body: values })
    return request(`${path}/${dialog.person.id}`, {
      method: 'PATCH',
      body: {
        name: values.name,
        ...(values.role ? { role: values.role } : {}),
        ...(values.is_active ? { is_active: values.is_active === 'true' } : {}),
      },
    })
  }
  return (
    <>
      <PageHeading
        eyebrow={platform ? 'Platform administration' : 'Your institute'}
        title={platform ? 'Platform accounts' : 'People'}
        description={
          platform
            ? 'The people who oversee this learning platform.'
            : 'Help your people take their next step.'
        }
        action={
          canCreate && (
            <Button onClick={() => setDialog({ type: 'create' })}>
              <Icon name="plus" />
              {platform ? 'Create platform account' : 'Add person'}
            </Button>
          )
        }
      />
      {platform && !canCreate && (
        <div className="notice">
          Your role can view platform accounts. Only Super Admin can create them.
        </div>
      )}
      {notice && (
        <div className="notice" role="status">
          {notice}
        </div>
      )}
      <div className="filters">
        <Field
          label="Search people"
          type="search"
          placeholder="Search by name or email"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
      </div>
      <section className="surface">
        <ResourceBoundary resource={people}>
          <Records
            key={query}
            rows={rows}
            empty={
              <Empty icon="learners" title="No people found">
                Add people to your institute or try a different search.
              </Empty>
            }
            render={(person) => (
              <li className="record-row" key={person.id}>
                <span className="avatar">{initials(person.name)}</span>
                <div className="record-content">
                  <strong>
                    {person.name}
                    {person.id === user.id && <span className="you-label">You</span>}
                  </strong>
                  <p>{person.email}</p>
                  <div className="badges">
                    <Badge>{roleLabels[person.role]}</Badge>
                    <Badge active={person.is_active}>
                      {person.is_active ? 'Active' : 'Inactive'}
                    </Badge>
                  </div>
                </div>
                {!platform && (
                  <div className="actions">
                    <Button kind="secondary" onClick={() => setDialog({ type: 'edit', person })}>
                      Edit person
                    </Button>
                    <Button kind="quiet" onClick={() => setDialog({ type: 'password', person })}>
                      Reset password
                    </Button>
                    {person.id !== user.id && (
                      <Button kind="quiet" onClick={() => setDialog({ type: 'status', person })}>
                        {person.is_active ? 'Deactivate' : 'Reactivate'}
                      </Button>
                    )}
                    {person.role === 'tenant_user' && person.is_active && (
                      <Button kind="quiet" onClick={() => setDialog({ type: 'transfer', person })}>
                        Transfer admin role
                      </Button>
                    )}
                  </div>
                )}
              </li>
            )}
          />
        </ResourceBoundary>
      </section>
      {dialog && (
        <ActionDialog
          title={
            dialog.type === 'create'
              ? platform
                ? 'Create platform account'
                : 'Add person'
              : dialog.type === 'password'
                ? 'Reset password'
                : dialog.type === 'status'
                  ? `${dialog.person.is_active ? 'Deactivate' : 'Reactivate'} ${dialog.person.name}`
                  : dialog.type === 'transfer'
                    ? `Make ${dialog.person.name} Tenant Admin`
                    : 'Edit person'
          }
          onClose={close}
          action={save}
          submitLabel={
            dialog.type === 'create'
              ? 'Create account'
              : dialog.type === 'password'
                ? 'Reset password'
                : dialog.type === 'status'
                  ? dialog.person.is_active
                    ? 'Deactivate account'
                    : 'Reactivate account'
                  : dialog.type === 'transfer'
                    ? 'Transfer admin role'
                    : 'Save changes'
          }
          explanation={
            dialog.type === 'password'
              ? `Set a new password for ${dialog.person.name}. This ends their existing sessions.`
              : dialog.type === 'status'
                ? dialog.person.is_active
                  ? 'This account will lose access immediately. Its assignments and progress are preserved.'
                  : 'This account can sign in again. Its assignments and progress are preserved.'
                : dialog.type === 'transfer'
                  ? `${dialog.person.name} becomes the only Tenant Admin. Your account becomes a learner and both existing sessions end. Assignments and progress are preserved.`
                  : dialog.type === 'edit'
                    ? 'Each institute has one Tenant Admin. Transfer that role to another active learner when needed. Changing account status ends existing sessions.'
                    : undefined
          }
          onSaved={() => {
            if (dialog.type === 'transfer') {
              clear('Administrator role transferred. Sign in again to continue.')
              return
            }
            close()
            people.refresh()
            setNotice('Account saved.')
          }}
        >
          {['create', 'edit'].includes(dialog.type) && (
            <Field
              label="Full name"
              name="name"
              required
              maxLength={150}
              defaultValue={dialog.person?.name || ''}
            />
          )}
          {dialog.type === 'create' && (
            <Field
              label="Email address"
              name="email"
              type="email"
              autoComplete="off"
              required
              maxLength={254}
              hint={
                platform
                  ? 'Unique among platform accounts.'
                  : 'Unique within this institute. The same email may belong to a different institute.'
              }
            />
          )}
          {['create', 'edit'].includes(dialog.type) &&
            (platform || dialog.person?.role !== 'tenant_admin') && (
              <Field
                label="Role"
                name="role"
                defaultValue={dialog.person?.role || (platform ? 'super_viewer' : 'tenant_user')}
              >
                {(platform ? ['super_viewer', 'admin', 'super_admin'] : ['tenant_user']).map(
                  (role) => (
                    <option key={role} value={role}>
                      {roleLabels[role]}
                    </option>
                  ),
                )}
              </Field>
            )}
          {dialog.type === 'edit' && dialog.person?.role !== 'tenant_admin' && (
            <Field
              label="Account status"
              name="is_active"
              defaultValue={String(dialog.person.is_active)}
            >
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </Field>
          )}
          {['create', 'password'].includes(dialog.type) && (
            <Field
              label={dialog.type === 'password' ? 'New password' : 'Initial password'}
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
              hint="12–128 characters."
            />
          )}
        </ActionDialog>
      )}
    </>
  )
}
