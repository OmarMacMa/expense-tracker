#!/bin/bash
# Azure Resource Setup for Expense Tracker
# Run this script once to create all required Azure resources.
#
# Prerequisites:
#   - Azure CLI installed and logged in (`az login`)
#   - An active Azure subscription
#
# Usage: bash azure-setup.sh

set -e

# ============================================================
# Configuration — customize these values
# ============================================================
RESOURCE_GROUP="expense-tracker-rg"
LOCATION="eastus"                    # Change to your preferred region
DB_SERVER_NAME="expense-tracker-db"  # Must be globally unique
DB_NAME="expense_tracker"
DB_ADMIN_USER="etadmin"
DB_ADMIN_PASSWORD=""                 # Will prompt if empty
BACKEND_APP_NAME="expense-tracker-api"  # Must be globally unique
FRONTEND_APP_NAME="expense-tracker-web" # Must be globally unique

# ============================================================
# Prompt for DB password if not set
# ============================================================
if [ -z "$DB_ADMIN_PASSWORD" ]; then
  read -sp "Enter PostgreSQL admin password: " DB_ADMIN_PASSWORD
  echo
fi

echo "🚀 Creating Azure resources for Expense Tracker..."

# ============================================================
# 1. Resource Group
# ============================================================
echo "📦 Creating resource group: $RESOURCE_GROUP"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# ============================================================
# 2. PostgreSQL Flexible Server (B1ms, ~$15-25/mo)
# ============================================================
echo "🗄️  Creating PostgreSQL Flexible Server: $DB_SERVER_NAME"
az postgres flexible-server create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DB_SERVER_NAME" \
  --location "$LOCATION" \
  --admin-user "$DB_ADMIN_USER" \
  --admin-password "$DB_ADMIN_PASSWORD" \
  --sku-name Standard_B1ms \
  --tier Burstable \
  --storage-size 32 \
  --version 15 \
  --yes

echo "📊 Creating database: $DB_NAME"
az postgres flexible-server db create \
  --resource-group "$RESOURCE_GROUP" \
  --server-name "$DB_SERVER_NAME" \
  --database-name "$DB_NAME"

# Allow Azure services to connect
echo "🔓 Configuring firewall for Azure services"
az postgres flexible-server firewall-rule create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$DB_SERVER_NAME" \
  --rule-name AllowAzureServices \
  --start-ip-address 0.0.0.0 \
  --end-ip-address 0.0.0.0

# ============================================================
# 3. App Service (Linux B1, ~$13/mo)
# ============================================================
echo "🖥️  Creating App Service Plan"
az appservice plan create \
  --resource-group "$RESOURCE_GROUP" \
  --name "${BACKEND_APP_NAME}-plan" \
  --sku B1 \
  --is-linux

echo "🐍 Creating App Service: $BACKEND_APP_NAME"
az webapp create \
  --resource-group "$RESOURCE_GROUP" \
  --plan "${BACKEND_APP_NAME}-plan" \
  --name "$BACKEND_APP_NAME" \
  --runtime "PYTHON:3.13"

# Configure startup command
az webapp config set \
  --resource-group "$RESOURCE_GROUP" \
  --name "$BACKEND_APP_NAME" \
  --startup-file "gunicorn -w 2 -k uvicorn.workers.UvicornWorker app.main:app --chdir backend"

# ============================================================
# 4. Static Web Apps (Free tier, $0)
# ============================================================
echo "🌐 Creating Static Web App: $FRONTEND_APP_NAME"
az staticwebapp create \
  --resource-group "$RESOURCE_GROUP" \
  --name "$FRONTEND_APP_NAME" \
  --location "$LOCATION" \
  --sku Free

# ============================================================
# Output connection info
# ============================================================
DB_HOST="${DB_SERVER_NAME}.postgres.database.azure.com"
DATABASE_URL="postgresql+asyncpg://${DB_ADMIN_USER}:${DB_ADMIN_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?ssl=require"

echo ""
echo "============================================================"
echo "✅ All Azure resources created!"
echo "============================================================"
echo ""
echo "📋 Next steps:"
echo ""
echo "1. Set App Service environment variables:"
echo "   az webapp config appsettings set \\"
echo "     --resource-group $RESOURCE_GROUP \\"
echo "     --name $BACKEND_APP_NAME \\"
echo "     --settings \\"
echo "       DATABASE_URL=\"$DATABASE_URL\" \\"
echo "       GOOGLE_CLIENT_ID=\"<your-google-client-id>\" \\"
echo "       GOOGLE_CLIENT_SECRET=\"<your-google-client-secret>\" \\"
echo "       JWT_SECRET=\"$(openssl rand -hex 32)\" \\"
echo "       FRONTEND_URL=\"https://${FRONTEND_APP_NAME}.azurestaticapps.net\" \\"
echo "       ENVIRONMENT=\"production\" \\"
echo "       SENTRY_DSN=\"<your-backend-sentry-dsn>\""
echo ""
echo "2. Add GitHub secrets:"
echo "   - AZURE_BACKEND_APP_NAME = $BACKEND_APP_NAME"
echo "   - AZURE_BACKEND_PUBLISH_PROFILE = (download from Azure Portal → App Service → Deployment Center)"
echo "   - AZURE_STATIC_WEB_APPS_API_TOKEN = (from Azure Portal → Static Web App → Manage deployment token)"
echo "   - DATABASE_URL = $DATABASE_URL"
echo "   - VITE_SENTRY_DSN = <your-frontend-sentry-dsn>"
echo ""
echo "3. Update Google OAuth redirect URI:"
echo "   https://${BACKEND_APP_NAME}.azurewebsites.net/api/v1/auth/google/callback"
echo ""
echo "4. Link backend to Static Web App (in Azure Portal):"
echo "   Static Web App → Settings → APIs → Link → Select $BACKEND_APP_NAME"
echo ""
echo "5. Push to main to trigger deployment!"
echo ""
