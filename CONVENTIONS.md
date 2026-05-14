# Conventions

This document defines **how developers and agents should work on this project**. It covers coding standards, project structure, Git workflow, environment setup, and operational rules.

---

## 1) Project structure

```
ExpenseTracker/
├── PRD.md                    # Product requirements (what & why)
├── ARCHITECTURE.md           # Technical architecture (how it's built)
├── REQUIREMENTS.md           # Non-functional requirements & quality bars
├── CONVENTIONS.md            # This file (how to work on the project)
├── SCOPE.md                  # Version scope & roadmap
│
├── frontend/                 # Vite + React SPA
│   ├── public/
│   ├── src/
│   │   ├── routes/           # React Router v7 page components
│   │   ├── components/       # Reusable UI components
│   │   │   ├── ui/           # shadcn/ui base components
│   │   │   ├── charts/       # Recharts wrapper components
│   │   │   ├── forms/        # Form components (expense, limit, etc.)
│   │   │   └── layout/       # Navigation, sidebar, tab bar
│   │   ├── hooks/            # Custom React hooks
│   │   ├── lib/              # Utilities, API client, constants
│   │   ├── types/            # TypeScript type definitions
│   │   ├── i18n/             # react-i18next config + translation files (2.0.0+)
│   │   └── styles/           # Global styles, Tailwind config
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── package.json
│   └── tsconfig.json
│
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── main.py           # FastAPI app entry point
│   │   ├── config.py         # Settings & environment variables
│   │   ├── auth/             # Auth routes, Google OAuth, JWT
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── routers/          # API route handlers (one file per domain)
│   │   │   ├── spaces.py
│   │   │   ├── expenses.py
│   │   │   ├── categories.py
│   │   │   ├── tags.py
│   │   │   ├── payment_methods.py
│   │   │   ├── limits.py
│   │   │   ├── recurring.py   # 1.1.0+
│   │   │   ├── insights.py
│   │   │   ├── merchants.py
│   │   │   ├── health.py
│   │   │   └── internal.py    # Internal cron endpoints (1.1.0+)
│   │   ├── services/         # Business logic layer
│   │   ├── db/               # Database session, connection
│   │   └── middleware/       # Auth middleware, space membership, rate limiting
│   ├── alembic/              # Database migrations
│   ├── tests/
│   │   ├── unit/             # Unit tests (business logic)
│   │   └── integration/      # Integration tests (API endpoints)
│   ├── requirements.txt
│   └── pyproject.toml
│
└── .github/
    └── workflows/
        ├── ci.yml             # CI pipeline (test, lint, build)
        ├── deploy.yml         # CD pipeline (deploy to Azure)
        └── cron.yml           # Scheduled job triggers (1.1.0+)
```

---

## 2) Coding standards

### Python (backend)

- **Python 3.11+**
- **Formatter**: `black` (default settings)
- **Linter**: `ruff` (replaces flake8, isort, etc.)
- **Type hints**: required on all function signatures
- **Async**: use `async def` for all route handlers and database operations
- **Naming**:
  - Files: `snake_case.py`
  - Classes: `PascalCase`
  - Functions/variables: `snake_case`
  - Constants: `UPPER_SNAKE_CASE`
- **Imports**: standard library → third-party → local (enforced by ruff)
- **Docstrings**: required for all service functions and complex logic. Not required for straightforward CRUD route handlers.

### TypeScript (frontend)

- **TypeScript strict mode** enabled
- **Formatter**: `prettier` (default settings)
- **Linter**: `eslint` with recommended React config
- **Naming**:
  - Files: `kebab-case.tsx` for components, `camelCase.ts` for utilities
  - Components: `PascalCase`
  - Functions/variables: `camelCase`
  - Types/interfaces: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
- **Component style**: functional components with hooks (no class components)
- **Props**: define with TypeScript interfaces, not `any`
- **State management**: TanStack Query for server state. React `useState`/`useReducer` for local UI state only.

### SQL

