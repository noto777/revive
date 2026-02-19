"""
FastAPI application factory.

Creates the main API app with:
- Middleware (CORS, logging, tenant resolution)
- Lifespan management (startup/shutdown)
- Health check endpoint
- Route mounting
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from db.session import get_async_session_maker, init_db
from engine.signals import ShutdownManager
from logger import setup_logging

logger = structlog.get_logger()


# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.
    
    Startup:
    - Initialize database
    - Setup logging
    - Initialize shutdown manager
    
    Shutdown:
    - Cleanup connections
    - Shutdown executor scheduler
    """
    # Startup
    logger.info("api_starting")
    
    # Setup logging
    setup_logging()
    
    # Initialize database
    init_db()
    
    # Initialize shutdown manager
    shutdown_manager = ShutdownManager()
    app.state.shutdown_manager = shutdown_manager
    
    logger.info("api_started")
    
    yield
    
    # Shutdown
    logger.info("api_stopping")
    
    # Trigger graceful shutdown
    shutdown_manager.trigger_shutdown()
    
    logger.info("api_stopped")


def create_app() -> FastAPI:
    """
    Application factory.
    
    Returns configured FastAPI application with:
    - CORS middleware
    - Request logging middleware
    - Health check endpoint
    - API routes (v1)
    """
    app = FastAPI(
        title="IronHand SaaS API",
        description="Multi-tenant algorithmic trading platform",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure allowed origins
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """Log all requests and responses."""
        logger.info(
            "request_received",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )
        
        response = await call_next(request)
        
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
        )
        
        return response
    
    # Exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        logger.error(
            "unhandled_exception",
            method=request.method,
            path=request.url.path,
            error=str(exc),
            exc_info=True,
        )
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected error occurred",
            },
        )
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """
        Health check endpoint.
        
        Returns:
            - status: "healthy"
            - version: API version
        """
        return {
            "status": "healthy",
            "version": "1.0.0",
            "service": "ironhand-saas",
        }
    
    @app.get("/")
    async def root():
        """Root endpoint - API info."""
        return {
            "name": "IronHand SaaS API",
            "version": "1.0.0",
            "docs": "/docs",
            "health": "/health",
        }
    
    # TODO: Mount API routes when implemented
    # from api.routes import strategies, positions, orders, dashboard, accounts, webhooks
    # app.include_router(strategies.router, prefix="/api/v1", tags=["strategies"])
    # app.include_router(positions.router, prefix="/api/v1", tags=["positions"])
    # app.include_router(orders.router, prefix="/api/v1", tags=["orders"])
    # app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
    # app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
    # app.include_router(webhooks.router, prefix="/api/v1", tags=["webhooks"])
    
    logger.info("app_created")
    
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
