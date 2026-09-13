# Repository Guidelines

## Project Structure

SparkFlow is a multi-tenant plugin execution platform. Douyin streak maintenance
is its first trusted plugin under `backend/plugins/`. `app/` and `components/` are the Next.js App Router UI;
`lib/` contains the strict Drizzle ORM schema and DB singleton; `backend/`
contains FastAPI routes, SQLAlchemy models, billing/Epay services, and the
worker; `drizzle/` stores generated MySQL migrations.

Keep user-owned resources scoped by `user_id`. Browser execution belongs in the
Python worker, never inside a Next.js request or Server Action.

## Development Commands

Key frontend commands:

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
`npm run db:migrate`. Use `npm run db:generate` only after schema changes. The full stack is also
available with `docker compose up -d --build`. Only platform entry points are
maintained; shared browser modules remain under `core/`.

## Coding Style

Use strict TypeScript, four-space Python indentation, `snake_case` Python names,
and PascalCase React components. Validate boundaries with Zod or Pydantic.
Keep payment callbacks idempotent, avoid logging cookies or secrets, and prefer
existing helpers and UI primitives before adding abstractions.

## Testing

Backend tests use `pytest` under `backend/tests/` and should be named
`test_*.py`. Add focused coverage for authentication, tenant isolation, billing
transitions, and worker behavior. Before submitting changes, run:
`npm run typecheck`, `npm run lint`, `npm run build`, and
`python -m pytest backend/tests -q`.
Use `python scripts/smoke_platform.py` for isolated SQLite HTTP/UI checks.
Synthetic cookie/friend fixtures do not verify live Douyin compatibility.
Keep runtime settings encrypted in the database; retain deployment bootstrap
secrets outside Git. New plugins must declare configuration and account requirements explicitly.

## Commits and Pull Requests

Use focused prefixes such as `feat:`, `fix:`, `docs:`, `ci:`, and `refactor:`.
Pull requests should describe affected roles and API routes, list validation
commands, include UI screenshots for visual changes, and call out migrations,
environment variables, payment flows, or credential-handling changes.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
