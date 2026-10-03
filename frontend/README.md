# Learning Platform Frontend

React JavaScript, Vite, and Tailwind CSS, connected to the FastAPI backend.

## Run Locally

Start the backend and its database services using [backend/README.md](../backend/README.md).
Then from `frontend/`:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:5173. Vite proxies `/api` to http://127.0.0.1:8000. On macOS/Linux use `npm`.

Institute sign-in requires email, password, and an institute. Type a name to see suggestions and
select one; a known slug can also be entered directly. The API still receives `tenant_slug`.
Platform sign-in uses email/password.
The development-only **Try the local demo** panel fills the documented credentials for each role.
River demo accounts use `river-institute`; see the backend guide for all credentials.

## Supported Workflows

- Super Admin: create/rename institutes, expire/reactivate trials, and create platform accounts.
- Platform Admin: create/rename institutes and view platform accounts.
- Super Viewer: read-only institute and platform-account views.
- Tenant Admin: create/edit/archive courses, add/edit lessons and their questions, search and
  select multiple learners for one enrollment action, revoke individual enrollments, read
  submitted answers, and view progress. They can manage learners and passwords and transfer the
  sole institute-admin role to an active learner. The transfer signs out the previous admin.
- Learner: read enrolled lessons, answer multiple-choice and text questions in the lesson, and
  record completion. Answers and progress survive reloads.

Trial expiration blocks learning screens and offers an access recheck after reactivation.
Forms show backend validation errors without losing entered values. Archive and revocation actions
explain their effects before confirmation. Lesson content and text answers render as plain text.
Text answers count when submitted; multiple-choice answers must be correct. The separate Progress
screen summarizes courses, while authoring, enrollment, and questions live on each course page.

## Sessions, Accessibility & Performance

Tokens live in memory and tab-scoped `sessionStorage`; passwords are never persisted by this app.
Reloading revalidates identity with the backend. A 401 clears the session; 403 permission errors
remain distinct. Sign-out requests backend token revocation and always clears this device's token.
Backend authorization remains authoritative regardless of visible navigation.

Hash routes support deep links and browser navigation without production rewrite rules. Requests
are abortable with a 15-second timeout. The Courses screen uses server-filtered, ten-row pages;
the tenant overview requests four courses plus a total count. Other collections fetch backend
pages of 100 records only when opened and paginate locally at ten rows. The Progress screen
fetches progress for only its ten visible rows in one authorized batch request. There is no
polling, external font service, animation library, or image CDN. Geist is locally served.
At larger scale, add server filtering/count endpoints for the remaining collections.

The UI supports 375px, 768px, and 1440px layouts, labeled inputs, 44px targets, keyboard focus,
native modal focus containment/restoration, skeletons, retryable errors, and reduced motion.

## Validation

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run format:check
npm.cmd run build
npx.cmd playwright install chromium --only-shell
npm.cmd run test:e2e
```

Unit tests cover scoped login requests, bearer headers, validation/errors, cancellation, and pagination.
Playwright verifies all five roles, reload/logout, course and lesson creation, lesson questions,
answer submissions, in-course enrollment, progress, revocation, last-admin protection,
expiration/reactivation, retries, session revocation, responsive layouts, and keyboard dialogs
against real PostgreSQL/Redis.

Browser tests require the backend virtual environment and local PostgreSQL/Redis. They start an API
on port 8001 using a randomly named `e2e_*` schema and Vite on 4173, leaving normal services on
8000/5173 untouched. Only generated test schemas and their Redis keys are removed. Test Redis
databases are 13/14. Screenshots and failure traces live in gitignored `test-results/`.
If a run is interrupted, `../backend/.venv/Scripts/python.exe e2e/server.py --cleanup` removes its
recorded test schema; use `.venv/bin/python` on Linux/macOS.

## Production

Serve `dist/` with `/api` reverse-proxied to FastAPI, or set `VITE_API_BASE_URL` before building.
`npm run preview` serves static output without the development API proxy. Frontend environment
variables are public; never put secrets in them. Use HTTPS and a restrictive Content Security
Policy appropriate to the deployed origin. The frontend makes no AI course-generation requests.
