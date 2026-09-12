# DouYin Spark Flow

DouYin Spark Flow is a Playwright-based automation project for maintaining
Douyin chat streaks. The repository now includes a commercial multi-tenant
console built with Next.js and a Python API.

## Product Console

The new platform is organized as a SaaS application:

- `app/` contains the Next.js App Router pages and same-origin API routes.
- `components/` contains reusable Tailwind/shadcn-style UI components.
- `lib/` contains the strict Drizzle MySQL schema and database singleton.
- `backend/` contains the FastAPI API, billing services, worker, and tests.
- `scripts/` contains migration and operational helpers.
- `core/` remains the browser automation engine while the new Runner wraps it.

The commercial platform supports user and admin roles, encrypted Douyin
accounts, task scheduling, quota-aware subscriptions, API keys, order audit
logs, and Epay V1/V2-compatible checkout callbacks. See
[`docs/IMPLEMENTATION.md`](docs/IMPLEMENTATION.md) for the architecture and
acceptance checklist.

## Legacy Script

The original local workflow remains available:

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

Do not commit `.env` files, browser cookies, API keys, or generated logs.
Review Douyin's terms and obtain the required authorization before operating
accounts for other people or offering paid automation.

For production, set a unique high-entropy `ENCRYPTION_KEY`; empty values and
the example placeholders are rejected by the API. Configure Epay credentials
and `ADMIN_PASSWORD` through the deployment environment, never in Git.

## License

The project is licensed under the MIT License; see [`LICENSE`](LICENSE).
