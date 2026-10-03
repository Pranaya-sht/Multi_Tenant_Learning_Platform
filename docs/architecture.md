# Architecture and Design Decisions

This document describes the implemented learning platform. The separately required AI course-generation design is intentionally excluded because the take-home brief requires the contributor to write it without AI assistance.

## Boundaries and data model

The React application calls a versioned FastAPI JSON API. PostgreSQL holds all authoritative state. Redis holds a short-lived course-detail cache and an RQ queue; neither determines permissions. SQLAlchemy defines tenant, account, course, lesson, enrollment, progress, question, and answer tables; Pydantic validates API payloads, and Alembic versions the schema.

```text
Tenant
  ├── User (platform users have no tenant)
  └── Course ── Lesson
       └── Assignment (course + learner) ── LessonProgress (assignment + lesson)
```

Each `Lesson` can have `LessonQuestion` rows. A `LessonAnswer` links one question to the learner's matching course `Assignment`; `LessonProgress` still represents completion of a lesson. This uses one PostgreSQL schema with `tenant_id` on tenant-owned records. It keeps migrations and local operations simple for multiple institutes. The tradeoff is that every learning query must include tenant scope. Composite foreign keys add a second defense: a course cannot be assigned to another tenant's user, and answers or progress cannot refer to an unrelated lesson or enrollment. Platform users have a null `tenant_id`; a role/scope constraint prevents platform roles from being stored as tenant users. Email is unique per tenant and independently among platform accounts.

## Identity and request path

1. Login finds a platform account by email with no tenant slug, or joins the supplied slug to locate a tenant account. Passwords use Argon2 hashes. Two accounts with the same email remain separate identities and can have different passwords and roles.
2. FastAPI issues a signed 30-minute JWT containing account ID, tenant ID, and token version. Each authenticated request validates the JWT and reloads the active account from PostgreSQL, checking tenant scope and token version. Logout, password reset, role change, and deactivation invalidate prior tokens for that account.
3. A dependency checks the role. Tenant learning dependencies lock the tenant row and check the current trial deadline. Routes derive `tenant_id` from the validated account and filter by it; learners additionally need an assignment to read a course or its progress. Cross-tenant and unassigned IDs yield 404.
4. Only after assignment authorization may a course-detail request read Redis. Cache keys include tenant ID, course ID, and content version. Writes increment that version; cache failures fall back to PostgreSQL.

The frontend uses role-aware navigation for usability, but it is never the access-control boundary. It keeps the JWT in memory and tab-scoped `sessionStorage`, revalidates the account after reload, and clears the local session on a 401.

## Tenant isolation

All tenant-owned rows carry a `tenant_id`. The API gets that ID from the validated account, not from an ID supplied in the request. A course or user lookup matches both the requested resource ID and the account's tenant ID. Learners also need an assignment to the course. Changing a URL to use another institute's course or user ID therefore returns 404; it does not expose whether that resource exists. Composite foreign keys prevent cross-tenant assignments, answers, and progress even if a write reaches the database. Course cache keys include the tenant ID, and the API checks assignment access before reading a cached course.

## Learning rules

A Tenant Admin creates a course, ordered lessons, and optional questions inside each lesson, then enrolls an active learner in the same tenant. The existing `Assignment` row is the course access grant; it is not a separate question task. Lesson and question structure are locked once any enrollment exists, keeping the lesson-count denominator and grading rules stable. Lesson text can still be edited. A question-based lesson completes only after every multiple-choice answer is correct and each text answer is nonblank; text is recorded as submitted, not automatically graded. Lessons without questions retain the original manual completion action. Both paths write the same `LessonProgress` row, so course percentages remain based on completed lessons. Repeated successful submissions are idempotent. Tenant-scoped foreign keys link answers to the matching question, lesson, and enrollment; answer keys are sent only to Tenant Admins. Revoking enrollment removes its answers and progress; archiving a course stops new enrollments but preserves existing content and progress.

## Tenant trial and expiration

Tenant creation starts in `created` while the first Tenant Admin is added. Both changes commit together, with the tenant set to `trial_active`; callers never see a partially initialized tenant. The trial deadline is UTC creation time plus `TRIAL_DAYS` (14 by default). At or after that deadline, the tenant is effectively `expired`.

Every learning request checks the stored status and deadline, so learning access closes even if Redis, the scheduler, or the worker is unavailable. Login and the tenant's own metadata remain available so users can see why access stopped. Existing users, courses, lessons, questions, answers, enrollments, and progress are preserved.

The scheduler enqueues an expiration sweep every 60 seconds by default. Its worker conditionally updates only due, nonexpired tenants, so repeated processing has no additional effect. A Super Admin can reactivate a tenant by setting a new access window from the current UTC time. A queued old sweep rechecks the deadline and cannot expire a tenant that was reactivated with a future deadline.

## Deliberate limits

The implementation has no public signup, invitations, payments, password recovery, or refresh tokens; administrators provision users as required by the brief. It needs a login rate limit, TLS, private Redis/PostgreSQL, and secret management before public deployment. Courses use server-side search and ten-row pages; people, institutes, and assignments still fetch 100-row API pages and filter locally when opened. Those views can move independently if their collections grow. The `/ready` endpoint checks data-service connections, not worker liveness or migration state.

## How to inspect the implementation

- Roles: [`backend/app/core/roles.py`](../backend/app/core/roles.py); request authorization: [`backend/app/api/dependencies.py`](../backend/app/api/dependencies.py).
- Data constraints: [`backend/app/models/domain.py`](../backend/app/models/domain.py); lesson question and answer routes: [`backend/app/api/routes/exercises.py`](../backend/app/api/routes/exercises.py); migrations: [`backend/alembic/versions/`](../backend/alembic/versions/).
- Learning routes: [`backend/app/api/routes/learning.py`](../backend/app/api/routes/learning.py); lifecycle: [`backend/app/services/tenants.py`](../backend/app/services/tenants.py), [`backend/app/jobs.py`](../backend/app/jobs.py).
- Exact API workflows, permissions, and tests: [`backend/README.md`](../backend/README.md).
