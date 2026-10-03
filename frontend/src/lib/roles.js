export const roleLabels = {
  super_admin: 'Super Admin',
  admin: 'Platform Admin',
  super_viewer: 'Super Viewer',
  tenant_admin: 'Tenant Admin',
  tenant_user: 'Learner',
}

export const isPlatform = (user) => user && !user.tenant_id
export const canManageTenants = (user) => ['super_admin', 'admin'].includes(user.role)

export function navigationFor(user) {
  if (isPlatform(user)) {
    return [
      ['overview', 'Overview', 'overview'],
      ['organizations', 'Institutes', 'organization'],
      ['accounts', 'Platform accounts', 'learners'],
    ]
  }
  return user.role === 'tenant_admin'
    ? [
        ['overview', 'Overview', 'overview'],
        ['courses', 'Courses', 'book'],
        ['people', 'People', 'learners'],
        ['assignments', 'Progress', 'assignment'],
      ]
    : [
        ['overview', 'Overview', 'overview'],
        ['courses', 'My courses', 'book'],
        ['progress', 'My progress', 'assignment'],
      ]
}

export function initials(name = '') {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

export function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
}
