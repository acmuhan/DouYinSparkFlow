# SparkFlow Product Implementation

The product is being rebuilt in this repository. The legacy CLI remains available
until its replacement Runner is verified. Do not interpret this checklist as a
claim of production readiness.

## Architecture

- Next.js App Router, TypeScript, Tailwind CSS and shadcn/ui primitives.
- Same-origin Route Handlers forward to Python; selected frontend contracts use
  Zod, while Python validates request schemas with Pydantic.
- Python FastAPI owns sessions, role/tenant authorization, billing and jobs.
- Drizzle owns MySQL schema and reviewed migrations. SQLAlchemy maps the same
  tables for Python transactions; live migration/schema parity still needs verification.
- A separate Python worker claims MySQL jobs. Browser execution never runs in a
  Next.js request or a serverless function.

## Acceptance Checklist

Code-level functionality implemented in this repository:

- [x] USER/ADMIN sessions, registration, profile, password and API keys
- [x] Tenant-scoped encrypted accounts, task CRUD, scheduling and quota enforcement
- [x] Isolated browser Runner, queued execution, cancellation and run history
- [x] Plans, monthly/quarterly/yearly orders and subscription activation/renewal
- [x] Epay V1/V2 signing, checkout, POST callbacks, reconciliation and manual refund records
- [x] Admin metrics, users, entitlements, quota changes, plans and audit logs
- [x] MySQL migrations, schema checks and TypeScript/Python automated checks
- [x] Responsive desktop/mobile console smoke checks

External or environment-dependent verification still required:

- [ ] MySQL concurrency/isolation integration tests against a live MySQL 8 instance
- [ ] Docker deployment runtime verification
- [ ] End-to-end payment and Douyin messaging tests with operator credentials

Live payment verification requires the operator's Epay endpoint/merchant keys.
Live messaging verification requires an authorized Douyin account and recipient.
Neither will be simulated as a successful real-world transaction.

## Operational Documentation

See [Development](DEVELOPMENT.md), [Deployment](DEPLOYMENT.md), and
[Billing](BILLING.md) for executable setup steps and current limitations.
Refund records do not trigger provider refunds. The stock Compose file needs
production environment and payment configuration overrides. A reverse proxy must
route the generated payment notification path to Python.
