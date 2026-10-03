import { expect, test } from '@playwright/test'
import fs from 'node:fs/promises'

const PASSWORD = 'LocalDemo-learning-2026!'
async function signIn(page, email, slug = '', password = PASSWORD) {
  await page.goto('/')
  if (!slug) await page.getByRole('button', { name: 'Platform account', exact: true }).click()
  else await page.getByLabel('Institute', { exact: true }).fill(slug)
  await page.getByLabel('Email address', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.locator('.workspace-header')).toBeVisible()
  await expect(
    page.getByRole('status', { name: 'Loading your workspace', exact: true }),
  ).toHaveCount(0)
}
async function navigate(page, label) {
  const toggle = page.getByRole('button', { name: 'Toggle workspace menu' })
  if ((await toggle.isVisible()) && (await toggle.getAttribute('aria-expanded')) === 'false')
    await toggle.click()
  await page
    .getByRole('navigation', { name: 'Workspace navigation' })
    .getByRole('link', { name: label, exact: true })
    .click()
}
function record(page, text) {
  return page
    .locator('li')
    .filter({ has: page.getByText(text, { exact: true }) })
    .first()
}
test.beforeEach(async ({ page }) => {
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  page.applicationErrors = errors
})
test.afterEach(async ({ page }) => {
  expect(page.applicationErrors).toEqual([])
})

test('institute name suggestions select the login scope', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 850 })
  await page.goto('/')
  await page.getByLabel('Institute', { exact: true }).fill('River')
  await expect(page.getByRole('listbox')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.getByRole('option', { name: /River Institute.*river-institute/ }).click()
  await expect(page.getByLabel('Institute', { exact: true })).toHaveValue('River Institute')
  await page.getByLabel('Email address', { exact: true }).fill('river.admin@example.com')
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.locator('.identity')).toContainText('Tenant Admin')
})

