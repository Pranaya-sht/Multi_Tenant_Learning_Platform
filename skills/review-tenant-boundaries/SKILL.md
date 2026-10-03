---
name: review-tenant-boundaries
description: Review this learning platform's API changes for tenant isolation, role enforcement, and lifecycle regressions. Use for focused implementation reviews, not for authoring the AI course-generation design.
---

# Review tenant boundaries

Read `AGENTS.md` at the repository root, then inspect the requested diff or feature.
If no review scope is given, use the current working-tree changes; if there are
none, ask which feature or revision to review. A review request authorizes
inspection and relevant isolated checks, not an unrelated rewrite or publication.

## Follow the actual access path

- Start at `backend/app/api/dependencies.py` for identity, permissions, trial
  checks, and identity refresh after acquiring tenant locks.
- Trace the affected routes under `backend/app/api/routes/`. Establish where
  tenant scope enters every relevant query and where learner assignment access
  is checked. Include nested IDs and batch operations.
- Compare affected relationships in `backend/app/models/domain.py` with Alembic
  revisions. Composite constraints protect tenant/course/enrollment relationships;
  API checks still determine who can read or mutate them.
- For cache changes, inspect `backend/app/infrastructure/redis.py` and the route
  using it. Verify authorization before retrieval, tenant/version key scope,
  and safe fallback when Redis is unavailable.
- For lifecycle changes, trace `services/tenants.py`, `jobs.py`, and the relevant
  scheduler/worker caller. Expiration must block learning at the deadline even
  without a worker; repeated processing and reactivation must preserve data.

Resolve these paths relative to `backend/app/` unless a full repository path is
specified. Consult the backend README for the intended permission matrix rather
than inferring permissions from frontend navigation.

## Preserve the domain invariants

Tenant email addresses are unique within their institute; platform addresses
have their own namespace. Tenant login requires a slug, but subsequent scope
comes from validated identity. A platform account cannot use tenant learning
routes merely because it is a Super Admin.

An institute has one Tenant Admin. Transfer is atomic and revokes both accounts'
old tokens; multiple platform Super Admins are allowed. Flag migrations that
silently demote accounts or remove the uniqueness protection.

Learner answers must match the question's lesson/course and the learner's course
enrollment. Learner responses exclude answer keys. Enrollment locks question
structure; progress writes and repeated jobs must retain their idempotent behavior.

## Validate findings proportionally

Use existing cases in `backend/tests/test_learning.py`, `test_account_scopes.py`,
`test_exercises.py`, and `test_security.py` as appropriate. A suspected access flaw
needs a concrete caller, resource, and request sequence. Exercise PostgreSQL for
row locks, concurrency, migration behavior, and database constraints; SQLite does
not validate those properties. Redis-dependent claims need the real Redis tests.

Use the isolated schema/key setup documented in `backend/README.md`. Do not export
or alter the user's normal tenant records. If services are unavailable, report
which checks could not run without treating that as a passing result.

Return confirmed findings first with severity, file/line evidence, expected versus
observed behavior, and a focused remedy. Separate hypotheses from reproduced
failures. For a clean review, state the inspected scope and test evidence rather
than asserting complete security. Make fixes when the user's request includes
them, then rerun checks affected by the fix.

Do not author the contributor's AI course-generation design or invent submission
history. Follow the repository's existing restriction on that separate document.
