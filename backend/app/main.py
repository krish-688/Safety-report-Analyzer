from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.routers import alerts, audit, auth, dashboard, equipment, incidents, investigations, plants, users


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()  # dev convenience: create tables if missing
    yield


app = FastAPI(title=settings.APP_NAME, version="0.2.0", lifespan=lifespan,
              docs_url="/docs", openapi_url=f"{settings.API_PREFIX}/openapi.json")

app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get(f"{settings.API_PREFIX}/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "app": settings.APP_NAME}


for r in (auth.router, users.router, plants.router, equipment.router, incidents.router, dashboard.router, investigations.router, alerts.router, audit.router):
    app.include_router(r, prefix=settings.API_PREFIX)
