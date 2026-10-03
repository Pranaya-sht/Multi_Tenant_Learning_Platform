# Learning Platform Backend

FastAPI with JWT authentication, Argon2 passwords, PostgreSQL/SQLAlchemy, Pydantic, Alembic,
Redis caching, and RQ expiration jobs. Interactive API documentation: http://127.0.0.1:8000/docs.

## Setup

Start PostgreSQL and Redis from the repository root:

```powershell
docker compose up -d --wait
```

Then from `backend/`:

```powershell
uv sync --locked
uv run python scripts/init_env.py
uv run alembic upgrade head
uv run python -m app.bootstrap --demo
uv run uvicorn app.main:create_app --factory --reload --host 127.0.0.1 --port 8000
```

Alternatively, configure existing PostgreSQL and Redis instances in `.env`. Environment variables
override the file. No tables or accounts are created automatically on API startup.
Compose exposes PostgreSQL on loopback port **5433**, avoiding the existing PostgreSQL service
on this machine's port 5432, and Redis on port 6379.

Run both background services in one terminal from `backend/`:

```powershell
uv run python -m app.background
```

The worker processes jobs while a scheduler thread submits an expiration
sweep every `EXPIRATION_INTERVAL_SECONDS` (default 60). The worker and queue use JSON serialization.
Windows development uses RQ SimpleWorker with its timer-based timeout; Linux uses a forked Worker.
The original `python -m app.worker` and `python -m app.scheduler` commands remain available for
separate production processes. Use Linux for production job isolation and periodic worker
heartbeats. Repeated jobs are safe.
Each sweep re-reads current expiration
dates, so an old queued job cannot expire a reactivated tenant whose deadline is in the future.

## Local Demo Credentials

The explicit `--demo` command only permits a loopback database. All demo accounts use
`LocalDemo-learning-2026!`. These are development credentials, not production bootstrap defaults.
Running the command again preserves existing passwords, tenant deadlines, and progress.

| Email | Role | Tenant |
| --- | --- | --- |
| superadmin@example.com | Super Admin | Platform |
| admin@example.com | Admin | Platform |
| viewer@example.com | Super Viewer | Platform |
| river.admin@example.com | Tenant Admin | River Institute |
| river.learner@example.com | Tenant User | River Institute |
| summit.admin@example.com | Tenant Admin | Summit Institute |
| summit.learner@example.com | Tenant User | Summit Institute |

Each institute receives an independent two-lesson demonstration course and learner assignment.
For a private bootstrap instead of demo accounts:

```powershell
uv run python -m app.bootstrap --email your-admin@example.com
```

Enter a password of 12–128 characters at the hidden prompt. Do not use demo accounts in production.

## Authentication & Permissions

`POST /api/v1/auth/login` returns an access token. Tenant accounts supply `email`, `password`,
and `tenant_slug`; platform accounts omit `tenant_slug` or set it to null.
`GET /api/v1/auth/institutes?q=river` is a public, bounded name/slug lookup for the sign-in
picker. It returns at most ten `{name, slug}` suggestions, including expired institutes so their
accounts can still reach the expiration screen. It reveals no accounts or trial metadata.
Use `Authorization: Bearer <access_token>`. Emails are normalized to lowercase and unique within
each tenant, with a separate unique namespace for platform accounts. The same email may have
independent accounts, passwords, roles, and progress in multiple tenants. There is no shared
identity or automatic tenant switching; authenticate again for a different tenant.

```json
{
  "email": "river.learner@example.com",
  "password": "LocalDemo-learning-2026!",
  "tenant_slug": "river-institute"
}
```

River demo accounts use `river-institute`; Summit demo accounts use `summit-institute`.
Missing, unknown, or incorrect account scope yields the same 401 credential error. Tenant slugs
select an account only during login; subsequent requests derive tenant scope from validated JWT
and database identity.
`GET /auth/me` and `/auth/permissions` expose the current identity and permission set.
`POST /auth/logout` revokes all current tokens for that account. Disablement, role changes, and
password resets also invalidate old tokens. JWT claims are verified, then the account and current
permissions are reloaded from PostgreSQL; Redis is never the authority for identity or access.

All paths below are relative to `/api/v1`.

