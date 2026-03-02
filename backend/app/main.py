from fastapi import FastAPI

from app.auth.router import router as auth_router
from app.routers.categories import router as categories_router
from app.routers.health import router as health_router
from app.routers.merchants import router as merchants_router
from app.routers.payment_methods import router as payment_methods_router
from app.routers.spaces import router as spaces_router
from app.routers.tags import router as tags_router

app = FastAPI(title="Expense Tracker API", version="0.1.0")
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(spaces_router)
app.include_router(categories_router)
app.include_router(tags_router)
app.include_router(merchants_router)
app.include_router(payment_methods_router)
