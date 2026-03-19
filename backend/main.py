"""
Main FastAPI application for Lumina backend
Handles chat requests, RAG pipeline orchestration, and API endpoints
"""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging.config
from dotenv import load_dotenv

from app.routes import chat_routes, health_routes
from app.logging_config import setup_logging
from app.utils.rate_limiter import RateLimiter

# Load environment variables from backend/.env and override shell vars
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Setup logging
LOGGING_CONFIG = setup_logging()
logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan (startup and shutdown)"""
    # Startup
    logger.info("Lumina backend starting up...")
    logger.info(f"Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info("RAG pipeline and vector database connections initialized")
    
    yield
    
    # Shutdown
    logger.info("Lumina backend shutting down...")


# Initialize FastAPI app
app = FastAPI(
    title="Lumina API",
    description="AI that illuminates every webpage - RAG-powered chatbot API for webpage content understanding",
    version="1.0.0",
    lifespan=lifespan
)

# Add middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize rate limiter
rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_RPM", "60")),
    requests_per_hour=int(os.getenv("RATE_LIMIT_RPH", "1000"))
)


# Include route handlers
app.include_router(health_routes.router, prefix="/api", tags=["health"])
app.include_router(chat_routes.router, prefix="/api", tags=["chat"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Lumina API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "ai-browsing-copilot",
        "version": "1.0.0"
    }


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    logger.error(f"Validation error: {str(exc)}")
    raise HTTPException(status_code=400, detail=str(exc))


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info"
    )
