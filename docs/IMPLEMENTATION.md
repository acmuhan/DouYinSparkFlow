# SparkFlow Product Implementation

The product is being rebuilt in this repository. The legacy CLI remains available
until its replacement Runner is verified. Do not interpret this checklist as a
claim of production readiness.

## Architecture

- Next.js App Router, TypeScript, Tailwind CSS and shadcn/ui primitives.
- Same-origin Route Handlers validate Zod contracts and forward to Python.
- Python FastAPI owns sessions, role/tenant authorization, billing and jobs.
- Drizzle owns MySQL schema and reviewed migrations. SQLAlchemy maps the same
  tables for Python transactions; integration tests check schema parity.
- A separate Python worker claims MySQL jobs. Browser execution never runs in a
  Next.js request or a serverless function.

## Acceptance Checklist

- [ ] USER/ADMIN sessions, registration, profile, password and API keys
- [ ] Tenant-scoped encrypted accounts, task CRUD, scheduling, quota enforcement
- [ ] Isolated browser Runner, queued execution, cancellation and run history
- [ ] Plans, monthly/quarterly/yearly orders and subscription activation/renewal
- [ ] Epay V1/V2 signing, checkout, callbacks, reconciliation and refunds
- [ ] Admin metrics, users, entitlements, quota changes, plans and audit logs
- [ ] MySQL migrations, concurrency/isolation tests and TypeScript checks
- [ ] Desktop/mobile rendered UI and end-to-end browser tests
- [ ] Docker deployment, configuration and operational documentation

Live payment verification requires the operator's Epay endpoint/merchant keys.
Live messaging verification requires an authorized Douyin account and recipient.
Neither will be simulated as a successful real-world transaction.