for (const [email, slug, role, links, missing] of [
  [
    'superadmin@example.com',
    '',
    'Super Admin',
    ['Overview', 'Institutes', 'Platform accounts'],
    ['Courses', 'People'],
  ],
  [
    'admin@example.com',
    '',
    'Platform Admin',
    ['Institutes', 'Platform accounts'],
    ['Courses', 'People'],
  ],
  [
    'viewer@example.com',
    '',
    'Super Viewer',
    ['Institutes', 'Platform accounts'],
    ['Courses', 'People'],
  ],
  [
    'river.admin@example.com',
    'river-institute',
    'Tenant Admin',
    ['Courses', 'People', 'Progress'],
    ['Institutes', 'Platform accounts'],
  ],
  [
    'river.learner@example.com',
    'river-institute',
    'Learner',
    ['My courses', 'My progress'],
    ['People', 'Institutes', 'Progress'],
  ],
]) {
  test(`${role} sees the correct workspace and navigation`, async ({ page }) => {
    await signIn(page, email, slug)
    await expect(page.locator('.identity')).toContainText(role)
    const nav = page.getByRole('navigation', { name: 'Workspace navigation' })
    for (const label of links)
      await expect(nav.getByRole('link', { name: label, exact: true })).toBeVisible()
    for (const label of missing)
      await expect(nav.getByRole('link', { name: label, exact: true })).toHaveCount(0)
    if (role === 'Super Viewer' || role === 'Platform Admin') {
      await navigate(page, 'Institutes')
      await expect(page.getByRole('button', { name: 'Expire trial', exact: true })).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Create institute', exact: true })).toHaveCount(
        role === 'Super Viewer' ? 0 : 1,
      )
    }
    await page.reload()
    await expect(page.locator('.identity')).toContainText(role)
    await page.getByRole('button', { name: 'Sign out', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
    expect(await page.evaluate(() => sessionStorage.getItem('synapse.access-token'))).toBeNull()
  })
}

for (const width of [375, 768, 1440]) {
  test(`responsive layout and keyboard dialogs at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto('/')
    await fs.mkdir('test-results/screenshots', { recursive: true })
    await page.screenshot({ path: `test-results/screenshots/login-${width}.png`, fullPage: true })
    await signIn(page, 'river.admin@example.com', 'river-institute')
    await page.screenshot({
      path: `test-results/screenshots/overview-${width}.png`,
      fullPage: true,
    })
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await navigate(page, 'Courses')
    const create = page.getByRole('button', { name: 'Create course', exact: true })
    await create.click()
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByLabel('Course title')).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(create).toBeFocused()
    await page.emulateMedia({ reducedMotion: 'reduce' })
    expect(
      await page.evaluate(
        () => getComputedStyle(document.querySelector('.btn')).transitionDuration,
      ),
    ).toBe('0s')
  })
}

test('lesson questions count toward progress and course access can be revoked', async ({
  page,
  browser,
}) => {
  await signIn(page, 'river.admin@example.com', 'river-institute')
  await navigate(page, 'Courses')
  await page.getByRole('button', { name: 'Create course', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Course title').fill('Browser course')
  await dialog.getByLabel('Description').fill('A course created through the real frontend.')
  await dialog.getByRole('button', { name: 'Create course', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Browser course', exact: true })).toBeVisible()
  for (const [title, content] of [
    ['First lesson', 'Read this lesson.\n<img src=x onerror=alert(1)>'],
    ['Second lesson', 'Keep learning.'],
  ]) {
    await page.getByRole('button', { name: 'Add lesson', exact: true }).click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Lesson title').fill(title)
    await dialog.getByLabel('Lesson content').fill(content)
    await dialog.getByRole('button', { name: 'Add lesson', exact: true }).click()
    await expect(page.getByRole('heading', { name: title, exact: true })).toBeVisible()
  }
  const firstLesson = page.locator('.lesson-editor-list > li').filter({ hasText: 'First lesson' })
  await firstLesson.getByRole('button', { name: 'Add question' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Question', { exact: true }).fill('Which answer means yes?')
  await dialog.getByLabel('Answer options').fill('No\nYes')
  await dialog.getByLabel('Correct option number').fill('2')
  await dialog.getByRole('button', { name: 'Add question' }).click()
  await expect(firstLesson).toContainText('Which answer means yes?')
  await firstLesson.getByRole('button', { name: 'Add question' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Question type').selectOption('text')
  await dialog.getByLabel('Question', { exact: true }).fill('What did you learn?')
  await dialog.getByRole('button', { name: 'Add question' }).click()
  await expect(firstLesson).toContainText('What did you learn?')
  await page.setViewportSize({ width: 375, height: 850 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await page.setViewportSize({ width: 1440, height: 1000 })
  await navigate(page, 'People')
  await page.getByRole('button', { name: 'Add person', exact: true }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Full name').fill('Browser learner')
  await dialog.getByLabel('Email address').fill('browser@example.com')
  await dialog.getByLabel('Initial password').fill(PASSWORD)
  await dialog.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('Browser learner', { exact: true })).toBeVisible()
  await record(page, 'Browser learner').getByRole('button', { name: 'Deactivate' }).click()
  dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('assignments and progress are preserved')
  await dialog.getByRole('button', { name: 'Deactivate account' }).click()
  await expect(record(page, 'Browser learner')).toContainText('Inactive')
  await record(page, 'Browser learner').getByRole('button', { name: 'Reactivate' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Reactivate account' }).click()
  await expect(record(page, 'Browser learner')).toContainText('Active')
  await navigate(page, 'Courses')
  await page.getByRole('link', { name: 'Browser course', exact: true }).click()
  await page.setViewportSize({ width: 375, height: 850 })
  await page.getByRole('button', { name: 'Enroll learners', exact: true }).click()
  dialog = page.getByRole('dialog')
  const learnerSearch = dialog.getByRole('combobox', { name: 'Learners' })
  await learnerSearch.fill('browser@')
  await dialog.getByRole('option', { name: /Browser learner.*browser@example.com/ }).click()
  await learnerSearch.fill('river.learner@')
  await dialog
    .getByRole('option', { name: /River Institute Learner.*river.learner@example.com/ })
    .click()
  await expect(dialog.getByRole('button', { name: 'Remove Browser learner' })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Remove River Institute Learner' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(
    true,
  )
  await dialog.getByRole('button', { name: 'Enroll learners', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 1000 })
  await expect(page.locator('.course-enrollment')).toContainText('Browser learner')
  await expect(page.locator('.course-enrollment')).toContainText('River Institute Learner')

  const context = await browser.newContext()
  const learner = await context.newPage()
  try {
    await signIn(learner, 'browser@example.com', 'river-institute')
    await learner.setViewportSize({ width: 375, height: 850 })
    await navigate(learner, 'My courses')
    await learner.getByRole('link', { name: 'Browser course', exact: true }).click()
    expect(
      await learner.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBe(true)
    await expect(learner.getByRole('heading', { name: 'First lesson', exact: true })).toBeVisible()
    await expect(learner.locator('.lesson-body')).toContainText('<img src=x onerror=alert(1)>')
    await expect(learner.locator('.lesson-body img')).toHaveCount(0)
    await learner.getByRole('radio', { name: 'No', exact: true }).check()
    await learner
      .getByLabel('2. What did you learn?')
      .fill('I learned to explain the answer. <img src=x onerror=alert(1)>')
    await learner.getByRole('button', { name: 'Submit answers' }).click()
    await expect(learner.getByText('Try another answer.')).toBeVisible()
    await expect(learner.getByRole('progressbar')).toHaveAttribute('value', '0')
    await learner.getByRole('radio', { name: 'Yes', exact: true }).check()
    await learner.getByRole('button', { name: 'Submit answers' }).click()
    await expect(learner.getByRole('progressbar')).toHaveAttribute('value', '50')
    await learner.getByRole('button', { name: 'Next lesson', exact: true }).click()
    await learner.getByRole('button', { name: 'Complete lesson', exact: true }).click()
    await expect(learner.getByRole('progressbar')).toHaveAttribute('value', '100')
    await learner.reload()
    await expect(learner.getByRole('progressbar')).toHaveAttribute('value', '100')
    await page.reload()
    await page
      .locator('.lesson-editor-list > li')
      .filter({ hasText: 'First lesson' })
      .getByRole('button', { name: 'View answers' })
      .click()
    await expect(page.locator('.lesson-submissions')).toContainText(
      'I learned to explain the answer.',
    )
    await expect(page.locator('.lesson-submissions img')).toHaveCount(0)
    await expect(page.locator('.course-enrollment')).toContainText('100%')
    await page
      .locator('.course-enrollment .record-list > li')
      .filter({ hasText: 'Browser learner' })
      .getByRole('button', { name: 'Revoke access' })
      .click()
    dialog = page.getByRole('dialog')
    await expect(dialog).toContainText('permanently removed')
    await dialog.getByRole('button', { name: 'Revoke access', exact: true }).click()
    await expect(page.locator('.course-enrollment')).not.toContainText('Browser learner')
    await expect(page.locator('.course-enrollment')).toContainText('River Institute Learner')
    await navigate(learner, 'My courses')
    await expect(
      learner.getByRole('heading', { name: 'Your next course is on its way' }),
    ).toBeVisible()
  } finally {
    await context.close()
  }
  await page.getByRole('button', { name: 'Revoke access' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Revoke access' }).click()
  await expect(page.getByRole('heading', { name: 'No learners enrolled' })).toBeVisible()
  await navigate(page, 'Courses')
  await record(page, 'Browser course').getByRole('button', { name: 'Archive', exact: true }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Archive course', exact: true })
    .click()
  await expect(record(page, 'Browser course')).toContainText('Archived')
  await record(page, 'Browser course').getByRole('button', { name: 'Restore', exact: true }).click()
  await page
    .getByRole('dialog')
    .getByRole('button', { name: 'Restore course', exact: true })
    .click()
  await expect(record(page, 'Browser course')).toContainText('Available')
})

test('an institute has one administrator and can transfer that role', async ({ page }) => {
  const adminRow = () =>
    page.locator('.record-list > li').filter({ hasText: 'River Institute Admin' })
  const learnerRow = () =>
    page.locator('.record-list > li').filter({ hasText: 'River Institute Learner' })
  await signIn(page, 'river.admin@example.com', 'river-institute')
  await navigate(page, 'People')
  await adminRow().getByRole('button', { name: 'Edit person' }).click()
  let dialog = page.getByRole('dialog')
  await expect(dialog.getByLabel('Account status')).toHaveCount(0)
  await expect(dialog.getByLabel('Role')).toHaveCount(0)
  await dialog.getByRole('button', { name: 'Save changes' }).click()
  await expect(adminRow()).toContainText('Active')
  await learnerRow().getByRole('button', { name: 'Transfer admin role' }).click()
  dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('only Tenant Admin')
  await dialog.getByRole('button', { name: 'Transfer admin role' }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()

  await signIn(page, 'river.learner@example.com', 'river-institute')
  await navigate(page, 'People')
  await expect(learnerRow()).toContainText('Tenant Admin')
  await adminRow().getByRole('button', { name: 'Transfer admin role' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Transfer admin role' }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await signIn(page, 'river.admin@example.com', 'river-institute')
  await navigate(page, 'People')
  await expect(adminRow()).toContainText('Tenant Admin')
})

test('platform creates an institute, expires it, and restores tenant access', async ({
  page,
  browser,
}) => {
  await signIn(page, 'superadmin@example.com')
  await navigate(page, 'Institutes')
  await page.getByRole('button', { name: 'Create institute', exact: true }).click()
  let dialog = page.getByRole('dialog')
  await dialog.getByLabel('Institute name').fill('Browser Institute')
  await dialog.getByLabel('Tenant slug', { exact: true }).fill('browser-institute')
  await dialog.getByLabel('Administrator name').fill('Browser administrator')
  await dialog.getByLabel('Administrator email').fill('browser.admin@example.com')
  await dialog.getByLabel('Administrator password').fill(PASSWORD)
  await dialog.getByRole('button', { name: 'Create institute', exact: true }).click()
  await expect(record(page, 'Browser Institute')).toContainText('Trial active')
  const context = await browser.newContext()
  const tenant = await context.newPage()
  try {
    await signIn(tenant, 'browser.admin@example.com', 'browser-institute')
    await expect(tenant.getByRole('heading', { name: 'Your curriculum starts here' })).toBeVisible()
    await record(page, 'Browser Institute')
      .getByRole('button', { name: 'Expire trial', exact: true })
      .click()
    await page
      .getByRole('dialog')
      .getByRole('button', { name: 'Expire trial', exact: true })
      .click()
    await expect(record(page, 'Browser Institute')).toContainText('Expired')
    await navigate(tenant, 'Courses')
    await expect(
      tenant.getByRole('heading', { name: 'A pause in your learning journey.' }),
    ).toBeVisible()
    await record(page, 'Browser Institute')
      .getByRole('button', { name: 'Reactivate', exact: true })
      .click()
    dialog = page.getByRole('dialog')
    await dialog.getByLabel('Access window in days').fill('21')
    await dialog.getByRole('button', { name: 'Start access window' }).click()
    await expect(record(page, 'Browser Institute')).toContainText('Trial active')
    await tenant.getByRole('button', { name: 'Check access again' }).click()
    await expect(tenant.getByRole('button', { name: 'Create course', exact: true })).toBeVisible()
  } finally {
    await context.close()
  }
  await navigate(page, 'Platform accounts')
  await page.getByRole('button', { name: 'Create platform account' }).click()
  dialog = page.getByRole('dialog')
  await dialog.getByLabel('Full name').fill('Browser platform viewer')
  await dialog.getByLabel('Email address').fill('browser.viewer@example.com')
  await dialog.getByLabel('Initial password').fill(PASSWORD)
  await dialog.getByRole('button', { name: 'Create account' }).click()
  await expect(page.getByText('Browser platform viewer', { exact: true })).toBeVisible()
})

test('failed requests can be retried and revoked sessions return to login', async ({ page }) => {
  await signIn(page, 'river.learner@example.com', 'river-institute')
  let failing = true
  await page.route('**/api/v1/tenant/courses/page?*', (route) =>
    failing
      ? route.fulfill({
          status: 503,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Database temporarily unavailable' }),
        })
      : route.continue(),
  )
  await navigate(page, 'My courses')
  await expect(page.getByRole('alert')).toContainText('Database temporarily unavailable')
  failing = false
  await page.getByRole('button', { name: 'Try again' }).click()
  await expect(
    page.getByRole('link', { name: 'Introduction to Python', exact: true }),
  ).toBeVisible()
  await page.route('**/api/v1/auth/me', (route) =>
    route.fulfill({
      status: 401,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Credentials revoked' }),
    }),
  )
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  await expect(page.getByRole('status')).toContainText('Your session ended')
  expect(await page.evaluate(() => sessionStorage.getItem('synapse.access-token'))).toBeNull()
})

test('course search and server pages reach records beyond the first ten', async ({ page }) => {
  await signIn(page, 'river.admin@example.com', 'river-institute')
  const token = await page.evaluate(() => sessionStorage.getItem('synapse.access-token'))
  for (let index = 1; index <= 12; index++) {
    const response = await page.request.post('/api/v1/tenant/courses', {
      headers: { Authorization: `Bearer ${token}` },
      data: { title: `Paged course ${String(index).padStart(2, '0')}` },
    })
    expect(response.status()).toBe(201)
  }
  await navigate(page, 'Courses')
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Next', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Paged course 12', exact: true })).toBeVisible()
  await page.getByLabel('Search courses').fill('Paged course 12')
  await expect(page.getByRole('link', { name: 'Paged course 12', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Next', exact: true })).toHaveCount(0)
})