| Action | Super Admin | Admin | Super Viewer | Tenant Admin | Tenant User |
| --- | --- | --- | --- | --- | --- |
| List/read tenant metadata | Yes | Yes | Yes | Own tenant | Own tenant |
| Create tenants and initial admin | Yes | Yes | No | No | No |
| Rename tenants | Yes | Yes | No | No | No |
| Expire/reactivate tenants | Yes | No | No | No | No |
| List platform accounts | Yes | Yes | Yes | No | No |
| Create platform accounts | Yes | No | No | No | No |
| Manage tenant users/courses/lessons | No | No | No | Own tenant | No |
| Create/edit lesson questions and read submitted answers | No | No | No | Own tenant | No |
| Assign/revoke courses | No | No | No | Own tenant | No |
| Read learning content | No | No | No | Own tenant | Assigned only |
| Read learning progress | No | No | No | Own tenant | Own only |
| Complete lessons | No | No | No | No | Own assignments |
| Submit lesson answers | No | No | No | No | Own enrolled courses |

Platform accounts cannot access tenant learning APIs, including Super Admin. Tenant context comes
from the validated account, never a client-supplied tenant identifier. Cross-tenant and unassigned
resource IDs return 404. Insufficient roles and expired learning access return 403.

## API Workflows

- `/tenants`: GET paginated list; POST creates a tenant and initial admin atomically. Supply
  `name`, lowercase `slug`, and `admin: {name, email, password}`.
- `/tenants/{id}`: GET metadata; PATCH `{name}`. POST `/expire` restricts learning immediately;
  POST `/reactivate` with `{days: 14}` gives a new access window from the current UTC time.
- `/platform-users`: GET list; POST `{name, email, password, role}` by Super Admin.
- `/tenant`: GET own metadata, including expiration, even after the trial expires.
- `/tenant/users`: GET list; POST `{name, email, password, role}` with `role=tenant_user`.
  Each institute has exactly one Tenant Admin. PATCH `/{id}` updates name or learner active status; it cannot
  create a second admin or remove the only admin. PUT `/{id}/password` resets a password.
  Deactivation invalidates existing tokens but keeps assignments and progress.
- `/tenant/users/{id}/transfer-admin`: Tenant Admin POST transfers the sole admin role to an active
  learner in the same institute. Both role changes commit together, their old JWTs are revoked,
  and assignments/progress stay in place. The previous admin becomes a learner and must sign in
  again. PostgreSQL enforces at most one Tenant Admin per institute with a partial unique index.
- `/tenant/courses`: GET list; POST `{title, description}`. GET `/{id}` includes lesson content.
  PATCH updates metadata or `is_archived`; DELETE archives without removing data.
- `/tenant/courses/page`: GET `{items, total, limit, offset}` with `limit`, `offset`, optional
  `q` (literal title/description substring), and `status=all|active|archived`. Ordering is stable
  by creation time and ID. The original list response remains unchanged.
- `/tenant/courses/{id}/lessons`: POST `{title, content, position}`. PUT `/{lesson_id}` edits
  title/content. Positions start at 1 and must be unique. Adding lessons is blocked once a course
  has assignments, so completion denominators do not change unexpectedly.
- `/tenant/courses/{id}/questions`: Tenant Admin GET lists the course's lesson questions, including
  multiple-choice answer keys. POST/PUT/DELETE on `/lessons/{lesson_id}/questions[/{question_id}]`
  add, replace, or remove a question. A question has `kind` (`multiple_choice` or `text`), `prompt`,
  and, for multiple choice, 2–6 `options` plus a zero-based `correct_option`. Question structure
  is locked after the first learner is enrolled. Each lesson supports up to 20 questions. These
  questions form the lesson's assignment; no separate assignment record is created for them.
- `/tenant/courses/{id}/lessons/{lesson_id}/exercise`: An enrolled learner GETs questions and their
  own saved answers, without answer keys. PUT submits one answer per question as
  `{ "answers": [{ "question_id": "...", "response": "1" }] }`. For multiple choice, `response`
  is the zero-based option number; incorrect answers remain saved and can be retried. A nonblank
  text answer counts as submitted and is **not automatically graded**. When all answers qualify,
  the lesson counts toward existing course progress. The old manual completion route returns 409
  for lessons with questions; it remains available for lessons without questions.
- `/tenant/courses/{id}/lessons/{lesson_id}/answers`: Tenant Admin GET reads learner submissions,
  with `limit` and `offset`. Learners cannot read other learners' answers.
- `/tenant/assignments`: GET own/tenant list; POST `{course_id, user_id}`. A course must have
  lessons, be unarchived, and target an active learner in the same tenant. Duplicates return 409.
  DELETE `/{id}` revokes access and removes that enrollment's answers and progress. This existing
  course-level assignment remains an access grant; question-based work lives inside lessons.
