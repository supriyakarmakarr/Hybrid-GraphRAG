"""
GraphRAG - Main FastAPI Application
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.logging import setup_logging
from app.core.db import init_databases, close_databases
from app.api.v1 import health, auth, ingest, search, query, workspace, feedback

setup_logging()
log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", env=settings.ENVIRONMENT)
    await init_databases()
    yield
    await close_databases()
    log.info("shutdown")


app = FastAPI(
    title="GraphRAG API",
    version="1.0.0",
    description="Hybrid RAG with Knowledge Graph — secure, multi-tenant",
    lifespan=lifespan,
    # Hide docs in production
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url=None,
)

# ─── Middleware ──────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ─── Routers ────────────────────────────────────────────────────────
app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router,   prefix="/api/v1")
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(query.router,  prefix="/api/v1")
app.include_router(workspace.router, prefix="/api/v1")
app.include_router(feedback.router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error("unhandled_exception", error_type=type(exc).__name__, path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
