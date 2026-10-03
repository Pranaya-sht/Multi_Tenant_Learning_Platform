# Selected AI coding instructions

These are selected excerpts from the `AGENTS.md` project instructions supplied to the assistant in this conversation. They preserve the supplied wording, with headings and line wrapping added for readability. They are project context, not a reconstructed transcript of earlier development prompts.

## 1. Stack and implementation discipline

```text
Use FastAPI, JWT, SQLAlchemy, Pydantic, PostgreSQL, Alembic, and Redis/RQ;
React JavaScript, Vite, and Tailwind for frontend.

Use four-space Python and two-space JavaScript indentation: snake_case functions,
PascalCase classes/components, and JavaScript camelCase. Follow Ruff, Oxlint,
and Prettier. Validate with Pydantic; change schemas through Alembic.
```

## 2. Tenant isolation and identity scope

```text
Enforce backend permissions. Derive tenant scope from validated identity;
scope queries, cache keys, and queued jobs. Never commit secrets;
preserve expired-tenant data.

Emails are unique per tenant and separately within platform accounts.
Tenant login requires tenant_slug; preserve this scope in account lookups.
```

## 3. Account and learning-data invariants

```text
Multiple platform Super Admins are allowed. Each institute has exactly one
Tenant Admin; creation and promotion cannot add another. Transfer the role
atomically and revoke both accounts' prior JWTs. Preserve the partial unique
index and never silently demote accounts in migrations.

Lesson questions belong to courses and lessons; learner answers belong to the
matching course enrollment. Keep answer keys out of learner responses, and lock
question structure after enrollment so progress rules stay stable.
```

## 4. Meaningful verification

```text
Use pytest (test_*.py) and Vitest (*.test.js). Cover JWT validation, all roles,
isolation, expiration, repeated jobs, assignments, and progress.
Set TEST_DATABASE_URL and REDIS_TEST_URL to exercise PostgreSQL constraints,
concurrency, migrations, caching, and the queue; tests use isolated schemas/keys.
No 100% coverage requirement.

Preserve real API behavior; never present mock metrics as live data.
```

The full context, commands, and contributor-only AI course-design restriction remain in [AGENTS.md](AGENTS.md).
