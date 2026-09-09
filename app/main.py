"""MemoForge — FastAPI application entry point.

Production-grade client documentation generator for Warba Bank.
"""

from __future__ import annotations

import logging
import sys

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.memo import router as memo_router
from app.core.config import get_settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
)

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI-Powered Client Documentation Engine for Warba Bank",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(memo_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and validate config on startup."""
    from app.core.business_config import load_config
    from app.db.session import init_db

    logger = logging.getLogger(__name__)
    logger.info("MemoForge starting up (env=%s, mock=%s)", settings.app_env, settings.mock_mode)

    # Validate business config
    try:
        load_config()
        logger.info("Business config validated")
    except Exception as e:
        logger.error("Config validation failed: %s", e)

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning("Database init skipped (may already exist): %s", e)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "env": settings.app_env,
        "mock_mode": settings.mock_mode,
    }


@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "description": "AI-Powered Client Documentation Engine for Warba Bank",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