- `/tenant/assignments/batch`: Tenant Admin POST `{course_id, user_ids}` with 1–50 distinct learner
  IDs. All users must be active learners in the admin's institute, the course must be active with
  lessons, and none may already be enrolled. The operation commits all enrollments together or
  creates none. The existing single-user endpoint remains available.
- `/tenant/assignments/{id}/progress`: GET totals, completed IDs, percentage, and completion state.
  PUT `/{id}/lessons/{lesson_id}/complete` records completion idempotently for the assigned learner.
- `/tenant/assignments/progress`: GET up to ten repeated `assignment_ids` query parameters in
  one response. Every ID must belong to the authenticated tenant and, for a learner, to that
  learner; otherwise the whole request returns 404. Existing single-assignment progress remains.

List endpoints accept `limit` (1–100, default 50) and `offset` (nonnegative). Unexpected body fields
are rejected. Lesson content is plain text; clients must escape it rather than execute it as HTML.
Archived courses remain accessible to existing assignees but cannot receive new assignments.

## Tenant Lifecycle, Isolation & Caching

Creation transitions `created` to `trial_active` within one transaction. The default 14-day trial
is calculated from UTC creation time; equality at the deadline counts as expired. Every learning
request checks the current database deadline and status before querying content or using caches.
Expiration therefore blocks access even when the worker/scheduler is stopped. Account login and
own tenant metadata remain available; users, courses, lesson questions, answers, enrollments, and
progress are preserved.
Super Admin can reactivate an institute with a new duration, preserving its existing data.

The expiration sweep performs one conditional UPDATE, changing only due, nonexpired tenants.
Repeating it has no additional effect. PostgreSQL tenant-row locks coordinate lifecycle changes
with learning requests; tenant-admin operations serialize to protect last-admin and lesson rules.
Learner reads use shared tenant locks, and lesson completion also locks its assignment.

All learning queries include tenant scope. Composite foreign keys additionally prohibit linking
an assignment to another tenant's user/course, or linking progress to an unrelated lesson.
Course-detail cache keys include tenant, course, and content version. Writes advance the version;
entries expire after `CACHE_SECONDS` (default 60). Assignment authorization always runs before a
cache read, including after revocation. Cache failure falls back to PostgreSQL. Cache and queue
use Redis logical databases 0 and 1; do not flush queue data to invalidate a cache.

## Tests & Migrations

```powershell
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run alembic upgrade head --sql
```

By default workflow tests use isolated SQLite databases with foreign keys enabled; health checks
mock infrastructure. To run the same workflows and migration round trip against PostgreSQL:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://learning:local-development-only@127.0.0.1:5433/learning_platform'
$env:REDIS_TEST_URL = 'redis://127.0.0.1:6379/15'
uv run pytest -q
Remove-Item Env:TEST_DATABASE_URL
Remove-Item Env:REDIS_TEST_URL
```

Tests create a randomly named schema per case and drop only that schema. The test account needs
schema-creation permission. Use a development database, never production. PostgreSQL runs verify
actual composite constraints, UUID/timestamp handling, API queries, and migration upgrade/downgrade.
Concurrency tests require PostgreSQL because SQLite ignores row-lock clauses.
Providing `REDIS_TEST_URL` also exercises real cache TTL/authorization and the configured RQ worker processing
two expiration jobs against the test schema. Tests remove only their own generated cache/queue
keys; they never flush Redis. Backend CI runs these checks with PostgreSQL and Redis services.

New models must be imported in `app/models/__init__.py`; create and review migrations with
`uv run alembic revision --autogenerate -m "describe change"`. The initial revision is
`0001_learning_schema`; `0002_tenant_scoped_email` preserves existing accounts while replacing
global email uniqueness. Apply it with `uv run alembic upgrade head`. Downgrading to global email
uniqueness is refused if duplicate emails exist across scopes; resolve those accounts explicitly.
Never edit applied revisions.

## Deployment Notes

Use private database credentials, a random JWT key, TLS, and restricted Redis access. Provide a
login rate limit at the ingress before exposing the API publicly. Access tokens expire after
30 minutes; there is no refresh-token or password-recovery flow. Expiration is a free-trial
lifecycle without payments or subscriptions. Health `/live` checks API liveness; `/ready` checks
PostgreSQL and both Redis connections, but not worker availability or migration state.

The contributor's [AI course-generation design draft](<../AI Course Design.md>) is separate from
this backend implementation. The take-home brief requires this design to be written by the
contributor and does not require an AI course-generation endpoint or command.

The local API benchmark script is `scripts/benchmark_api.py`.