- Table names: `snake_case`, plural (e.g., `expenses`, `expense_lines`)
- Column names: `snake_case`
- All foreign keys explicitly named
- Migrations: one migration per logical change (don't batch unrelated schema changes)

---

## 3) API conventions

### URL patterns
- All endpoints under `/api/v1/`
- Space-scoped: `/api/v1/spaces/{space_id}/...`
- Resource names are **plural** (e.g., `/expenses`, `/categories`, `/limits`)
- Use kebab-case for multi-word resources (e.g., `/payment-methods`)

### HTTP methods
- `GET` — read (list or detail)
- `POST` — create
- `PUT` — full update (replace all fields; client sends the complete resource)
- `PATCH` — partial update (client sends only the fields to change; omitted fields remain unchanged)
- `DELETE` — delete

**When to use PUT vs PATCH:**
- Use `PUT` when the client sends the **complete resource** (e.g., space settings where all fields are displayed in a single form).
- Use `PATCH` for most entity updates (expenses, limits, recurring templates, payment methods) where users typically edit one or two fields at a time. This reduces payload size, avoids accidental overwrites from stale client state, and matches user intent more accurately.
- Pydantic schemas for PATCH endpoints should use `Optional` fields with `model.model_dump(exclude_unset=True)` to distinguish "field not sent" (keep current value) from "field explicitly set to null" (clear the value).
- In the current API, `PUT` is used only for `PUT /spaces/{space_id}` (space settings) and `PUT /spaces/{space_id}/categories/{cat_id}` (category rename — trivially a full replacement). All other update endpoints use `PATCH`.

### Response format
- Success: return the resource (or list of resources) directly
- List endpoints: return `{ "data": [...], "next_cursor": "..." }`
- Error: return `{ "error": { "code": "ERROR_CODE", "message": "...", "details": {...} } }`

### Status codes
- `200` — success
- `201` — created
- `204` — deleted (no content)
- `400` — bad request
- `401` — not authenticated
- `403` — not authorized
- `404` — not found
- `409` — conflict
- `422` — unprocessable entity
- `429` — rate limited (with `Retry-After` header)
- `500` — internal error

### Validation
- All request bodies validated by Pydantic schemas
- All query parameters validated with FastAPI's `Query()` with type hints
- Return `422` with field-level error details for validation failures

---

## 4) Git workflow

### Branch strategy

- **`main`** — always equals the latest tagged release. No direct pushes. Only updated via release branch merges.
- **`release/X.Y.x`** — long-lived release branch per minor version (e.g., `release/1.0.x` for all `1.0.*` patches). Created from `main` after a version tag. Accumulates 2–3 changes (fix/\*, chore/\*), then merges to `main` with a new patch tag. Stays open until the next minor version begins (e.g., `release/1.0.x` is retired when `release/1.1.x` is created).
- **`fix/{short-description}`** — bug fix branches. Created from and merged into the current `release/X.Y.x` branch via PR (e.g., `fix/limit-calculation`).
- **`chore/{short-description}`** — infrastructure, docs, or tooling changes. Created from and merged into the current `release/X.Y.x` branch via PR.
- **`feature/{short-description}`** — feature branches for new minor/major versions. Created from `main` and merged into `main` or a new release branch.
- **`hotfix/{short-description}`** — urgent fixes that cannot wait for the normal release cycle. Created from `main`, merged to both `main` and the active release branch.
- **`copilot/{short-description}`** — branches authored by the Copilot coding agent (created automatically when assigning an issue to Copilot). Treated as equivalent to `fix/*` or `chore/*` depending on the change; targets the current `release/X.Y.x` for patches or `main` for feature work, following the same review rules as a human-authored PR.

### Workflow

```
main (v1.0.0)
  └── release/1.0.x
        ├── fix/some-bug       → PR into release/1.0.x
        ├── fix/another-bug    → PR into release/1.0.x
        ├── chore/update-docs  → PR into release/1.0.x
        └── (2-3 changes ready)
              → PR release/1.0.x → main
              → tag v1.0.1 + GitHub Release
              → deploy (automatic)
```

- `fix/*` and `chore/*` branches are created **from** the active release branch and PRs target that release branch.
- When 2–3 changes accumulate on the release branch, open a PR from `release/X.Y.x` → `main`. Squash merge, tag the merge commit (e.g., `v1.0.1`), and create a GitHub Release with notes describing the bundled changes.
- The release branch stays open after merging — future patches continue on it.
- Deploy is triggered automatically when `main` receives a push (via `deploy.yml`).

### Version bump advisory

If a change on a `fix/*` or `chore/*` branch is significant enough to warrant a **minor** (new feature) or **major** (breaking change) version bump rather than a patch, the developer or agent must flag this before merging. The change should be moved to a `feature/*` branch targeting a new release cycle instead.

### Tags and GitHub Releases

- Tags follow SemVer with `v` prefix: `v1.0.0`, `v1.0.1`, `v1.1.0`, `v2.0.0`.
- Every tag gets a **GitHub Release** with a description of what's included (2–3 bullet points per bundled change).
- Tags are created on `main` merge commits only.

### Commit messages
- Format: `type: short description`
- Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `style`
- Examples:
  - `feat: add expense CRUD endpoints`
  - `fix: correct limit calculation for quarterly timeframe`
  - `test: add integration tests for invite lifecycle`
  - `docs: update API endpoint documentation`
- Keep commits atomic — one logical change per commit

### Pull requests
- PRs from `fix/*` and `chore/*` branches target `release/X.Y.x`
- PRs from `release/X.Y.x` target `main` (for version releases)
- PRs from `feature/*` branches target `main` or a new release branch
- PR title follows the same format as commit messages
- PR description should explain *what* and *why*, not much of the *how*. And should include a design specified behind the PR content (if applies).
- All tests must pass before merge
- Squash merge preferred (clean history)

---

## 5) Environment setup

### Prerequisites
- Node.js 20+ and npm
- Python 3.11+
- PostgreSQL 15+ (local or Docker)
- Azure CLI (for deployment)
- GitHub CLI (optional, for cron workflow management)

### Local development

**Frontend:**
```bash
cd frontend
npm install
npm run dev         # starts Vite dev server on localhost:5173
```

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # or venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload   # starts FastAPI on localhost:8000
```

**Database:**
```bash
# Option 1: Docker
docker run --name expense-db -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=expense_tracker -p 5432:5432 -d postgres:15

# Option 2: Local PostgreSQL
createdb expense_tracker
```

**Migrations:**
```bash
cd backend
alembic upgrade head            # apply all migrations
alembic revision --autogenerate -m "description"  # create new migration
```

### Environment variables

**Backend (`backend/.env`):**
```
DATABASE_URL=postgresql+asyncpg://postgres:devpass@localhost:5432/expense_tracker
GOOGLE_CLIENT_ID=<from Google Cloud Console>
GOOGLE_CLIENT_SECRET=<from Google Cloud Console>
JWT_SECRET=<random-secret-for-signing>
JWT_SECRET_PREVIOUS=<previous-secret-during-rotation; optional>
INTERNAL_CRON_TOKEN=<random-secret-for-cron-auth>
FRONTEND_URL=http://localhost:5173
ENVIRONMENT=development
```

**Frontend (`frontend/.env`):**
```
VITE_API_URL=http://localhost:8000/api/v1
```

### Running the full stack locally

**Quick start (all services):**
```bash
# Terminal 1: Database
docker run --name expense-db -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=expense_tracker -p 5432:5432 -d postgres:15

# Terminal 2: Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload      # http://localhost:8000

# Terminal 3: Frontend
cd frontend
npm install
npm run dev                        # http://localhost:5173
```

**Verifying the stack is running:**
- Frontend: open `http://localhost:5173` — should show the sign-in page
- Backend: `curl http://localhost:8000/api/v1/health` — should return `{"status": "ok", "db": "connected"}`
- Database: `docker exec -it expense-db psql -U postgres -d expense_tracker -c "\dt"` — should list tables after migrations

**Google OAuth local setup:**
1. Go to Google Cloud Console → APIs & Services → Credentials
2. Create an OAuth 2.0 Client ID (Web application)
3. Add `http://localhost:8000/api/v1/auth/google/callback` as an authorized redirect URI
4. Copy Client ID and Client Secret into `backend/.env`

**Common issues:**
- Port conflict on 5432: another PostgreSQL instance is running. Stop it or use `-p 5433:5432` and update `DATABASE_URL`
- `alembic upgrade head` fails: ensure the database exists and `DATABASE_URL` is correct
- Google OAuth redirect mismatch: the redirect URI in Google Console must exactly match the callback path
- Vite proxy not working: ensure `vite.config.ts` has the proxy config and the backend is running on port 8000

**Resetting the database:**
```bash
docker stop expense-db && docker rm expense-db
docker run --name expense-db -e POSTGRES_PASSWORD=devpass -e POSTGRES_DB=expense_tracker -p 5432:5432 -d postgres:15
cd backend && alembic upgrade head
```

**Development seed data:**
```bash
cd backend
python -m app.seed    # populates a test space with sample data
```

The seed script (`backend/app/seed.py`) creates:
- 1 test space ("Demo Family") with 2 members
- 8 categories (from the recommended defaults)
- 3 payment methods (Cash + 2 cards)
- ~100 expenses spanning 3 months (realistic distribution across categories/merchants)
- 2 limits (weekly groceries, monthly total)
- Diverse merchants with repeat usage (for autocomplete and suggestion testing)

This provides enough data for dashboard charts, Insights filters, and limit alerts to be useful during development. The seed is idempotent — running it twice does not duplicate data.

---

## 6) Dependency management

### Frontend
- Use `npm` (not yarn or pnpm) for consistency
- Pin exact versions in `package.json` (no `^` or `~`)
- Run `npm audit` periodically
- shadcn/ui components are copied into `src/components/ui/` (not an npm dependency)

### Backend
- Use `pip` with `requirements.txt` (pinned versions)
- Use a virtual environment (`venv`) — never install globally
- Core dependencies: `fastapi`, `uvicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `python-jose[cryptography]`, `httpx`, `structlog`, `slowapi`
- Dev dependencies in a separate `requirements-dev.txt`: `pytest`, `pytest-asyncio`, `httpx`, `black`, `ruff`

---

## 7) Code organization rules

### Separation of concerns
- **Routers** handle HTTP (parse request, call service, return response). No business logic in routers.
- **Services** contain business logic (validation, calculations, orchestration). Services are pure functions or classes — no HTTP awareness.
- **Models** define database structure (SQLAlchemy). No business logic in models.
- **Schemas** define API contracts (Pydantic). Separate schemas for request and response when they differ.

### Frontend component organization
- **Route components** (`routes/` directory): minimal logic, compose from smaller components.
- **Feature components** (`components/forms/`, `components/charts/`): domain-specific, may call hooks.
- **UI components** (`components/ui/`): generic, reusable, no domain knowledge (shadcn/ui).
- **Hooks** (`hooks/`): encapsulate API calls and data transformation. One hook per domain (e.g., `useExpenses`, `useLimits`).
- **Types** (`types/`): shared TypeScript interfaces matching API response shapes.

### File size guidelines
- If a file exceeds ~300 lines, consider splitting it (if needed).
- One router file per domain (expenses, categories, limits, etc.).
- One service file per domain.

---

## 8) Deployment

### Frontend (Azure Static Web Apps)
- Deployed automatically on push to `main` via GitHub Actions
- Preview deployments on PRs (Azure Static Web Apps preview environments)
- `linkedBackend` configuration proxies `/api/*` to Azure App Service
- Vite builds a static bundle (`npm run build` → `dist/`) deployed to Static Web Apps
- SPA fallback: Azure Static Web Apps serves `index.html` for all routes (configured in `staticwebapp.config.json`)
- Environment variables: build-time via `VITE_` prefix in `.env` files; runtime via Azure Static Web Apps settings

### Backend (Azure App Service)
- Deployed via GitHub Actions CI/CD pipeline
- Pipeline: install deps → run tests → deploy to Azure
- Environment variables configured in Azure App Service settings

### Scheduled jobs (GitHub Actions cron)
- Defined in `.github/workflows/cron.yml`
- Daily trigger: calls `POST /api/v1/internal/cron/recurring-generate` (1.1.0+)
- Monthly trigger: calls `POST /api/v1/internal/cron/wrap-generate` (2.0.0+)
- Authenticated via `INTERNAL_CRON_TOKEN` secret

### Database migrations
- Run `alembic upgrade head` as part of deployment pipeline (before new code starts serving)
- Never modify a migration that has been applied to production — create a new one

---

## 9) Documentation rules

- These 6 project documents are the source of truth: PRD, ARCHITECTURE, REQUIREMENTS, CONVENTIONS, SCOPE, and UI_SPECS.
- `design/UI_SPECS.md` defines visual layout, component placement, color palette, and design decisions per view, per version. PRD §8 remains the high-level view list; UI_SPECS has the detailed specs.
- The `design/` folder at project root contains UI_SPECS.md plus HTML visual reference mockups (home, transactions, add-expense — mobile and desktop). These are the design source of truth for frontend implementation.
- Update the relevant document when a decision changes.
- Do not create ad-hoc markdown files for planning or notes — keep decisions in the appropriate document. If there is a need for additional files that shouldn't live under the existing documents, ask first.
- API documentation is auto-generated by FastAPI (OpenAPI/Swagger) — do not maintain a separate API doc.
- Code comments: only when the *why* is non-obvious. Do not comment *what* the code does if it's self-evident. Should be decisions, limitations, complex logic, business rules, etc.
