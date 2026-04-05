# Copilot Instructions — Expense Tracker & Budget Insights

## Project overview

Multi-tenant SaaS web app for couples/families to track shared expenses. React SPA frontend + FastAPI backend + PostgreSQL. Currently in pre-code phase (MVP / 1.0.0) — design docs exist but source code has not been written yet.

Check `SCOPE.md` before building any feature to confirm it's in scope for the current version (MVP). Key docs: `PRD.md` (what/why), `ARCHITECTURE.md` (how), `REQUIREMENTS.md` (quality bars), `CONVENTIONS.md` (how to work), `SCOPE.md` (version roadmap), `design/UI_SPECS.md` (visual specs & design system).

## Design system & frontend references

The `design/` folder at project root is the single source of truth for all frontend visual decisions:

- **`design/UI_SPECS.md`** — complete design system: color palette (Cool Lavender + Sage), typography (Ubuntu), component rules, responsive breakpoints, per-view layout specs by version.
- **`design/home-mobile.html`** + **`design/home-desktop.html`** — visual reference mockups for the Home dashboard.
- **`design/transactions-mobile.html`** + **`design/transactions-desktop.html`** — visual reference mockups for the Transaction list.
- **`design/add-expense-mobile.html`** + **`design/add-expense-desktop.html`** — visual reference mockups for the Add Expense form.

**When building any frontend view**, open the corresponding HTML reference file first to understand the exact layout, colors, spacing, and component structure expected. These mockups are the design authority — implement views to match them.

## Build, test, and lint commands

### Backend (Python / FastAPI)

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # Windows
source venv/bin/activate           # macOS/Linux
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run server
uvicorn app.main:app --reload

# Lint & format
ruff check .
ruff check . --fix
black .

# Tests (all)
pytest

# Single test file
pytest tests/unit/test_limits.py

# Single test function
pytest tests/unit/test_limits.py::test_weekly_limit_calculation -v

# Seed dev data
python -m app.seed
```

### Frontend (React / Vite)

```bash
cd frontend
npm install

# Run dev server
npm run dev

# Lint & format
npx eslint .
npx prettier --check .
npx prettier --write .

# Build
npm run build
```

### Database (PostgreSQL + Alembic)

```bash
cd backend
alembic upgrade head                               # Apply migrations
alembic revision --autogenerate -m "description"   # Create migration
```

## Architecture

**Three-tier**: React SPA → FastAPI REST API → PostgreSQL.

- **Frontend** (Azure Static Web Apps): Vite + React + TypeScript, React Router v7, shadcn/ui + Tailwind, Recharts, TanStack Query. Proxies `/api/*` to backend via `linkedBackend` (no CORS needed).
- **Backend** (Azure App Service): FastAPI + Pydantic schemas + SQLAlchemy 2.0 async ORM + Alembic migrations. JWT auth via httpOnly cookies. Google OAuth only.
- **Database** (Azure PostgreSQL): All datetimes stored as UTC. Space timezone used only for display and time window calculations.

### Layered backend (strict separation)

- **Routers** (`app/routers/`): HTTP concerns only — parse request, call service, return response. No business logic.
- **Services** (`app/services/`): All business logic — validation, calculations, orchestration. No HTTP awareness.
- **Models** (`app/models/`): SQLAlchemy ORM — database structure only. No business logic.
- **Schemas** (`app/schemas/`): Pydantic request/response contracts. Separate schemas for request vs response when they differ.

### Multi-tenancy

Every space-scoped query **must** include `space_id` in the WHERE clause. Use the `SpaceScopedRepository` pattern — never write raw queries against space-scoped tables. Direct UUID lookups must always include `AND space_id = :space_id`.

### API design

- All endpoints under `/api/2.0.0/`, space-scoped under `/api/2.0.0/spaces/{space_id}/...`
- Plural resource names, kebab-case for multi-word (`/payment-methods`)
- Use PATCH for most updates (with `model.model_dump(exclude_unset=True)`); PUT only for full replacements (space settings, category rename)
- Cursor-based pagination: `{ "data": [...], "next_cursor": "..." }`
- Errors: `{ "error": { "code": "ERROR_CODE", "message": "...", "details": {...} } }`

### TimeWindowResolver

All time window math (week/month/quarter/year boundaries) must go through a single `TimeWindowResolver` utility — no ad-hoc timezone calculations anywhere. Week starts Monday. The frontend TypeScript version must produce identical boundaries to the backend Python version.

## Key conventions

### Python (backend)

- Python 3.11+, `async def` for all route handlers and DB operations
- Formatter: `black` (defaults). Linter: `ruff`
- Type hints required on all function signatures
- Docstrings required for service functions and complex logic, not for simple CRUD handlers
- Files: `snake_case.py`. Classes: `PascalCase`. Functions/vars: `snake_case`. Constants: `UPPER_SNAKE_CASE`

### TypeScript (frontend)

- Strict mode enabled. Formatter: `prettier`. Linter: `eslint`
- Files: `kebab-case.tsx` (components), `camelCase.ts` (utilities)
- Functional components with hooks only. Props defined with TypeScript interfaces, never `any`
- TanStack Query for server state; `useState`/`useReducer` for local UI state only
- One custom hook per domain (`useExpenses`, `useLimits`, etc.)

### SQL / Migrations

- Tables: `snake_case`, plural. One migration per logical change.
- All datetimes as `TIMESTAMPTZ`, stored UTC

### Git

- Branch naming: `feature/{desc}`, `fix/{desc}`, `release/{version}`, `hotfix/{desc}`
- Commits: `type: short description` (types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`)
- Squash merge to `main`. All tests must pass before merge.

### Dependencies

- Frontend: `npm` only (no yarn/pnpm), pin exact versions, shadcn/ui components copied into `src/components/ui/`
- Backend: `pip` with `requirements.txt` (pinned), always use venv

### Documentation

- The 6 project docs (PRD, ARCHITECTURE, REQUIREMENTS, CONVENTIONS, SCOPE, design/UI_SPECS) are the source of truth. If any of them become outdated or are missing information as the product is built, update them proactively.
- The `design/` folder contains UI_SPECS.md + HTML visual reference mockups. When building frontend views, consult both the specs and the mockups.
- If scope grows or new documentation is strictly needed beyond the existing docs, create a new document for it.
- Code comments only for non-obvious *why*, not *what*

### Business rules to watch

- No future-dated expenses (server-side 422)
- Only confirmed expenses count toward limits and insights (pending excluded)
- Category deletion atomically reassigns orphans to "Uncategorized"
- Payment method deletion sets `payment_method_id` to NULL; frontend shows "Deleted method"
- Tags stored without `#` prefix, normalized lowercase; `#` is display-only
- Merchant → category suggestion uses latest category by expense creation time (not purchase date)
- `expenses.updated_at` set by service layer, not DB triggers
