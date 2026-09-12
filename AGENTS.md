# Repository Guidelines

## Architecture

SparkFlow is a commercial multi-tenant console layered over the legacy Douyin
Playwright runner. `app/` and `components/` are the Next.js App Router UI;
`lib/` contains the strict Drizzle ORM schema and DB singleton; `backend/`
contains FastAPI routes, SQLAlchemy models, billing/Epay services, and the
worker; `drizzle/` stores generated MySQL migrations.

Keep user-owned resources scoped by `user_id`. Browser execution belongs in the
Python worker, never inside a Next.js request or Server Action.

## Local Development

Install frontend dependencies and run checks:

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run build
```

Run the API and worker locally with MySQL 8+:

```bash
python -m pip install -r backend/requirements.txt
uvicorn backend.app:app --reload --port 8000
python -m backend.worker
```

Copy `.env.platform.example` to `.env.local`, set `DATABASE_URL`, and run
`npm run db:generate` followed by `npm run db:migrate`. The full stack is also
available with `docker compose up -d --build`; the legacy script is behind the
`legacy` Compose profile.

## Code and Tests

Use strict TypeScript, four-space Python indentation, snake_case Python names,
and PascalCase React components. Validate requests with Zod/Pydantic; keep
payment callbacks idempotent and never log cookies or secrets. Backend tests
use `pytest` under `backend/tests/`. Before a pull request run:
`npm run typecheck && npm run lint && npm run build` and
`python -m pytest backend/tests -q`.

## Commits and Pull Requests

Use focused prefixes such as `feat:`, `fix:`, `docs:`, `ci:`, and `refactor:`.
Pull requests should describe affected roles and API routes, list validation
commands, include UI screenshots for visual changes, and call out migration,
environment-variable, payment, or credential-handling changes.
