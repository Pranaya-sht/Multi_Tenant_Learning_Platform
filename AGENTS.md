# Repository Guidelines

## Technology & Structure

Use FastAPI, JWT, SQLAlchemy, Pydantic, PostgreSQL, Alembic, and Redis/RQ; React JavaScript, Vite, and Tailwind for frontend.

Read the take-home Markdown brief first. Code: `backend/app/`; tests: `backend/tests/`; migrations: `backend/alembic/`; frontend: `frontend/src/`. Compose provides PostgreSQL on 5433 and Redis on 6379. Both applications are implemented.

## Development Commands

From `backend/`:

- `uv sync --locked`: install dependencies.
- `uv run python scripts/init_env.py`: initialize local configuration.
- `uv run uvicorn app.main:create_app --factory --reload`: serve the API.
- `uv run python -m app.background`: run the queue worker and expiration scheduler together locally.
- `uv run python -m app.worker` and `uv run python -m app.scheduler`: optional separate processes.
- `uv run alembic upgrade head`: apply migrations.
- `uv run pytest -q`: run tests.
- `uv run ruff check .`: lint; `uv run ruff format .`: format.

From `frontend/`: `npm.cmd ci`, `npm.cmd run dev`, `npm.cmd run build`, `npm.cmd test`, `npm.cmd run lint`, and `npm.cmd run format:check`. `npm.cmd run test:e2e` uses isolated PostgreSQL/Redis and Playwright. Use `npm` outside Windows.

## Coding Style

Use four-space Python and two-space JavaScript indentation: `snake_case` functions, `PascalCase` classes/components, and JavaScript `camelCase`. Follow Ruff, Oxlint, and Prettier. Validate with Pydantic; change schemas through Alembic.

## Frontend Design & Optimization

Use Stitch MCP for design/refinement and reuse the existing project design system.

Inspect screenshots and HTML before adapting them into React/Tailwind. Preserve real API behavior; never present mock metrics as live data. Use shared tokens, local assets, semantic controls, visible focus, and 44px touch targets. Check 375px, 768px, and 1440px layouts. Animate transform/opacity, respect reduced motion, and avoid unnecessary polling or CDN scripts.

## Testing

Use pytest (`test_*.py`) and Vitest (`*.test.js`). Cover JWT validation, all roles, isolation, expiration, repeated jobs, assignments, and progress. Set `TEST_DATABASE_URL` and `REDIS_TEST_URL` to exercise PostgreSQL constraints, concurrency, migrations, caching, and the queue; tests use isolated schemas/keys. No 100% coverage requirement.

## Commits & Pull Requests

No Git history exists. Use imperative commits: `Add tenant-scoped course queries`. Describe behavior, checks, and migrations; link issues and include screenshots.

## Security & Agent Instructions

Enforce backend permissions. Derive tenant scope from validated identity; scope queries, cache keys, and queued jobs. Never commit secrets; preserve expired-tenant data.
Emails are unique per tenant and separately within platform accounts. Tenant login requires `tenant_slug`; preserve this scope in account lookups.
Multiple platform Super Admins are allowed. Each institute has exactly one Tenant Admin; creation and promotion cannot add another. Transfer the role atomically and revoke both accounts' prior JWTs. Preserve the partial unique index and never silently demote accounts in migrations.
Lesson questions belong to courses and lessons; learner answers belong to the matching course enrollment. Keep answer keys out of learner responses, and lock question structure after enrollment so progress rules stay stable.

AI coding assistance is allowed. The brief prohibits AI-written course-generation design documentation; leave that design to the contributor.
