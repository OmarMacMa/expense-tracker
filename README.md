# Expense Tracker & Budget Insights

Multi-tenant SaaS web app for couples/families to track shared expenses. React SPA frontend + FastAPI backend + PostgreSQL.

## Quick Start

### Prerequisites

- Node.js 20+ and npm
- Python 3.11+
- Docker (for PostgreSQL)

### 1. Start the database

```bash
docker compose up -d
```

This starts PostgreSQL 15 on port 5432 with database `expense_tracker`.

### 2. Start the backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

# Apply migrations (once DB schema exists)
# alembic upgrade head

# Start the API server
uvicorn app.main:app --reload    # http://localhost:8000
```

### 3. Start the frontend

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173
```

### Verify

- **Frontend**: Open http://localhost:5173
- **Backend**: `curl http://localhost:8000/api/v1/health` → `{"status": "ok"}`
- **Database**: `docker exec -it expense-db psql -U postgres -d expense_tracker -c "\dt"`

### Environment Variables

Copy the example env files and fill in your values:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

See `CONVENTIONS.md` §5 for full environment setup details.

## Project Documentation

| Document | Description |
|---|---|
| [PRD.md](PRD.md) | Product requirements (what & why) |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Technical architecture (how) |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Non-functional requirements & quality bars |
| [CONVENTIONS.md](CONVENTIONS.md) | Coding standards & workflow |
| [SCOPE.md](SCOPE.md) | Version scope & roadmap |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | Phased build plan |

## Commands

### Backend

```bash
cd backend
uvicorn app.main:app --reload     # Run server
ruff check .                      # Lint
black .                           # Format
pytest                            # Test
```

### Frontend

```bash
cd frontend
npm run dev                       # Dev server
npm run build                     # Build
npx eslint .                      # Lint
npx prettier --check .            # Check formatting
```

### Database

```bash
docker compose up -d              # Start PostgreSQL
docker compose down               # Stop PostgreSQL
docker compose down -v            # Stop + delete data
```
