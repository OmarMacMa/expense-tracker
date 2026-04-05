# Operations Guide

## Deployment

### First-time setup
1. Run `bash azure-setup.sh` to create Azure resources
2. Follow the output instructions to configure env vars and GitHub secrets
3. Push to `main` to trigger the first deployment

### Continuous deployment
- Every push to `main` triggers: CI (lint + test + build) → Deploy (backend + frontend)
- Deployments are atomic — if CI fails, no deploy happens

### Backend startup
```
gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app
```
Workers: 2 (appropriate for B1 tier with 1.75GB RAM)

### Database migrations
Migrations run automatically as part of the deploy pipeline.
To run manually:
```bash
cd backend
alembic upgrade head      # Apply all pending
alembic downgrade -1      # Rollback last migration
alembic history           # View migration history
```

---

## Rollback Procedures

### Application rollback
Azure App Service supports deployment slots:
1. Go to Azure Portal → App Service → Deployment slots
2. Swap the "production" slot with the previous deployment
3. Or redeploy a specific commit: `git push origin <commit-sha>:main`

### Database rollback
```bash
alembic downgrade -1    # Rollback one migration
alembic downgrade <revision>  # Rollback to specific revision
```
**Rule**: Never modify a migration that has been applied to production. Always create a new migration.

### Emergency procedures
1. **App is down**: Check Azure Portal → App Service → Diagnose and solve problems
2. **Database issues**: Azure PostgreSQL → Connection security → Verify firewall rules
3. **Auth broken**: Verify GOOGLE_CLIENT_ID/SECRET and JWT_SECRET in App Service settings

---

## Monitoring & Alerts

### Built-in monitoring (free)
Azure App Service provides:
- Uptime monitoring
- Response time metrics
- Error rate tracking
- CPU/memory usage

### Recommended alert rules (free tier, up to 10 rules)

| Alert | Condition | Action |
|-------|-----------|--------|
| Health check failure | GET /api/v1/health returns non-200 for 5 min | Email notification |
| 5xx error spike | Server errors > 10 in 5 minutes | Email notification |
| High response time | Average response time > 5s for 5 min | Email notification |

To set up: Azure Portal → App Service → Alerts → New alert rule

### Health check endpoint
```
GET /api/v1/health
Response: {"status": "ok", "db": "connected"}
```
Configure as App Service health check probe: Settings → Health check → Path: `/api/v1/health`

---

## Environment Variables

### Backend (App Service)
| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string with `?ssl=require` |
| GOOGLE_CLIENT_ID | Yes | Google OAuth client ID |
| GOOGLE_CLIENT_SECRET | Yes | Google OAuth client secret |
| JWT_SECRET | Yes | Random 64-char hex string |
| FRONTEND_URL | Yes | Static Web App URL |
| ENVIRONMENT | Yes | `production` |
| SENTRY_DSN | No | Sentry backend DSN |
| LOG_LEVEL | No | Default: `INFO` |

### Frontend (build-time)
| Variable | Required | Description |
|----------|----------|-------------|
| VITE_SENTRY_DSN | No | Sentry frontend DSN |

### GitHub Secrets (for CD pipeline)
| Secret | Description |
|--------|-------------|
| AZURE_BACKEND_APP_NAME | App Service name |
| AZURE_BACKEND_PUBLISH_PROFILE | Download from Azure Portal |
| AZURE_STATIC_WEB_APPS_API_TOKEN | From Static Web App deployment token |
| DATABASE_URL | For running migrations in CI |
| VITE_SENTRY_DSN | Frontend Sentry DSN (build-time) |
